import hashlib
import base64
import os
import time
import httpx
import logging
import urllib.parse
from typing import Dict, Optional, Tuple
from app.config import settings

logger = logging.getLogger(__name__)

# Temporary in-memory storage for MVP
# state -> {code_verifier: str, expires_at: float}
_oauth_sessions: Dict[str, Dict[str, any]] = {}

class XOAuthService:
    @staticmethod
    def generate_pkce() -> Tuple[str, str]:
        """Generate code_verifier and code_challenge (S256)"""
        # Code verifier: random string of 43-128 characters
        code_verifier = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8').rstrip('=')
        
        # Code challenge: SHA256 hash of code_verifier, base64url encoded
        sha256_hash = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(sha256_hash).decode('utf-8').rstrip('=')
        
        return code_verifier, code_challenge

    @staticmethod
    def generate_state() -> str:
        """Generate a random state string"""
        return base64.urlsafe_b64encode(os.urandom(16)).decode('utf-8').rstrip('=')

    def get_authorization_url(self) -> str:
        """Generate the X OAuth 2.0 authorization URL"""
        state = self.generate_state()
        code_verifier, code_challenge = self.generate_pkce()
        
        # Store for later validation
        _oauth_sessions[state] = {
            "code_verifier": code_verifier,
            "expires_at": time.time() + 600 # 10 minutes expiry
        }
        
        params = {
            "response_type": "code",
            "client_id": settings.X_CLIENT_ID,
            "redirect_uri": settings.X_REDIRECT_URI,
            "scope": settings.X_SCOPES,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256"
        }
        
        query_string = "&".join([f"{k}={urllib.parse.quote(v)}" for k, v in params.items()])
        return f"https://twitter.com/i/oauth2/authorize?{query_string}"

    async def exchange_code(self, code: str, state: str) -> Dict:
        """Exchange authorization code for access tokens"""
        session = _oauth_sessions.pop(state, None)
        if not session:
            raise ValueError("Invalid or expired state")
        
        if time.time() > session["expires_at"]:
            raise ValueError("OAuth session expired")

        code_verifier = session["code_verifier"]
        
        url = "https://api.twitter.com/2/oauth2/token"
        data = {
            "code": code,
            "grant_type": "authorization_code",
            "client_id": settings.X_CLIENT_ID,
            "redirect_uri": settings.X_REDIRECT_URI,
            "code_verifier": code_verifier
        }
        
        # Twitter OAuth 2.0 with Confidential Client (needs Basic Auth or credentials in body)
        # Using Client Credentials in body with Basic Auth is common for X
        auth = httpx.BasicAuth(settings.X_CLIENT_ID, settings.X_CLIENT_SECRET)
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, data=data, auth=auth)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"X Token Exchange Error: {e.response.text}")
                raise Exception(f"Failed to exchange X code: {e.response.text}")

x_oauth_service = XOAuthService()
