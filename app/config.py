"""
Configuration settings
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load from project root .env (same folder as main.py)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=True)


def update_env_token(key: str, value: str) -> bool:
    """
    Update or add a key=value line in the project's .env file.
    Returns True if the file was updated successfully.
    """
    env_path = _PROJECT_ROOT / ".env"
    try:
        lines = []
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8", errors="replace").splitlines()
        key_prefix = f"{key}="
        new_line = f'{key}="{value}"' if (" " in value or "#" in value or "\n" in value) else f"{key}={value}"
        found = False
        for i, line in enumerate(lines):
            if line.strip().startswith(key_prefix) or (line.strip() and line.split("=", 1)[0].strip() == key):
                lines[i] = new_line
                found = True
                break
        if not found:
            lines.append(new_line)
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


class Settings:
    """Application settings"""
    
    # Instagram API
    INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "")
    PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
    GRAPH_API_VERSION = os.getenv("GRAPH_API_VERSION", "v24.0")
    GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
    
    # Facebook App Credentials (for token refresh)
    FB_APP_ID = os.getenv("FB_APP_ID", "")
    FB_APP_SECRET = os.getenv("FB_APP_SECRET", "")
    
    # Image Hosting
    
    # Image Hosting
    IMGBB_API_KEY = os.getenv("IMGBB_API_KEY", "")
    IMGUR_CLIENT_ID = os.getenv("IMGUR_CLIENT_ID", "")
    
    # OpenAI AI Content Generation
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

    # Catbox.moe (Public image hosting)
    CATBOX_USER_HASH = os.getenv("CATBOX_USER_HASH", "")
    
    # File Upload
    UPLOAD_DIR = Path("./uploads")
    MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
    MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024
    ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
    
    # LinkedIn API (for future posting)
    LINKEDIN_CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID", "")
    LINKEDIN_CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")
    LINKEDIN_ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
    LINKEDIN_REDIRECT_URI = os.getenv("LINKEDIN_REDIRECT_URI", "http://localhost:8000/api/platforms/linkedin/callback")
    LINKEDIN_SCOPES = "w_member_social,openid,profile,email"
    
    # X (Twitter) API
    X_CLIENT_ID = os.getenv("X_CLIENT_ID", "")
    X_CLIENT_SECRET = os.getenv("X_CLIENT_SECRET", "")
    X_REDIRECT_URI = os.getenv("X_REDIRECT_URI", "http://localhost:8000/api/platforms/x/callback")
    X_SCOPES = os.getenv("X_SCOPES", "tweet.read tweet.write users.read offline.access")
    
    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))
    
    def __init__(self):
        # Create upload directory
        self.UPLOAD_DIR.mkdir(exist_ok=True)
    
    def get_config_status(self) -> dict:
        """Check configuration status"""
        return {
            "access_token_configured": bool(self.PAGE_ACCESS_TOKEN),
            "instagram_account_configured": bool(self.INSTAGRAM_ACCOUNT_ID),
            "fb_app_credentials_configured": bool(self.FB_APP_ID and self.FB_APP_SECRET),
            "openai_configured": bool(self.OPENAI_API_KEY),
            "catbox_configured": True,  # Standard use doesn't require hash
            "hosting_available": bool(self.IMGBB_API_KEY or self.IMGUR_CLIENT_ID or True),
            "linkedin_configured": bool(self.LINKEDIN_CLIENT_ID and self.LINKEDIN_CLIENT_SECRET and self.LINKEDIN_REDIRECT_URI),
            "linkedin_token_configured": bool(self.LINKEDIN_ACCESS_TOKEN or os.getenv("LINKEDIN_ACCESS_TOKEN")),
            "x_configured": bool(self.X_CLIENT_ID and self.X_CLIENT_SECRET and self.X_REDIRECT_URI),
        }


settings = Settings()