"""
Instagram / Facebook Graph access token lifecycle (Multi-user SQLite).
"""
from __future__ import annotations
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Tuple
import requests
from app.config import settings
from app.database import db

logger = logging.getLogger(__name__)

META_OAUTH_ACCESS_TOKEN_URL = "https://graph.facebook.com/v24.0/oauth/access_token"

class InstagramReauthRequired(Exception):
    """Raised when the token is expired/invalid and the user must re-login."""

class InstagramTokenService:
    def __init__(self, fb_app_id: Optional[str] = None, fb_app_secret: Optional[str] = None):
        self._fb_app_id = fb_app_id or settings.FB_APP_ID
        self._fb_app_secret = fb_app_secret or settings.FB_APP_SECRET
        if not self._fb_app_id or not self._fb_app_secret:
            logger.warning("FB_APP_ID / FB_APP_SECRET not configured; token refresh will not work.")

    def exchange_short_lived_token(self, short_token: str) -> Tuple[str, datetime]:
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": self._fb_app_id,
            "client_secret": self._fb_app_secret,
            "fb_exchange_token": short_token,
        }
        resp = requests.get(META_OAUTH_ACCESS_TOKEN_URL, params=params, timeout=20)
        data = resp.json()
        if resp.status_code >= 400 or data.get("error"):
            self._raise_for_meta_error(data)
        
        long_token = data.get("access_token")
        expires_in = data.get("expires_in")
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))
        return long_token, expires_at

    def store_long_lived_token(self, user_id: int, long_token: str, expires_at: datetime):
        with db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO instagram_accounts 
                (user_id, access_token, expires_at, last_refreshed_at, status) 
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, long_token, expires_at, datetime.now(timezone.utc), "active"))
            conn.commit()

    def get_access_token_for_user(self, user_id: int) -> str:
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM instagram_accounts WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if not row or row['status'] != 'active':
                raise InstagramReauthRequired("No active Instagram token.")
            
            expires_at = datetime.fromisoformat(row['expires_at'])
            if expires_at <= datetime.now(timezone.utc):
                raise InstagramReauthRequired("Instagram token expired.")
            
            # Auto-refresh if within 10 days
            if expires_at - datetime.now(timezone.utc) <= timedelta(days=10):
                try:
                    new_token, new_expires = self.refresh_token(row['access_token'])
                    self.store_long_lived_token(user_id, new_token, new_expires)
                    return new_token
                except Exception:
                    logger.exception("Auto-refresh failed.")
            
            return row['access_token']

    def refresh_token(self, long_lived_token: str) -> Tuple[str, datetime]:
        params = {
            "grant_type": "fb_refresh_token",
            "client_id": self._fb_app_id,
            "client_secret": self._fb_app_secret,
            "fb_exchange_token": long_lived_token,
        }
        resp = requests.get(META_OAUTH_ACCESS_TOKEN_URL, params=params, timeout=20)
        data = resp.json()
        if resp.status_code >= 400 or data.get("error"):
            self._raise_for_meta_error(data)
        return data["access_token"], datetime.now(timezone.utc) + timedelta(seconds=int(data["expires_in"]))

    def _raise_for_meta_error(self, data: dict):
        error = data.get("error", {})
        code = error.get("code")
        message = error.get("message", "Unknown Meta error")
        if code == 190:
            raise InstagramReauthRequired(message)
        raise RuntimeError(f"Meta error {code}: {message}")

    # Legacy method compatibility
    def bootstrap_from_env(self):
        pass

    def scheduled_refresh(self, within_days=10):
        # Could iterate all users and refresh if needed
        pass
