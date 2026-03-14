"""
Instagram Auto Post API - Main Application
Overhauled for Premium UI & Persistent Scheduling

"""

from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException, BackgroundTasks, File, UploadFile, Form, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict
from datetime import datetime, timezone
import asyncio
import time
import os

from app.models import (
    InstagramPostResponse, HealthCheck, InstagramMultiPostResponse,
    LinkedInPostResponse, LinkedInAccount,
    ScheduledPostResponse, ScheduledJobInfo, ScheduledJobsListResponse,
    User, UserLogin, Token
)
from app.services.auth_service import auth_service
from app.config import settings
from app.services import ImageService, InstagramService
from app.services.openai_service import openai_service
from app.services.linkedin_service import LinkedInService
import app.services.scheduler_service as scheduler_svc
from app.services.instagram_token_service import InstagramTokenService, InstagramReauthRequired
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# Initialize basic services
image_service = ImageService()
instagram_service = InstagramService()
linkedin_service = LinkedInService()
token_service = InstagramTokenService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """ Startup/shutdown hooks: persistent scheduler initialization. """
    # Bootstrap tokens
    try:
        token_service.bootstrap_from_env()
    except Exception as e:
        print(f"⚠ Token bootstrap warning: {e}")

    # APScheduler Setup with SQLite Persistence
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    from apscheduler.jobstores.memory import MemoryJobStore
    from apscheduler.executors.pool import ThreadPoolExecutor

    jobstores = {
        "default": SQLAlchemyJobStore(url="sqlite:///scheduler.db"),
        "memory": MemoryJobStore(),
    }
    executors = {
        "default": ThreadPoolExecutor(max_workers=5)
    }
    scheduler = BackgroundScheduler(
        jobstores=jobstores,
        executors=executors,
        timezone="UTC",
        job_defaults={"misfire_grace_time": 300}
    )
    
    # Token refresh (memory-based)
    scheduler.add_job(
        token_service.scheduled_refresh,
        trigger="interval",
        days=1,
        kwargs={"within_days": 10},
        id="instagram_token_daily_refresh",
        jobstore="memory",
        replace_existing=True,
    )
    
    scheduler.start()
    app.state.scheduler = scheduler
    yield
    scheduler.shutdown(wait=False)

app = FastAPI(
    title="SocialMediaAutomation Elite",
    description="Premium Social Media Management Engine",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return RedirectResponse(url="/static/landing.html")

# ---------------------------------------------------------------------------
# Authentication & User Profile
# ---------------------------------------------------------------------------

@app.post("/api/auth/signup", response_model=User)
async def signup(user: User):
    db_user = await auth_service.get_user_by_email(user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return await auth_service.create_user(user)

@app.post("/api/auth/login", response_model=Token)
async def login(user_data: UserLogin):
    user = await auth_service.get_user_by_email(user_data.email)
    if not user or not auth_service.verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    access_token = auth_service.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/auth/me", response_model=User)
async def get_me(current_user: User = Depends(auth_service.get_current_user)):
    return current_user

# ---------------------------------------------------------------------------
# AI Magic & Core Engine Utilities
# ---------------------------------------------------------------------------

@app.post("/api/ai/analyze-image")
async def analyze_image(
    file: UploadFile = File(...),
    current_user: User = Depends(auth_service.get_current_user)
):
    """Visual Analysis & Caption Generation"""
    file_path = None
    try:
        file_path = await image_service.save_upload(file)
        results = await openai_service.generate_multi_captions(
            image_path=str(file_path)
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if file_path: image_service.cleanup_file(file_path)

@app.get("/api/jobs")
async def list_jobs(current_user: User = Depends(auth_service.get_current_user)):
    """Retrieve all missions (scheduled, published, failed)"""
    return scheduler_svc.list_jobs(current_user.id)

@app.get("/api/user/stats")
async def get_user_stats(current_user: User = Depends(auth_service.get_current_user)):
    """Aggregate mission metrics for the USER DASHBOARD"""
    return scheduler_svc.get_stats(current_user.id)

@app.delete("/api/jobs/{job_id}")
async def cancel_job(job_id: str, current_user: User = Depends(auth_service.get_current_user)):
    """Abort a MISSION-IN-PROGRESS"""
    success = scheduler_svc.cancel_job(app.state.scheduler, job_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Mission not found or already executed.")
    return {"success": True, "message": "Mission aborted successfully."}

# ---------------------------------------------------------------------------
# Platform Account Connections
# ---------------------------------------------------------------------------

@app.get("/api/platforms/instagram/account")
async def get_insta_acc(current_user: User = Depends(auth_service.get_current_user)):
    record = token_service.get_record(current_user.id)
    if not record or record.get('status') != 'active':
        return {"connected": False}
    return {"connected": True, "username": record.get("username"), "id": record.get("instagram_account_id")}

@app.post("/auth/instagram/exchange-token")
async def exchange_insta_token(short_lived_token: str = Form(...), current_user: User = Depends(auth_service.get_current_user)):
    long_token, expires_at = token_service.exchange_short_lived_token(short_lived_token)
    acc_info = token_service.fetch_account_info_from_token(long_token)
    token_service.store_long_lived_token(current_user.id, long_token, expires_at, acc_info.get("instagram_account_id"), acc_info.get("username"))
    return {"success": True, "account": acc_info}

@app.get("/api/platforms/linkedin/accounts")
async def list_linkedin_acc(current_user: User = Depends(auth_service.get_current_user)):
    return linkedin_service.store.get_all_accounts(current_user.id)

@app.get("/api/platforms/linkedin/connect")
async def linkedin_connect(current_user: User = Depends(auth_service.get_current_user)):
    return RedirectResponse(linkedin_service.get_auth_url(current_user.id))

@app.get("/api/platforms/linkedin/callback")
async def linkedin_callback(code: str = None, state: str = None):
    try:
        user_id = linkedin_service.get_user_id_from_state(state)
        access_token = linkedin_service.exchange_code_for_token(code)
        profile = linkedin_service.get_member_profile(access_token)
        account = LinkedInAccount(
            user_id=user_id, 
            member_urn=profile["member_urn"], 
            access_token=access_token, 
            name=profile.get("name", "LinkedIn Member")
        )
        linkedin_service.store.add_account(account)
        return FileResponse("static/success.html")
    except Exception as e:
        print(f"❌ LinkedIn Callback Error: {e}")
        raise HTTPException(status_code=400, detail=f"LinkedIn Sync Failed: {str(e)}")

        linkedin_service.store.add_account(account)
        return FileResponse("static/success.html")
    except Exception as e:
        print(f"❌ LinkedIn Callback Error: {e}")
        raise HTTPException(status_code=400, detail=f"LinkedIn Sync Failed: {str(e)}")

# ---------------------------------------------------------------------------
# Direct Posting Endpoints
# ---------------------------------------------------------------------------

@app.post("/upload-post")
async def post_insta_direct(
    file: UploadFile = File(None),
    text: str = Form(None),
    current_user: User = Depends(auth_service.get_current_user)
):
    """Direct Instagram Publication"""
    try:
        record = token_service.get_record(current_user.id)
        if not record: raise InstagramReauthRequired("No Instagram connection.")
        page_token = token_service.get_access_token_for_user(current_user.id)
        ig_id = record.get('instagram_account_id')
        
        file_path = await image_service.save_upload(file)
        hosted_url = image_service.upload_to_cloud(file_path)
        
        container_id = instagram_service.create_media_container(hosted_url, text or "", page_token, ig_id)
        time.sleep(3) # Wait for processing
        post_id = instagram_service.publish_media_container(container_id, page_token, ig_id)
        
        image_service.cleanup_file(file_path)
        return {"success": True, "post_id": post_id, "message": "Elite content published to Instagram!"}
    except HTTPException as e:
        raise e
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/platforms/instagram/post-carousel")
async def post_insta_carousel(
    files: List[UploadFile] = File(...),
    text: str = Form(None),
    current_user: User = Depends(auth_service.get_current_user)
):
    """Direct Instagram Carousel Publication"""
    try:
        record = token_service.get_record(current_user.id)
        if not record: raise InstagramReauthRequired("No Instagram connection.")
        page_token = token_service.get_access_token_for_user(current_user.id)
        ig_id = record.get('instagram_account_id')
        
        hosted_urls = await image_service.process_and_host_images(uploads=files)
        
        creation_id = instagram_service.create_carousel_media(hosted_urls, text or "", page_token, ig_id)
        time.sleep(5) # Wait for processing
        post_id = instagram_service.publish_media_container(creation_id, page_token, ig_id)
        
        return {"success": True, "post_id": post_id, "message": "Elite carousel published to Instagram!"}
    except HTTPException as e:
        raise e
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/platforms/linkedin/post")
async def post_li_direct(
    member_urn: str = Form(...),
    text: str = Form(None),
    file: UploadFile = File(None),
    current_user: User = Depends(auth_service.get_current_user)
):
    try:
        account = linkedin_service.store.get_account(member_urn, current_user.id)
        if not account: raise HTTPException(status_code=404, detail="LinkedIn account not found.")
        
        if file:
            file_path = await image_service.save_upload(file)
            post_id = linkedin_service.post_image(member_urn, text or "", str(file_path), account.access_token)
            image_service.cleanup_file(file_path)
        else:
            post_id = linkedin_service.post_text(member_urn, text or "", account.access_token)
            
        return {"success": True, "post_id": post_id, "message": "Elite content published to LinkedIn!"}
    except HTTPException as e:
        raise e
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------------------------------------------------------
# Scheduling Engine (Unified)
# ---------------------------------------------------------------------------

def _parse_scheduled_at(scheduled_at: str) -> datetime:
    try:
        dt = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
    except:
        raise HTTPException(status_code=400, detail="Invalid date format. Use ISO-8601.")
    
    if dt.tzinfo is None:
        from datetime import timedelta
        dt = dt.replace(tzinfo=timezone(timedelta(0))) # Default to UTC if not specified
    
    dt_utc = dt.astimezone(timezone.utc)
    if dt_utc <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Mission must be scheduled for the future.")
    return dt_utc

@app.post("/api/platforms/instagram/schedule-post")
async def schedule_insta(
    scheduled_at: str = Form(...),
    file: UploadFile = File(None),
    text: str = Form(None),
    current_user: User = Depends(auth_service.get_current_user)
):
    run_at = _parse_scheduled_at(scheduled_at)
    file_path = await image_service.save_upload(file)
    hosted_url = image_service.upload_to_cloud(file_path)
    image_service.cleanup_file(file_path)
    
    job_id = scheduler_svc.schedule_instagram_post(app.state.scheduler, run_at, current_user.id, hosted_url, text or "")
    return {"success": True, "job_id": job_id}

@app.post("/api/platforms/instagram/schedule-carousel")
async def schedule_insta_carousel(
    scheduled_at: str = Form(...),
    files: List[UploadFile] = File(...),
    text: str = Form(None),
    current_user: User = Depends(auth_service.get_current_user)
):
    run_at = _parse_scheduled_at(scheduled_at)
    hosted_urls = await image_service.process_and_host_images(uploads=files)
    
    job_id = scheduler_svc.schedule_instagram_carousel(app.state.scheduler, run_at, current_user.id, hosted_urls, text or "")
    return {"success": True, "job_id": job_id}

@app.post("/api/platforms/linkedin/schedule-post")
async def schedule_li(
    scheduled_at: str = Form(...),
    member_urn: str = Form(...),
    file: UploadFile = File(None),
    text: str = Form(None),
    current_user: User = Depends(auth_service.get_current_user)
):
    run_at = _parse_scheduled_at(scheduled_at)
    account = linkedin_service.store.get_account(member_urn, current_user.id)
    if not account: raise HTTPException(status_code=404, detail="LinkedIn account not found.")
    
    saved_path = None
    if file:
        temp_path = await image_service.save_upload(file)
        saved_path = str(temp_path)
    
    job_id = scheduler_svc.schedule_linkedin_post(app.state.scheduler, run_at, current_user.id, member_urn, account.access_token, text or "", saved_path)
    return {"success": True, "job_id": job_id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
