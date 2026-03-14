import logging
import requests
from typing import List, Optional, Dict, Any
from urllib.parse import urlencode, quote
from app.config import settings
from app.models import LinkedInAccount
import threading
import os

logger = logging.getLogger(__name__)

from app.database import db
import time
import base64

# Temporary in-memory storage for LinkedIn state
# state -> {user_id: int, expires_at: float}
_linkedin_sessions: Dict[str, Dict[str, Any]] = {}

class LinkedInStore:
    """Persistent SQLite store for LinkedIn accounts"""
    def __init__(self, db_path: str = "accounts.db"):
        self.db_path = db_path
        self._lock = threading.RLock()
        self._init_db()

    def _init_db(self):
        # Already handled by app/database.py
        pass

    def add_account(self, account: LinkedInAccount):
        with db.get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO linkedin_accounts 
                (member_urn, user_id, name, access_token, status) 
                VALUES (?, ?, ?, ?, ?)
            """, (account.member_urn, account.user_id, account.name, account.access_token, account.status))
            conn.commit()

    def get_account(self, member_urn: str, user_id: int) -> Optional[LinkedInAccount]:
        with db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT member_urn, user_id, name, access_token, status FROM linkedin_accounts WHERE member_urn = ? AND user_id = ?", 
                (member_urn, user_id)
            )
            row = cursor.fetchone()
            if row:
                return LinkedInAccount(
                    user_id=row['user_id'],
                    member_urn=row['member_urn'],
                    name=row['name'],
                    access_token=row['access_token'],
                    status=row['status']
                )
            return None

    def get_all_accounts(self, user_id: int) -> List[LinkedInAccount]:
        with db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT member_urn, user_id, name, access_token, status FROM linkedin_accounts WHERE user_id = ?",
                (user_id,)
            )
            return [LinkedInAccount(**dict(row)) for row in cursor.fetchall()]

class LinkedInService:
    """Service to handle LinkedIn OAuth and posting"""
    
    def __init__(self, store: Optional[LinkedInStore] = None):
        self.store = store or LinkedInStore()
        self.client_id = settings.LINKEDIN_CLIENT_ID
        self.client_secret = settings.LINKEDIN_CLIENT_SECRET
        self.redirect_uri = settings.LINKEDIN_REDIRECT_URI

    def get_auth_url(self, user_id: int) -> str:
        """Generate LinkedIn OAuth URL with user_id linked state"""
        state = base64.urlsafe_b64encode(os.urandom(16)).decode('utf8').rstrip('=')
        
        _linkedin_sessions[state] = {
            "user_id": user_id,
            "expires_at": time.time() + 600
        }

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": settings.LINKEDIN_SCOPES,
            "state": state
        }
        return f"https://www.linkedin.com/oauth/v2/authorization?{urlencode(params)}"

    def get_user_id_from_state(self, state: str) -> int:
        """Retrieve and validate user_id from state session"""
        session = _linkedin_sessions.pop(state, None)
        if not session or time.time() > session["expires_at"]:
            raise ValueError("Invalid or expired LinkedIn OAuth session")
        return session["user_id"]

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

        # Small delay to ensure LinkedIn processes the asset before we use it in a share
        time.sleep(2)

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
