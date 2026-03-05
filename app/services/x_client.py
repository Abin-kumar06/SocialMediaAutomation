import httpx
import logging
import threading
from typing import Dict, Optional, List
from app.models import XAccount
from app.database import db

logger = logging.getLogger(__name__)

class XStore:
    """Persistent SQLite store for X accounts"""
    def __init__(self):
        # DB handled by app/database.py
        pass

    def add_account(self, account: XAccount):
        logger.info(f"Storing X account for user {account.x_user_id} (@{account.username})")
        with db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO x_accounts 
                (x_user_id, user_id, username, access_token, refresh_token, expires_at, status) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (str(account.x_user_id), account.user_id, account.username, 
                  account.access_token, account.refresh_token, account.expires_at, account.status))
            conn.commit()

    def get_account(self, x_user_id: str, user_id: int) -> Optional[XAccount]:
        with db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM x_accounts WHERE x_user_id = ? AND user_id = ?", 
                (str(x_user_id), user_id)
            )
            row = cursor.fetchone()
            if row:
                return XAccount(**dict(row))
            return None

    def get_all_accounts(self, user_id: int) -> List[XAccount]:
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM x_accounts WHERE user_id = ?", (user_id,))
            return [XAccount(**dict(row)) for row in cursor.fetchall()]

class XClient:
    def __init__(self, store: Optional[XStore] = None):
        self.base_url = "https://api.twitter.com/2"
        self.store = store or XStore()

    async def get_me(self, access_token: str) -> Dict:
        """Fetch the authenticated user's profile information"""
        url = f"{self.base_url}/users/me"
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        params = {
            "user.fields": "id,name,username,profile_image_url"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                return response.json().get("data", {})
            except httpx.HTTPStatusError as e:
                logger.error(f"X API Error (users/me): {e.response.text}")
                raise Exception(f"Failed to fetch X user profile: {e.response.text}")

    async def upload_media(self, access_token: str, file_path: str) -> str:
        """
        Upload media to X using API v1.1 (required for v2 tweets)
        Returns the media_id as a string.
        """
        url = "https://upload.twitter.com/1.1/media/upload.json"
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        # Determine media type
        from pathlib import Path
        import mimetypes
        path = Path(file_path)
        mime_type, _ = mimetypes.guess_type(file_path)
        
        async with httpx.AsyncClient() as client:
            try:
                with open(file_path, "rb") as f:
                    files = {"media": (path.name, f, mime_type or "image/jpeg")}
                    response = await client.post(url, headers=headers, files=files)
                    
                response.raise_for_status()
                return response.json().get("media_id_string")
            except httpx.HTTPStatusError as e:
                logger.error(f"X Media Upload Error: {e.response.text}")
                raise Exception(f"Failed to upload media to X: {e.response.text}")
            except Exception as e:
                logger.error(f"X Media Upload Error: {str(e)}")
                raise

    async def post_tweet(self, access_token: str, text: Optional[str] = None, media_ids: Optional[List[str]] = None) -> Dict:
        """Post a tweet using X API v2"""
        url = f"{self.base_url}/tweets"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {}
        if text:
            payload["text"] = text
        if media_ids:
            payload["media"] = {"media_ids": media_ids}
            
        if not payload:
            raise ValueError("Tweet must have either text or media")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json().get("data", {})
            except httpx.HTTPStatusError as e:
                logger.error(f"X API Error (post tweet): {e.response.text}")
                raise Exception(f"Failed to post tweet: {e.response.text}")


x_client = XClient()
