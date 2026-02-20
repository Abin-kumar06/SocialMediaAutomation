"""
Instagram / Facebook Graph access token lifecycle.

Converts short-lived OAuth tokens to long-lived tokens (~60 days) and stores them.
The app must NEVER use short-lived tokens for posting — only long-lived tokens
are stored and used.
"""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Tuple

import requests

from app.config import settings, update_env_token

logger = logging.getLogger(__name__)

# Meta OAuth endpoint — MUST be used exactly as per Meta docs
META_OAUTH_ACCESS_TOKEN_URL = "https://graph.facebook.com/v24.0/oauth/access_token"


class InstagramReauthRequired(Exception):
    """
    Raised when the token is expired/invalid and the user must re-login.
    Meta error code 190 (and subcode 463 for expired) trigger this.
    """


@dataclass(frozen=True)
class InstagramAccessTokenRecord:
    access_token: str
    expires_at: datetime  # UTC
    last_refreshed_at: datetime  # UTC
    status: str  # "active" | "needs_reauth"

    def expires_in(self, now_utc: Optional[datetime] = None) -> timedelta:
        now = now_utc or datetime.now(timezone.utc)
        return self.expires_at - now


class InMemoryInstagramTokenStore:
    """
    MVP token store.

    Replace with a DB-backed repository when you add multi-user support.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._record: Optional[InstagramAccessTokenRecord] = None

    def get(self) -> Optional[InstagramAccessTokenRecord]:
        with self._lock:
            return self._record

    def set(self, record: InstagramAccessTokenRecord) -> None:
        with self._lock:
            self._record = record

    def mark_needs_reauth(self) -> None:
        with self._lock:
            if not self._record:
                self._record = InstagramAccessTokenRecord(
                    access_token="",
                    expires_at=datetime.now(timezone.utc),
                    last_refreshed_at=datetime.now(timezone.utc),
                    status="needs_reauth",
                )
                return
            self._record = InstagramAccessTokenRecord(
                access_token=self._record.access_token,
                expires_at=self._record.expires_at,
                last_refreshed_at=self._record.last_refreshed_at,
                status="needs_reauth",
            )


class InstagramTokenService:
    """
    Complete Instagram/Facebook Graph access token lifecycle.

    Required Meta flows (used exactly as provided):

    - Short-lived → Long-lived exchange:
      GET https://graph.facebook.com/v24.0/oauth/access_token
        ?grant_type=fb_exchange_token
        &client_id=FB_APP_ID
        &client_secret=FB_APP_SECRET
        &fb_exchange_token=SHORT_LIVED_TOKEN

    - Refresh long-lived token:
      GET https://graph.facebook.com/v24.0/oauth/access_token
        ?grant_type=fb_refresh_token
        &client_id=FB_APP_ID
        &client_secret=FB_APP_SECRET
        &fb_exchange_token=LONG_LIVED_TOKEN
    """

    def __init__(
        self,
        *,
        store: Optional[InMemoryInstagramTokenStore] = None,
        fb_app_id: Optional[str] = None,
        fb_app_secret: Optional[str] = None,
        refresh_if_expires_within_days: int = 7,
    ) -> None:
        self._store = store or InMemoryInstagramTokenStore()
        self._fb_app_id = fb_app_id or os.getenv("FB_APP_ID") or settings.FB_APP_ID
        self._fb_app_secret = fb_app_secret or os.getenv("FB_APP_SECRET") or settings.FB_APP_SECRET
        self._refresh_window = timedelta(days=max(1, int(refresh_if_expires_within_days)))

        if not self._fb_app_id or not self._fb_app_secret:
            logger.warning("FB_APP_ID / FB_APP_SECRET not configured; token refresh will not work.")

    # ----------------------------
    # Public API
    # ----------------------------

    def exchange_short_lived_token(self, short_token: str) -> Tuple[str, datetime]:
        """
        Convert a short-lived user access token to a long-lived token (~60 days).

        Calls Meta OAuth endpoint exactly:
          GET https://graph.facebook.com/v24.0/oauth/access_token
            ?grant_type=fb_exchange_token
            &client_id=FB_APP_ID
            &client_secret=FB_APP_SECRET
            &fb_exchange_token=SHORT_LIVED_TOKEN

        Returns:
            (long_token, expires_at) — expires_at is UTC.
        Raises:
            InstagramReauthRequired: If short token is expired/invalid (Meta code 190).
            RuntimeError: If Meta returns another error or response is malformed.
        """
        short_token = (short_token or "").strip()
        if not short_token:
            raise ValueError("short_token cannot be empty")

        self._require_app_credentials()
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": self._fb_app_id,
            "client_secret": self._fb_app_secret,
            "fb_exchange_token": short_token,
        }
        logger.info("Exchanging short-lived token for long-lived token (Meta OAuth).")
        data = self._meta_get(params=params)

        # Parse access_token and expires_in from Meta response
        long_token = (data.get("access_token") or "").strip()
        expires_in = data.get("expires_in")
        if not long_token:
            raise RuntimeError("Meta response missing access_token")
        if expires_in is None:
            raise RuntimeError("Meta response missing expires_in")

        # Calculate expires_at in UTC (never store or use short-lived token after this)
        now_utc = datetime.now(timezone.utc)
        expires_at = now_utc + timedelta(seconds=int(expires_in))

        return (long_token, expires_at)

    def store_long_lived_token(
        self,
        long_token: str,
        expires_at: datetime,
    ) -> InstagramAccessTokenRecord:
        """
        Store the long-lived token only. Used immediately after exchange_short_lived_token.

        Persists: access_token (long-lived), expires_at (UTC), last_refreshed_at, status=active.
        Also updates runtime config and .env so existing posting code uses this token.
        """
        long_token = (long_token or "").strip()
        if not long_token:
            raise ValueError("long_token cannot be empty")

        now_utc = datetime.now(timezone.utc)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        record = InstagramAccessTokenRecord(
            access_token=long_token,
            expires_at=expires_at,
            last_refreshed_at=now_utc,
            status="active",
        )
        self._apply_and_store(record)
        logger.info("Stored long-lived token; expires_at=%s", expires_at.isoformat())
        return record

    def handle_oauth_callback(self, short_lived_token: str) -> InstagramAccessTokenRecord:
        """
        Call immediately after OAuth login: exchange short-lived → long-lived, store only long-lived, discard short-lived.
        """
        # Step 1: Exchange (never store the short-lived token)
        long_token, expires_at = self.exchange_short_lived_token(short_lived_token)
        # Step 2: Store ONLY the long-lived token; short-lived is discarded
        return self.store_long_lived_token(long_token, expires_at)

    def bootstrap_from_env(self) -> Optional[InstagramAccessTokenRecord]:
        """
        Optional bootstrap for existing deployments that already have PAGE_ACCESS_TOKEN in .env.

        We try refresh first (assumes token might already be long-lived),
        then try exchange (if it was short-lived).
        """
        token = (settings.PAGE_ACCESS_TOKEN or "").strip()
        if not token:
            return None

        logger.info("Bootstrapping Instagram token from environment.")

        # Try refresh (long-lived) first
        try:
            record = self.refresh_long_lived_token(token)
            self._apply_and_store(record)
            return record
        except InstagramReauthRequired:
            self._store.mark_needs_reauth()
            raise
        except Exception as e:
            logger.info("Refresh bootstrap failed; attempting exchange. Reason=%s", e)

        # Try exchange (short-lived → long-lived); exchange_short_lived_for_long_lived already stores
        try:
            record = self.exchange_short_lived_for_long_lived(token)
            return record
        except InstagramReauthRequired:
            self._store.mark_needs_reauth()
            raise
        except Exception as e:
            logger.exception("Token bootstrap failed; marking needs_reauth. Reason=%s", e)
            self._store.mark_needs_reauth()
            return None

    def get_record(self) -> Optional[InstagramAccessTokenRecord]:
        return self._store.get()

    def get_access_token_for_posting(self) -> str:
        """
        Call this before posting.

        - If token expires in <= 7 days, refresh first.
        - If refresh fails, mark needs_reauth and block posting.
        """
        record = self._store.get()
        if not record or record.status != "active" or not record.access_token:
            self._store.mark_needs_reauth()
            raise InstagramReauthRequired("No active Instagram access token. Re-authentication required.")

        now = datetime.now(timezone.utc)
        if record.expires_at <= now:
            self._store.mark_needs_reauth()
            raise InstagramReauthRequired("Instagram access token expired. Re-authentication required.")

        if record.expires_in(now) <= self._refresh_window:
            logger.info(
                "Token expires soon (%s). Refreshing before posting.",
                record.expires_in(now),
            )
            try:
                refreshed = self.refresh_long_lived_token(record.access_token)
                self._apply_and_store(refreshed)
                return refreshed.access_token
            except InstagramReauthRequired:
                self._store.mark_needs_reauth()
                raise
            except Exception as e:
                logger.exception("Pre-post refresh failed; marking needs_reauth. Reason=%s", e)
                self._store.mark_needs_reauth()
                raise InstagramReauthRequired("Token refresh failed; re-authentication required.")

        return record.access_token

    def scheduled_refresh(self, *, within_days: int = 10) -> None:
        """
        Scheduled job entry point.
        Refreshes tokens expiring within the next 7–10 days (default 10).
        """
        record = self._store.get()
        if not record or record.status != "active" or not record.access_token:
            return

        now = datetime.now(timezone.utc)
        window = timedelta(days=max(1, int(within_days)))
        if record.expires_at <= now:
            logger.warning("Scheduled refresh: token already expired; marking needs_reauth.")
            self._store.mark_needs_reauth()
            return

        if record.expires_in(now) <= window:
            logger.info("Scheduled refresh: token expires within %s; refreshing.", window)
            try:
                refreshed = self.refresh_long_lived_token(record.access_token)
                self._apply_and_store(refreshed)
                logger.info("Scheduled refresh succeeded. New expires_at=%s", refreshed.expires_at.isoformat())
            except InstagramReauthRequired as e:
                logger.warning("Scheduled refresh requires re-authentication: %s", e)
                self._store.mark_needs_reauth()
            except Exception as e:
                logger.exception("Scheduled refresh failed; keeping existing token. Reason=%s", e)

    def force_refresh_now(self) -> InstagramAccessTokenRecord:
        """
        Force an immediate refresh attempt of the currently stored token.
        Useful for a manual admin action or debugging.
        """
        record = self._store.get()
        if not record or record.status != "active" or not record.access_token:
            self._store.mark_needs_reauth()
            raise InstagramReauthRequired("No active token to refresh. Re-authentication required.")

        refreshed = self.refresh_long_lived_token(record.access_token)
        self._apply_and_store(refreshed)
        return refreshed

    # ----------------------------
    # Meta HTTP flows
    # ----------------------------

    def exchange_short_lived_for_long_lived(self, short_lived_token: str) -> InstagramAccessTokenRecord:
        """Internal: exchange short → long and return a record (used by bootstrap)."""
        long_token, expires_at = self.exchange_short_lived_token(short_lived_token)
        return self.store_long_lived_token(long_token, expires_at)

    def refresh_long_lived_token(self, long_lived_token: str) -> InstagramAccessTokenRecord:
        self._require_app_credentials()
        params = {
            "grant_type": "fb_refresh_token",
            "client_id": self._fb_app_id,
            "client_secret": self._fb_app_secret,
            "fb_exchange_token": long_lived_token,
        }
        logger.info("Refreshing long-lived token.")
        data = self._meta_get(params=params)
        return self._record_from_meta_response(data)

    # ----------------------------
    # Internals
    # ----------------------------

    def _require_app_credentials(self) -> None:
        if not self._fb_app_id or not self._fb_app_secret:
            raise RuntimeError("FB_APP_ID / FB_APP_SECRET must be configured to manage token lifecycle.")

    def _meta_get(self, *, params: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = requests.get(META_OAUTH_ACCESS_TOKEN_URL, params=params, timeout=20)
            # Meta uses JSON error payloads even on non-2xx
            payload: dict[str, Any] = {}
            try:
                payload = resp.json()
            except Exception:
                payload = {}

            if resp.status_code >= 400:
                self._raise_for_meta_error(payload, http_status=resp.status_code)

            # Some failures still come back 200 with an "error" key
            if isinstance(payload, dict) and payload.get("error"):
                self._raise_for_meta_error(payload, http_status=resp.status_code)

            return payload
        except InstagramReauthRequired:
            raise
        except requests.RequestException as e:
            raise RuntimeError(f"Meta token endpoint request failed: {e}") from e

    def _raise_for_meta_error(self, payload: dict[str, Any], *, http_status: int) -> None:
        err = payload.get("error") if isinstance(payload, dict) else None
        if not isinstance(err, dict):
            raise RuntimeError(f"Meta token endpoint error (HTTP {http_status}). Response: {payload}")

        code = err.get("code")
        subcode = err.get("error_subcode")
        message = err.get("message", "Meta API error")

        # Error 190: Invalid OAuth 2.0 Access Token — require re-login (do not store short-lived token)
        if code == 190:
            if subcode == 463:
                logger.warning("Meta token expired (code=190, subcode=463): %s", message)
            else:
                logger.warning("Meta token invalid (code=190): %s", message)
            raise InstagramReauthRequired(
                message or "Access token invalid or expired. Please log in again."
            )

        raise RuntimeError(f"Meta API error (HTTP {http_status}) code={code} subcode={subcode}: {message}")

    def _record_from_meta_response(self, data: dict[str, Any]) -> InstagramAccessTokenRecord:
        access_token = (data.get("access_token") or "").strip()
        expires_in = data.get("expires_in")
        if not access_token or not expires_in:
            raise RuntimeError(f"Unexpected token response from Meta: {data}")

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=int(expires_in))
        return InstagramAccessTokenRecord(
            access_token=access_token,
            expires_at=expires_at,
            last_refreshed_at=now,
            status="active",
        )

    def _apply_and_store(self, record: InstagramAccessTokenRecord) -> None:
        """
        Store in-memory record, and also update runtime + .env token used by existing posting code.
        """
        self._store.set(record)
        settings.PAGE_ACCESS_TOKEN = record.access_token
        update_env_token("PAGE_ACCESS_TOKEN", record.access_token)

