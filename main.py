"""
Instagram Auto Post API - Main Application
"""
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException, BackgroundTasks, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from app.models import InstagramPostResponse, HealthCheck, InstagramMultiPostResponse, LinkedInPostResponse, LinkedInAccount
from app.config import settings
from app.services import ImageService, InstagramService
from app.services.ollama_caption_service import OllamaCaptionService
from app.services.linkedin_service import LinkedInService
from app.services.instagram_token_service import InstagramTokenService, InstagramReauthRequired
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import time
from datetime import datetime, timezone


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown hooks: token bootstrap + daily refresh scheduler."""
    # Bootstrap token lifecycle from existing .env token (if present)
    try:
        token_service.bootstrap_from_env()
    except InstagramReauthRequired as e:
        # Don't crash startup; just require re-auth before posting
        print(f"⚠ Instagram token requires re-authentication: {e}")
    except Exception as e:
        print(f"⚠ Instagram token bootstrap failed: {e}")

    # Daily scheduler to refresh tokens expiring soon
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        token_service.scheduled_refresh,
        trigger="interval",
        days=1,
        kwargs={"within_days": 10},
        id="instagram_token_daily_refresh",
        replace_existing=True,
    )
    scheduler.start()
    app.state.scheduler = scheduler
    yield
    try:
        scheduler.shutdown(wait=False)
    except Exception:
        pass


app = FastAPI(
    title="Instagram Auto Post API",
    description="Upload images directly and post to Instagram",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize services
image_service = ImageService()
instagram_service = InstagramService()
ollama_service = OllamaCaptionService()
linkedin_service = LinkedInService()
token_service = InstagramTokenService()


@app.get("/", response_model=HealthCheck)
async def health_check():
    """Health check endpoint"""
    return {
        "status": "online",
        "instagram_account_id": settings.INSTAGRAM_ACCOUNT_ID,
        "api_version": "v22.0",
        "upload_dir": settings.UPLOAD_DIR,
        "config_status": settings.get_config_status()
    }


# LinkedIn Platform Routes

@app.get("/api/platforms/linkedin/connect")
async def linkedin_connect():
    """Redirect to LinkedIn OAuth"""
    return RedirectResponse(linkedin_service.get_auth_url())


@app.get("/api/platforms/linkedin/callback")
async def linkedin_callback(
    code: str = None,
    error: str = None,
    error_description: str = None
):
    """Handle LinkedIn OAuth callback"""
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"LinkedIn OAuth Error: {error} - {error_description}"
        )
    
    if not code:
        raise HTTPException(
            status_code=400,
            detail="Missing 'code' parameter. Did you authorize the app?"
        )

    try:
        # 1. Exchange code for access token
        access_token = linkedin_service.exchange_code_for_token(code)
        
        # 2. Fetch member profile
        profile = linkedin_service.get_member_profile(access_token)
        
        # 3. Store account in-memory
        account = LinkedInAccount(
            user_id="default",
            member_urn=profile["member_urn"],
            access_token=access_token,
            name=profile["name"]
        )
        linkedin_service.store.add_account(account)
            
        return {
            "success": True,
            "message": "Connected to LinkedIn successfully!",
            "account": {
                "urn": account.member_urn,
                "name": account.name
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LinkedIn Connection Error: {str(e)}")


@app.get("/api/platforms/linkedin/accounts", response_model=List[LinkedInAccount])
async def list_linkedin_accounts():
    """List all connected LinkedIn accounts"""
    return linkedin_service.store.get_all_accounts()


@app.post("/api/platforms/linkedin/post", response_model=LinkedInPostResponse)
async def linkedin_post(
    member_urn: str = Form(...),
    text: str = Form(None),
    file: UploadFile = File(None),
    image_url: str = Form(None),
    auto_caption: bool = Form(False),
    prompt: str = Form(None)
):
    """Post text or image to LinkedIn"""
    if not text and not auto_caption:
        raise HTTPException(status_code=400, detail="Provide either text or enable auto_caption")
    
    account = linkedin_service.store.get_account(member_urn)
    if not account:
        raise HTTPException(status_code=404, detail="LinkedIn account not found. Please connect first.")

    final_text = text
    if auto_caption:
        if not prompt:
            raise HTTPException(status_code=400, detail="Prompt required for auto_caption")
        generated = ollama_service.generate_caption(platform="linkedin", topic=prompt)
        final_text = generated.get("full_caption")

    file_path = None
    try:
        if file or image_url:
            # Handle image post
            if file:
                file_path = await image_service.save_upload(file)
                post_id = linkedin_service.post_image(member_urn, final_text, str(file_path), account.access_token)
                image_url_result = None
            else:
                # LinkedIn requires a local file for binary upload, so if we have a URL, we'd need to download it first.
                # For this implementation, we assume file upload is preferred.
                # Simplified: post as text if image_url is provided but downloading not implemented.
                # Alternatively, use ImageService if it has a download feature.
                # Let's keep it simple: support local file upload.
                raise HTTPException(status_code=400, detail="LinkedIn image post requires a file upload in this version")
            
            return LinkedInPostResponse(
                success=True,
                post_id=post_id,
                message="Image post published to LinkedIn!",
                linkedin_post_url=f"https://www.linkedin.com/feed/update/{post_id}",
                uploaded_image_url=image_url_result,
                caption=final_text
            )
        else:
            # Handle text post
            post_id = linkedin_service.post_text(member_urn, final_text, account.access_token)
            return LinkedInPostResponse(
                success=True,
                post_id=post_id,
                message="Text post published to LinkedIn!",
                linkedin_post_url=f"https://www.linkedin.com/feed/update/{post_id}",
                caption=final_text
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if file_path:
            image_service.cleanup_file(file_path)


@app.post("/upload-post", response_model=InstagramPostResponse)
async def create_instagram_post(
    file: UploadFile = File(None, description="Image file (JPG, PNG)"),
    image_url: str = Form(None, description="Direct URL to an image"),
    caption: str = Form(None, description="Post caption"),
    auto_caption: bool = Form(False, description="Generate caption/hashtags automatically"),
    prompt: str = Form(None, description="Prompt/context for caption generation"),
    keywords: str = Form(None, description="Comma-separated keywords"),
    tone: str = Form("", description="Caption tone (e.g., playful, professional)"),
    platform: str = Form("instagram", description="Platform (instagram, linkedin, x)"),
    hashtag_count: int = Form(8, description="Number of hashtags to generate (legacy, Ollama uses platform defaults)")
):
    """
    Upload an image or provide a URL and post to Instagram (Synchronous)
    
    - **file**: Image file (max 10MB)
    - **image_url**: (Alternative) Direct URL to a public image
    - **caption**: Caption text
    """
    if not file and not image_url:
        raise HTTPException(
            status_code=400,
            detail="Either file or image_url must be provided"
        )
    if auto_caption and not prompt:
        raise HTTPException(
            status_code=400,
            detail="When auto_caption=true, a prompt is required to generate the caption"
        )
    if not caption and not auto_caption:
        raise HTTPException(
            status_code=400,
            detail="Provide either caption or enable auto_caption with a prompt"
        )
    if not settings.PAGE_ACCESS_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="Access token not configured"
        )
    
    # Ensure token is fresh before posting (refreshes automatically if expiring soon)
    try:
        token_service.get_access_token_for_posting()
    except InstagramReauthRequired as e:
        raise HTTPException(status_code=401, detail=str(e))
    
    file_path = None
    
    try:
        # Step 1: Save/Download image
        if file:
            file_path = await image_service.save_upload(file)
        else:
            file_path = await image_service.process_image_from_url(image_url)
        
        # Step 2: Upload to image hosting
        image_url = image_service.upload_to_cloud(file_path)
        
        # Default caption to manual input
        final_caption = caption

        if auto_caption:
            # Auto-generation is enabled - generate caption from prompt
            try:
                keyword_list = [k.strip() for k in (keywords or "").split(",") if k.strip()]
                generated = ollama_service.generate_caption(
                    platform=platform,
                    topic=f"{prompt}. Keywords: {', '.join(keyword_list)}" if keyword_list else prompt
                )
                generated_caption = generated.get("full_caption")
                if generated_caption:
                    final_caption = generated_caption
            except Exception as e:
                print(f"⚠ Caption generation failed: {e}")
        
        # If still empty (no manual, no auto-gen result), use default
        if not final_caption:
            final_caption = "Check it out! 📸"

        # Step 4: Create Instagram container
        creation_id = instagram_service.create_media_container(image_url, final_caption)
        
        # Step 5: Wait for processing
        time.sleep(2)
        
        # Step 6: Check status
        status = instagram_service.check_container_status(creation_id)
        if status.get('status_code') == 'ERROR':
            raise HTTPException(
                status_code=400,
                detail=f"Container failed: {status.get('status')}"
            )
        
        # Step 7: Publish
        post_id = instagram_service.publish_media_container(creation_id)
        
        # Cleanup
        image_service.cleanup_file(file_path)
        
        return InstagramPostResponse(
            success=True,
            creation_id=creation_id,
            post_id=post_id,
            message="Post published successfully!",
            instagram_post_url=f"https://www.instagram.com/p/{post_id}/",
            uploaded_image_url=image_url,
            caption=final_caption
        )
        
    except HTTPException:
        if file_path:
            image_service.cleanup_file(file_path)
        raise
    except Exception as e:
        if file_path:
            image_service.cleanup_file(file_path)
        raise HTTPException(
            status_code=500,
            detail=f"Error: {str(e)}"
        )


@app.post("/upload-post-async", response_model=InstagramPostResponse)
async def create_instagram_post_async(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(None),
    image_url: str = Form(None),
    caption: str = Form(None),
    auto_caption: bool = Form(False),
    prompt: str = Form(None),
    keywords: str = Form(None),
    tone: str = Form(""),
    platform: str = Form("instagram"),
    hashtag_count: int = Form(8)
):
    """
    Upload and post asynchronously (publishing in background)
    """
    if not file and not image_url:
        raise HTTPException(status_code=400, detail="Either file or image_url must be provided")
    if auto_caption and not prompt:
        raise HTTPException(
            status_code=400,
            detail="When auto_caption=true, a prompt is required to generate the caption"
        )
    if not caption and not auto_caption:
        raise HTTPException(
            status_code=400,
            detail="Provide either caption or enable auto_caption with a prompt"
        )
    
    if not settings.PAGE_ACCESS_TOKEN:
        raise HTTPException(status_code=500, detail="Access token not configured")
    
    # Ensure token is fresh before posting (refreshes automatically if expiring soon)
    try:
        token_service.get_access_token_for_posting()
    except InstagramReauthRequired as e:
        raise HTTPException(status_code=401, detail=str(e))
    
    try:
        if file:
            file_path = await image_service.save_upload(file)
        else:
            file_path = await image_service.process_image_from_url(image_url)
        
        hosted_image_url = image_service.upload_to_cloud(file_path)

        if auto_caption:
            # Auto-generation is enabled - generate caption from prompt
            try:
                keyword_list = [k.strip() for k in (keywords or "").split(",") if k.strip()]
                generated = ollama_service.generate_caption(
                    platform=platform,
                    topic=f"{prompt}. Keywords: {', '.join(keyword_list)}" if keyword_list else prompt
                )
                final_caption = generated.get("full_caption")
                if not final_caption:
                    # Fallback to manual caption if provided, otherwise default
                    final_caption = caption or "Check it out! 📸"
            except Exception as e:
                print(f"⚠ Caption generation failed: {e}")
                # Fallback to manual caption if provided, otherwise default
                final_caption = caption or "Check it out! 📸"
        elif not final_caption:
            # No auto-caption and no manual caption - use default
            final_caption = "Check it out! 📸"

        creation_id = instagram_service.create_media_container(hosted_image_url, final_caption)
        
        # Use asyncio.sleep to avoid blocking the main thread
        async def publish_in_background():
            await asyncio.sleep(5)
            try:
                instagram_service.publish_media_container(creation_id)
            finally:
                image_service.cleanup_file(file_path)
        
        background_tasks.add_task(publish_in_background)
        
        return InstagramPostResponse(
            success=True,
            creation_id=creation_id,
            post_id=None,
            message="Publishing in background...",
            uploaded_image_url=hosted_image_url,
            caption=final_caption
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload-multi-post", response_model=InstagramMultiPostResponse)
async def create_instagram_multi_post(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(None, description="Multiple image files (JPG, PNG)"),
    image_urls: str = Form(None, description="Comma-separated direct image URLs"),
    caption: str = Form(None, description="Post caption"),
    auto_caption: bool = Form(False, description="Generate caption/hashtags automatically"),
    prompt: str = Form(None, description="Prompt/context for caption generation"),
    keywords: str = Form(None, description="Comma-separated keywords"),
    tone: str = Form("", description="Caption tone (e.g., playful, professional)"),
    platform: str = Form("instagram"),
    hashtag_count: int = Form(8, description="Number of hashtags to generate")
):
    """
    Upload multiple images or provide multiple URLs and post as an Instagram carousel
    """
    if not files and not image_urls:
        raise HTTPException(status_code=400, detail="Either files or image_urls must be provided")
    if auto_caption and not prompt:
        raise HTTPException(
            status_code=400,
            detail="When auto_caption=true, a prompt is required to generate the caption"
        )
    if not caption and not auto_caption:
        raise HTTPException(
            status_code=400,
            detail="Provide either caption or enable auto_caption with a prompt"
        )

    if not settings.PAGE_ACCESS_TOKEN:
        raise HTTPException(status_code=500, detail="Access token not configured")

    # Ensure token is fresh before posting (refreshes automatically if expiring soon)
    try:
        token_service.get_access_token_for_posting()
    except InstagramReauthRequired as e:
        raise HTTPException(status_code=401, detail=str(e))

    file_paths = None
    try:
        # Parse image URLs
        url_list = []
        if image_urls:
            url_list = [u.strip() for u in image_urls.split(',') if u.strip()]

        # Process and host images (uploads + URLs)
        hosted_image_urls = await image_service.process_and_host_images(files, url_list)

        # Generate caption if auto_caption is enabled, otherwise use manual caption
        final_caption = caption
        if auto_caption:
            # Auto-generation is enabled - generate caption from prompt
            try:
                keyword_list = [k.strip() for k in (keywords or "").split(",") if k.strip()]
                generated = ollama_service.generate_caption(
                    platform=platform,
                    topic=f"{prompt}. Keywords: {', '.join(keyword_list)}" if keyword_list else prompt
                )
                final_caption = generated.get("full_caption")
                if not final_caption:
                    # Fallback to manual caption if provided, otherwise default
                    final_caption = caption or "Check it out! 📸"
            except Exception as e:
                print(f"⚠ Caption generation failed: {e}")
                # Fallback to manual caption if provided, otherwise default
                final_caption = caption or "Check it out! 📸"
        elif not final_caption:
            # No auto-caption and no manual caption - use default
            final_caption = "Check it out! 📸"

        # Create carousel container
        creation_id = instagram_service.create_carousel_media(hosted_image_urls, final_caption)

        # Allow processing time
        time.sleep(2)

        # Check status
        status = instagram_service.check_container_status(creation_id)
        if status.get('status_code') == 'ERROR':
            raise HTTPException(status_code=400, detail=f"Container failed: {status.get('status')}")

        # Publish
        post_id = instagram_service.publish_media_container(creation_id)

        return InstagramMultiPostResponse(
            success=True,
            creation_id=creation_id,
            post_id=post_id,
            message="Carousel published successfully!",
            instagram_post_url=f"https://www.instagram.com/p/{post_id}/",
            uploaded_image_urls=hosted_image_urls
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate-caption")
async def generate_caption(
    prompt: str = Form(..., description="Prompt/context for caption generation"),
    keywords: str = Form(None, description="Comma-separated keywords"),
    tone: str = Form("", description="Caption tone"),
    hashtag_count: int = Form(8, description="Number of hashtags to generate"),
    platform: str = Form("instagram", description="Platform (instagram, linkedin, x)")
):
    """Generate caption and hashtags with AI"""
    keyword_list = [k.strip() for k in (keywords or "").split(",") if k.strip()]
    return ollama_service.generate_caption(
        platform=platform,
        topic=f"{prompt}. Keywords: {', '.join(keyword_list)}" if keyword_list else prompt
    )


@app.get("/account-info")
async def get_account_info():
    """Get Instagram account information"""
    if not settings.PAGE_ACCESS_TOKEN:
        raise HTTPException(status_code=500, detail="Access token not configured")
    
    return instagram_service.get_account_info()


@app.get("/token-status")
async def get_token_status():
    """Get current token lifecycle status (local store)."""
    record = token_service.get_record()
    if not record or not record.access_token or record.status != "active":
        return {"valid": False, "status": "needs_reauth", "message": "No active token in store"}

    now = datetime.now(timezone.utc)
    return {
        "valid": record.expires_at > now,
        "status": record.status,
        "expires_at": record.expires_at.isoformat(),
        "expires_in_seconds": int(record.expires_in(now).total_seconds()),
        "last_refreshed_at": record.last_refreshed_at.isoformat(),
    }


@app.get("/refresh-token")
async def refresh_token():
    """Force refresh the current long-lived token (if present)."""
    try:
        record = token_service.force_refresh_now()
        return {
            "success": True,
            "message": "Token refreshed successfully",
            "expires_at": record.expires_at.isoformat(),
            "expires_in_seconds": int(record.expires_in().total_seconds()),
            "last_refreshed_at": record.last_refreshed_at.isoformat(),
            "status": record.status,
        }
    except InstagramReauthRequired as e:
        raise HTTPException(status_code=401, detail=str(e))


@app.post("/auth/instagram/exchange-token")
async def instagram_oauth_callback(
    short_lived_token: str = Form(..., description="Short-lived user access token from OAuth callback"),
):
    """
    Instagram OAuth callback: receive short-lived token → exchange to long-lived → store only long-lived.

    Flow (no token logic in route; all in service):
      1. Exchange short_lived_token via Meta API → (long_token, expires_at).
      2. Store only the long-lived token; short-lived is never stored.
    If the short-lived token is expired (Meta 190), returns 401 and requires re-login.
    """
    try:
        # Step 1: Convert short-lived to long-lived (~60 days); raises if token expired/invalid
        long_token, expires_at = token_service.exchange_short_lived_token(short_lived_token)
        # Step 2: Store ONLY long-lived token (discard short-lived); updates store + .env
        record = token_service.store_long_lived_token(long_token, expires_at)
        return {
            "success": True,
            "status": record.status,
            "expires_at": record.expires_at.isoformat(),
            "expires_in_seconds": int(record.expires_in().total_seconds()),
            "last_refreshed_at": record.last_refreshed_at.isoformat(),
        }
    except InstagramReauthRequired as e:
        raise HTTPException(status_code=401, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/cleanup-uploads")
async def cleanup_uploads():
    """Delete all temporary upload files"""
    return image_service.cleanup_all_uploads()


@app.get("/config-check")
async def config_check():
    """Check configuration status"""
    config = settings.get_config_status()
    
    issues = []
    if not config["access_token_configured"]:
        issues.append("PAGE_ACCESS_TOKEN not set")
    if not config["hosting_available"]:
        issues.append("No image hosting configured")
    
    return {
        "configuration": config,
        "issues": issues,
        "ready": len(issues) == 0
    }


    return results

# Gemini internal check removed as we moved to Ollama locally.


if __name__ == "__main__":
    import uvicorn
    # Configure uvicorn to exclude directories that cause unnecessary reloads
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        reload_excludes=[".venv", "uploads", "*.log", "__pycache__", ".git"]
    )
