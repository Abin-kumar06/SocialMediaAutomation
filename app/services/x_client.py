import httpx
import logging
import threading
import json
import os
from pathlib import Path
from typing import Dict, Optional, List
from app.models import XAccount

logger = logging.getLogger(__name__)

class XStore:
    """Persistent JSON store for X accounts"""
    def __init__(self, storage_path: Optional[str] = None):
        if storage_path:
            self.storage_path = Path(storage_path)
        else:
            # Absolute path to the app directory
            app_dir = Path(__file__).resolve().parent.parent
            self.storage_path = app_dir / "x_accounts.json"
            
        # Ensure parent directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"DEBUG: X storage path: {self.storage_path.absolute()}")
        
        self._accounts: Dict[str, XAccount] = {}
        self._lock = threading.RLock()
        self._load()

    def _load(self):
        """Load accounts from JSON file"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r") as f:
                    data = json.load(f)
                    for x_id, acc_data in data.items():
                        self._accounts[str(x_id)] = XAccount(**acc_data)
                logger.info(f"Loaded {len(self._accounts)} accounts from {self.storage_path}")
            except Exception as e:
                logger.error(f"Failed to load X accounts: {e}")

    def _save(self):
        """Save accounts to JSON file"""
        try:
            with open(self.storage_path, "w") as f:
                data = {x_id: acc.dict() for x_id, acc in self._accounts.items()}
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(self._accounts)} accounts to {self.storage_path}")
        except Exception as e:
            logger.error(f"Failed to save X accounts: {e}")

    def add_account(self, account: XAccount):
        with self._lock:
            x_id = str(account.x_user_id)
            logger.info(f"Storing X account for user {x_id} (@{account.username})")
            self._accounts[x_id] = account
            self._save()

    def get_account(self, x_user_id: str) -> Optional[XAccount]:
        with self._lock:
            search_id = str(x_user_id).strip()
            account = self._accounts.get(search_id)
            
            if not account:
                # Truncation check: See if any stored ID starts with the first 15 digits
                # Twitter IDs are usually 19 digits. Truncation often zeros out the last few.
                if len(search_id) >= 15:
                    prefix = search_id[:15]
                    for stored_id, acc in self._accounts.items():
                        if stored_id.startswith(prefix):
                            logger.warning(f"Likely ID truncation detected! Input: {search_id}, Stored: {stored_id}")
                            return acc

            if account:
                logger.info(f"Found X account: {search_id}")
            else:
                logger.warning(f"X account NOT found: '{search_id}'. Stored IDs: {list(self._accounts.keys())}")
            return account

    def get_all_accounts(self) -> List[XAccount]:
        with self._lock:
            return list(self._accounts.values())

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
                # X API v2 returns data wrapped in a 'data' object
                return response.json().get("data", {})
            except httpx.HTTPStatusError as e:
                logger.error(f"X API Error (users/me): {e.response.text}")
                raise Exception(f"Failed to fetch X user profile: {e.response.text}")

    async def post_tweet(self, access_token: str, text: str, media_ids: Optional[list] = None) -> Dict:
        """Post a tweet using X API v2"""
        url = f"{self.base_url}/tweets"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        payload = {"text": text}
        if media_ids:
            payload["media"] = {"media_ids": media_ids}
            
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json().get("data", {})
            except httpx.HTTPStatusError as e:
                logger.error(f"X API Error (post tweet): {e.response.text}")
                raise Exception(f"Failed to post tweet: {e.response.text}")

x_client = XClient()
