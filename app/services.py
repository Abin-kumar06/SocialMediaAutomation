"""
Business logic services
"""
from fastapi import HTTPException, UploadFile
from typing import List, Optional
import json
import requests
import aiofiles
import uuid
import os
import re
from pathlib import Path
from app.config import settings, update_env_token
from PIL import Image
from io import BytesIO


class ImageService:
    """Handle image upload and hosting"""
    
    # Instagram aspect ratio requirements
    VALID_ASPECT_RATIOS = {
        'square': {'ratio': 1.0, 'name': 'Square (1:1)', 'target_width': 1080, 'target_height': 1080},
        'portrait': {'ratio': 0.8, 'name': 'Portrait (4:5)', 'target_width': 1080, 'target_height': 1350},
        'landscape': {'ratio': 1.91, 'name': 'Landscape (1.91:1)', 'target_width': 1080, 'target_height': 566}
    }
    
    def get_closest_aspect_ratio(self, width: int, height: int) -> str:
        """Determine which aspect ratio the image is closest to"""
        aspect_ratio = width / height if height > 0 else 0
        
        closest_ratio = 'square'
        min_diff = float('inf')
        
        for ratio_key, ratio_info in self.VALID_ASPECT_RATIOS.items():
            diff = abs(aspect_ratio - ratio_info['ratio'])
            if diff < min_diff:
                min_diff = diff
                closest_ratio = ratio_key
        
        return closest_ratio
    
    def resize_image_to_aspect_ratio(self, image: Image.Image, target_ratio: str) -> Image.Image:
        """Resize image to match target aspect ratio"""
        ratio_info = self.VALID_ASPECT_RATIOS[target_ratio]
        target_width = ratio_info['target_width']
        target_height = ratio_info['target_height']
        target_aspect = ratio_info['ratio']
        
        current_width, current_height = image.size
        current_aspect = current_width / current_height if current_height > 0 else 0
        
        # Determine crop dimensions to match aspect ratio
        if current_aspect > target_aspect:
            # Image is wider - crop from sides
            new_width = int(current_height * target_aspect)
            new_height = current_height
            left = (current_width - new_width) // 2
            top = 0
        else:
            # Image is taller - crop from top/bottom
            new_width = current_width
            new_height = int(current_width / target_aspect)
            left = 0
            top = (current_height - new_height) // 2
        
        # Crop to correct aspect ratio
        right = left + new_width
        bottom = top + new_height
        image = image.crop((left, top, right, bottom))
        
        # Resize to target dimensions
        image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        return image
    
    async def save_upload(self, upload_file: UploadFile) -> Path:
        """Save uploaded file to disk"""
        # Validate file extension
        file_ext = Path(upload_file.filename).suffix.lower()
        if file_ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )
        
        # Read file content
        content = await upload_file.read()
        
        # Check file size
        if len(content) > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Max: {settings.MAX_FILE_SIZE_MB}MB"
            )
        
        return await self.process_and_save_image(content)

    async def process_image_from_url(self, image_url: str) -> Path:
        """Download and process image from a URL"""
        try:
            response = requests.get(image_url, timeout=30)
            response.raise_for_status()
            content = response.content
            
            # Basic size check
            if len(content) > settings.MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"Image from URL is too large. Max: {settings.MAX_FILE_SIZE_MB}MB"
                )
            
            return await self.process_and_save_image(content)
            
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to download image from URL: {str(e)}"
            )

    async def process_and_save_image(self, content: bytes) -> Path:
        """Core image processing and saving logic"""
        # Load and process image
        try:
            image = Image.open(BytesIO(content))
            
            # Convert to RGB if necessary
            if image.mode in ('RGBA', 'LA', 'P'):
                rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                mask = image.split()[-1] if image.mode == 'RGBA' else None
                rgb_image.paste(image, mask=mask)
                image = rgb_image
            
            # Get original dimensions
            original_width, original_height = image.size
            
            # Find closest aspect ratio
            target_ratio = self.get_closest_aspect_ratio(original_width, original_height)
            
            # Resize image to match aspect ratio
            image = self.resize_image_to_aspect_ratio(image, target_ratio)
            
            # Convert image back to bytes
            img_byte_arr = BytesIO()
            image.save(img_byte_arr, format='JPEG', quality=95)
            content = img_byte_arr.getvalue()
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid image content: {str(e)}"
            )
        
        # Generate unique filename
        unique_filename = f"{uuid.uuid4()}.jpg"
        file_path = settings.UPLOAD_DIR / unique_filename
        
        # Save file
        async with aiofiles.open(file_path, 'wb') as out_file:
            await out_file.write(content)
        
        return file_path

    async def process_and_host_images(self, uploads: List[UploadFile] = None, image_urls: List[str] = None) -> List[str]:
        """Process multiple uploaded files or remote image URLs, upload them and return hosted URLs."""
        file_paths: List[Path] = []
        try:
            if uploads:
                for upload in uploads:
                    p = await self.save_upload(upload)
                    file_paths.append(p)

            if image_urls:
                for img_url in image_urls:
                    p = await self.process_image_from_url(img_url)
                    file_paths.append(p)

            hosted_urls: List[str] = []
            for p in file_paths:
                hosted_urls.append(self.upload_to_cloud(p))

            return hosted_urls
        finally:
            for p in file_paths:
                try:
                    self.cleanup_file(p)
                except Exception:
                    pass
    
    def upload_to_imgbb(self, file_path: Path) -> str:
        """Upload to ImgBB"""
        if not settings.IMGBB_API_KEY:
            raise HTTPException(
                status_code=500,
                detail="ImgBB API key not configured"
            )
        
        url = "https://api.imgbb.com/1/upload"
        
        with open(file_path, "rb") as file:
            payload = {"key": settings.IMGBB_API_KEY}
            files = {"image": file}
            
            try:
                response = requests.post(url, data=payload, files=files, timeout=30)
                response.raise_for_status()
                result = response.json()
                
                if result.get("success"):
                    return result["data"]["url"]
                else:
                    raise HTTPException(
                        status_code=500,
                        detail=f"ImgBB upload failed: {result.get('error', {}).get('message', 'Unknown error')}"
                    )
            except requests.exceptions.RequestException as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to upload to ImgBB: {str(e)}"
                )
    
    def upload_to_imgur(self, file_path: Path) -> str:
        """Upload to Imgur"""
        if not settings.IMGUR_CLIENT_ID:
            raise HTTPException(
                status_code=500,
                detail="Imgur client ID not configured"
            )
        
        url = "https://api.imgur.com/3/image"
        headers = {"Authorization": f"Client-ID {settings.IMGUR_CLIENT_ID}"}
        
        with open(file_path, "rb") as file:
            files = {"image": file}
            
            try:
                response = requests.post(url, headers=headers, files=files, timeout=30)
                response.raise_for_status()
                result = response.json()
                
                if result.get("success"):
                    return result["data"]["link"]
                else:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Imgur upload failed"
                    )
            except requests.exceptions.RequestException as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to upload to Imgur: {str(e)}"
                )
    
    def upload_to_catbox(self, file_path: Path) -> str:
        """Upload to Catbox.moe (reliable for Instagram)"""
        url = "https://catbox.moe/user/api.php"
        
        try:
            with open(file_path, "rb") as file:
                files = {"fileToUpload": file}
                data = {"reqtype": "fileupload"}
                if settings.CATBOX_USER_HASH:
                    data["userhash"] = settings.CATBOX_USER_HASH
                
                response = requests.post(url, data=data, files=files, timeout=30)
                response.raise_for_status()
                
                direct_url = response.text.strip()
                if direct_url.startswith("http"):
                    return direct_url
                else:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Catbox upload failed: {direct_url}"
                    )
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload to Catbox: {str(e)}"
            )

    def upload_to_cloud(self, file_path: Path) -> str:
        """Upload to configured cloud service. Prioritizes Catbox as ImgBB is often blocked by Meta."""
        # Try Catbox first as it's currently the most reliable for Instagram
        try:
            return self.upload_to_catbox(file_path)
        except Exception as e:
            print(f"⚠ Catbox upload failed, falling back: {e}")
            
        if settings.IMGBB_API_KEY:
            return self.upload_to_imgbb(file_path)
        elif settings.IMGUR_CLIENT_ID:
            return self.upload_to_imgur(file_path)
        else:
            raise HTTPException(
                status_code=500,
                detail="No image hosting service configured"
            )
    
    def cleanup_file(self, file_path: Path):
        """Delete temporary file"""
        try:
            if file_path.exists():
                os.remove(file_path)
        except Exception as e:
            print(f"Warning: Failed to delete {file_path}: {e}")
    
    def cleanup_all_uploads(self) -> dict:
        """Delete all files in uploads directory"""
        try:
            deleted_count = 0
            for file_path in settings.UPLOAD_DIR.glob("*"):
                if file_path.is_file():
                    os.remove(file_path)
                    deleted_count += 1
            
            return {
                "success": True,
                "message": f"Deleted {deleted_count} files",
                "deleted_count": deleted_count
            }
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Cleanup failed: {str(e)}"
            )


class InstagramService:
    """Handle Instagram API operations"""
    
    def create_media_container(self, image_url: str, caption: str, access_token: str, instagram_account_id: Optional[str] = None) -> str:
        """Create Instagram media container"""
        target_account_id = instagram_account_id or settings.INSTAGRAM_ACCOUNT_ID
        url = f"{settings.GRAPH_API_BASE}/{target_account_id}/media"
        payload = {
            'image_url': image_url,
            'caption': caption,
            'access_token': access_token
        }
        
        try:
            response = requests.post(url, data=payload, timeout=30)
            
            # Get the response body for better error messages
            result = response.json()
            
            # Check if there's an error in the response
            if 'error' in result:
                error_msg = result['error'].get('message', 'Unknown error')
                error_code = result['error'].get('code', 'N/A')
                error_subcode = result['error'].get('error_subcode', 'N/A')
                
                raise HTTPException(
                    status_code=400,
                    detail=f"Instagram API Error: {error_msg} (Code: {error_code}, Subcode: {error_subcode})"
                )
            
            response.raise_for_status()
            return result['id']
            
        except HTTPException:
            raise
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create container: {str(e)}"
            )

    def create_carousel_media(self, image_urls: List[str], caption: str, access_token: str, instagram_account_id: Optional[str] = None) -> str:
        """Create a carousel (multi-photo) media container."""
        target_account_id = instagram_account_id or settings.INSTAGRAM_ACCOUNT_ID
        child_ids: List[str] = []

        # Create child containers
        for img_url in image_urls:
            url = f"{settings.GRAPH_API_BASE}/{target_account_id}/media"
            payload = {
                'image_url': img_url,
                'access_token': access_token
            }

            try:
                resp = requests.post(url, data=payload, timeout=30)
                result = resp.json()
                if 'error' in result:
                    error_msg = result['error'].get('message', 'Unknown error')
                    raise HTTPException(
                        status_code=400,
                        detail=f"Instagram API Error (child): {error_msg}"
                    )
                resp.raise_for_status()
                child_ids.append(result['id'])
            except HTTPException:
                raise
            except requests.exceptions.RequestException as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to create child media: {str(e)}"
                )

        # Create album/container with children. Instagram expects children as separate indexed parameters.
        album_url = f"{settings.GRAPH_API_BASE}/{settings.INSTAGRAM_ACCOUNT_ID}/media"
        album_payload = {
            'caption': caption,
            'media_type': 'CAROUSEL',
            'access_token': access_token
        }
        
        # Add children as indexed parameters (children[0], children[1], etc.)
        for idx, child_id in enumerate(child_ids):
            album_payload[f'children[{idx}]'] = child_id

        try:
            album_resp = requests.post(f"{settings.GRAPH_API_BASE}/{target_account_id}/media", data=album_payload, timeout=30)
            album_result = album_resp.json()
            if 'error' in album_result:
                raise HTTPException(
                    status_code=400,
                    detail=f"Instagram API Error (album): {album_result['error'].get('message', 'Unknown error')}"
                )
            album_resp.raise_for_status()
            return album_result['id']
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to create album container: {str(e)}"
            )
    
    def publish_media_container(self, creation_id: str, access_token: str, instagram_account_id: Optional[str] = None) -> str:
        """Publish Instagram media container"""
        target_account_id = instagram_account_id or settings.INSTAGRAM_ACCOUNT_ID
        url = f"{settings.GRAPH_API_BASE}/{target_account_id}/media_publish"
        payload = {
            'creation_id': creation_id,
            'access_token': access_token
        }
        
        try:
            response = requests.post(url, data=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if 'error' in result:
                raise HTTPException(
                    status_code=400,
                    detail=f"Instagram API Error: {result['error']['message']}"
                )
            
            return result['id']
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to publish: {str(e)}"
            )
    
    def check_container_status(self, creation_id: str, access_token: str) -> dict:
        """Check container status"""
        url = f"{settings.GRAPH_API_BASE}/{creation_id}"
        params = {
            'fields': 'status_code,status',
            'access_token': access_token
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to check status: {str(e)}"
            )
    
    def get_account_info(self, access_token: str, instagram_account_id: Optional[str] = None) -> dict:
        """Get Instagram account info"""
        target_account_id = instagram_account_id or settings.INSTAGRAM_ACCOUNT_ID
        url = f"{settings.GRAPH_API_BASE}/{target_account_id}"
        params = {
            'fields': 'id,username,name,profile_picture_url,followers_count,follows_count,media_count',
            'access_token': access_token
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to fetch account info: {str(e)}"
            )

    def check_token_status(self) -> dict:
        """Check if the current access token is valid or expired"""
        url = f"{settings.GRAPH_API_BASE}/me"
        params = {
            'fields': 'id,name',
            'access_token': settings.PAGE_ACCESS_TOKEN
        }
        
        try:
            response = requests.get(url, params=params, timeout=15)
            result = response.json()
            
            if 'error' in result:
                error = result['error']
                return {
                    "valid": False,
                    "expired": error.get('error_subcode') == 463 or "expired" in error.get('message', '').lower(),
                    "message": error.get('message'),
                    "code": error.get('code'),
                    "subcode": error.get('error_subcode')
                }
            
            return {
                "valid": True,
                "expired": False,
                "message": "Token is active and valid",
                "user_id": result.get('id'),
                "name": result.get('name')
            }
        except Exception as e:
            return {
                "valid": False,
                "expired": False,
                "message": f"Connection error: {str(e)}"
            }

    def refresh_access_token(self) -> dict:
        """
        Attempt to refresh/extend the access token.
        Note: This requires FB_APP_ID and FB_APP_SECRET.
        """
        if not settings.FB_APP_ID or not settings.FB_APP_SECRET:
            return {
                "success": False,
                "message": "Cannot refresh token: FB_APP_ID or FB_APP_SECRET not configured. Please manually update PAGE_ACCESS_TOKEN in .env"
            }
        
        url = f"{settings.GRAPH_API_BASE}/oauth/access_token"
        params = {
            'grant_type': 'fb_exchange_token',
            'client_id': settings.FB_APP_ID,
            'client_secret': settings.FB_APP_SECRET,
            'fb_exchange_token': settings.PAGE_ACCESS_TOKEN
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            result = response.json()
            
            if 'error' in result:
                return {
                    "success": False,
                    "message": f"Refresh failed: {result['error'].get('message')}"
                }
            
            new_token = result.get('access_token')
            if new_token:
                # Persist to .env so it survives restarts and stays in sync
                persisted = update_env_token("PAGE_ACCESS_TOKEN", new_token)
                return {
                    "success": True,
                    "message": "Token extended successfully." + (" Saved to .env." if persisted else " Please update .env manually with the new token."),
                    "new_token": new_token,
                    "expires_in": result.get('expires_in'),
                    "saved_to_env": persisted,
                }
            
            return {"success": False, "message": "Failed to retrieve new token from response"}
            
        except Exception as e:
            return {"success": False, "message": f"Request failed: {str(e)}"}
    
    def ensure_valid_token(self) -> bool:
        """
        Automatically check if token is valid, and refresh if needed.
        Updates settings.PAGE_ACCESS_TOKEN with the new token.
        Returns True if token is now valid, False otherwise.
        """
        # Check if current token is valid
        token_status = self.check_token_status()
        
        if token_status.get('valid'):
            print("✓ Token is active and valid")
            return True
        
        print("⚠ Token is expired or invalid. Attempting to refresh...")
        
        # Try to refresh token if it's not valid
        refresh_result = self.refresh_access_token()
        
        if refresh_result.get('success') and refresh_result.get('new_token'):
            new_token = refresh_result['new_token']
            # Update the token in settings (and already persisted to .env by refresh_access_token)
            settings.PAGE_ACCESS_TOKEN = new_token
            if refresh_result.get('saved_to_env'):
                print("✓ Token refreshed and saved to .env")
            else:
                print("✓ Token refreshed; update .env manually with the new token")
            
            # Verify the new token works
            new_token_status = self.check_token_status()
            return new_token_status.get('valid', False)
        else:
            error_msg = refresh_result.get('message', 'Unknown error')
            print(f"✗ Failed to refresh token: {error_msg}")
            return False



