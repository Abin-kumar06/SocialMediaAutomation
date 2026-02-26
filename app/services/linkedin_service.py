import logging
import requests
from typing import List, Optional, Dict, Any
from urllib.parse import urlencode, quote
from app.config import settings
from app.models import LinkedInAccount
import threading
import os

logger = logging.getLogger(__name__)

import sqlite3
import threading
from pathlib import Path

class LinkedInStore:
    """Persistent SQLite store for LinkedIn accounts"""
    def __init__(self, db_path: str = "accounts.db"):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self):
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS linkedin_accounts (
                        member_urn TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        access_token TEXT NOT NULL,
                        email TEXT,
                        status TEXT DEFAULT 'active'
                    )
                """)
                conn.commit()

    def add_account(self, account: LinkedInAccount):
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO linkedin_accounts 
                    (member_urn, name, access_token, status) 
                    VALUES (?, ?, ?, ?)
                """, (account.member_urn, account.name, account.access_token, account.status))
                conn.commit()

    def get_account(self, member_urn: str) -> Optional[LinkedInAccount]:
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT member_urn, name, access_token, status FROM linkedin_accounts WHERE member_urn = ?", 
                    (member_urn,)
                )
                row = cursor.fetchone()
                if row:
                    return LinkedInAccount(
                        user_id="default",
                        member_urn=row[0],
                        name=row[1],
                        access_token=row[2],
                        status=row[3]
                    )
                return None

    def get_all_accounts(self) -> List[LinkedInAccount]:
        with self._lock:
            accounts = []
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT member_urn, name, access_token, status FROM linkedin_accounts")
                for row in cursor.fetchall():
                    accounts.append(LinkedInAccount(
                        user_id="default",
                        member_urn=row[0],
                        name=row[1],
                        access_token=row[2],
                        status=row[3]
                    ))
            return accounts

class LinkedInService:
    """Service to handle LinkedIn OAuth and posting"""
    
    def __init__(self, store: Optional[LinkedInStore] = None):
        self.store = store or LinkedInStore()
        self.client_id = settings.LINKEDIN_CLIENT_ID
        self.client_secret = settings.LINKEDIN_CLIENT_SECRET
        self.redirect_uri = settings.LINKEDIN_REDIRECT_URI

    def get_auth_url(self) -> str:
        """Generate LinkedIn OAuth URL"""
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": settings.LINKEDIN_SCOPES,
            "state": "random_string_123" # In production, use a secure CSRF state
        }
        return f"https://www.linkedin.com/oauth/v2/authorization?{urlencode(params)}"

    def exchange_code_for_token(self, code: str) -> str:
        """Exchange auth code for access token"""
        url = "https://www.linkedin.com/oauth/v2/accessToken"
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        print(f"DEBUG: Exchanging code. URL: {url}, Data: {data}")
        response = requests.post(url, data=data)
        print(f"DEBUG: Token Response: {response.status_code} - {response.text}")
        response.raise_for_status()
        return response.json().get("access_token")

    def get_member_profile(self, token: str) -> Dict[str, Any]:
        """Fetch LinkedIn member profile info (URN and name)"""
        # UserInfo endpoint (OpenID Connect)
        url = "https://api.linkedin.com/v2/userinfo"
        headers = {"Authorization": f"Bearer {token}"}
        print(f"DEBUG: Fetching profile. URL: {url}")
        response = requests.get(url, headers=headers)
        print(f"DEBUG: Profile Response: {response.status_code} - {response.text}")
        response.raise_for_status()
        data = response.json()
        
        # Sub is usually the unique ID, but for posting we need the URN format: urn:li:person:XXXX
        member_id = data.get("sub")
        return {
            "member_urn": f"urn:li:person:{member_id}",
            "name": data.get("name", "LinkedIn Member"),
            "email": data.get("email")
        }

    def post_text(self, member_urn: str, text: str, token: str) -> str:
        """Post text to LinkedIn via Share API"""
        url = "https://api.linkedin.com/v2/ugcPosts"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json"
        }
        payload = {
            "author": member_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json().get("id")

    def post_image(self, member_urn: str, text: str, image_path: str, token: str) -> str:
        """Post image to LinkedIn (Register -> Upload -> Create Share)"""
        # 1. Register Upload
        register_url = "https://api.linkedin.com/v2/assets?action=registerUpload"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json"
        }
        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                "owner": member_urn,
                "serviceRelationships": [
                    {
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent"
                    }
                ]
            }
        }
        reg_response = requests.post(register_url, json=register_payload, headers=headers)
        reg_response.raise_for_status()
        reg_data = reg_response.json()
        
        upload_url = reg_data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
        asset_urn = reg_data["value"]["asset"]

        # 2. Upload Binary
        with open(image_path, "rb") as f:
            upload_headers = {"Authorization": f"Bearer {token}"}
            upload_resp = requests.put(upload_url, data=f, headers=upload_headers)
            upload_resp.raise_for_status()

        # 3. Create UGC Post
        post_url = "https://api.linkedin.com/v2/ugcPosts"
        post_payload = {
            "author": member_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text
                    },
                    "shareMediaCategory": "IMAGE",
                    "media": [
                        {
                            "status": "READY",
                            "description": {
                                "text": "Post Image"
                            },
                            "media": asset_urn,
                            "title": {
                                "text": "Image Title"
                            }
                        }
                    ]
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        post_response = requests.post(post_url, json=post_payload, headers=headers)
        post_response.raise_for_status()
        return post_response.json().get("id")
