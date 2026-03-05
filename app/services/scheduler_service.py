"""
Scheduler Service — wraps APScheduler to manage scheduled social media posts.

Jobs are stored in an in-memory dict keyed by job_id so they can be
listed and cancelled. The scheduler instance is injected from main.py
(app.state.scheduler) so it shares the same BackgroundScheduler that
powers the token-refresh job.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from apscheduler.schedulers.background import BackgroundScheduler


# ---------------------------------------------------------------------------
# In-memory metadata store
# ---------------------------------------------------------------------------

_job_meta: dict[str, dict] = {}  # job_id → metadata dict


def _make_meta(job_id: str, platform: str, scheduled_at: datetime, user_id: int) -> dict:
    return {
        "job_id": job_id,
        "user_id": user_id,
        "platform": platform,
        "scheduled_at": scheduled_at.isoformat(),
        "status": "pending",
    }


# ---------------------------------------------------------------------------
# Job functions (called by APScheduler at run-time)
# ---------------------------------------------------------------------------

def _run_instagram_post(job_id: str, user_id: int, hosted_image_url: str, caption: str):
    """Execute a scheduled Instagram single-image post."""
    from app.services import InstagramService
    _job_meta[job_id]["status"] = "running"
    try:
        from app.services.instagram_token_service import InstagramTokenService
        token_svc = InstagramTokenService()
        access_token = token_svc.get_access_token_for_user(user_id)
        
        svc = InstagramService()
        creation_id = svc.create_media_container(hosted_image_url, caption, access_token)
        import time; time.sleep(2)
        post_id = svc.publish_media_container(creation_id, access_token)
        _job_meta[job_id]["status"] = "published"
        _job_meta[job_id]["post_id"] = post_id
        print(f"✅ Scheduled Instagram post published — post_id={post_id}  job_id={job_id}")
    except Exception as e:
        _job_meta[job_id]["status"] = "failed"
        _job_meta[job_id]["error"] = str(e)
        print(f"❌ Scheduled Instagram post failed — job_id={job_id}  error={e}")


def _run_instagram_carousel(job_id: str, user_id: int, hosted_image_urls: list[str], caption: str):
    """Execute a scheduled Instagram carousel post."""
    from app.services import InstagramService
    _job_meta[job_id]["status"] = "running"
    try:
        from app.services.instagram_token_service import InstagramTokenService
        token_svc = InstagramTokenService()
        access_token = token_svc.get_access_token_for_user(user_id)

        svc = InstagramService()
        creation_id = svc.create_carousel_media(hosted_image_urls, caption, access_token)
        import time; time.sleep(2)
        post_id = svc.publish_media_container(creation_id, access_token)
        _job_meta[job_id]["status"] = "published"
        _job_meta[job_id]["post_id"] = post_id
        print(f"✅ Scheduled Instagram carousel published — post_id={post_id}  job_id={job_id}")
    except Exception as e:
        _job_meta[job_id]["status"] = "failed"
        _job_meta[job_id]["error"] = str(e)
        print(f"❌ Scheduled Instagram carousel failed — job_id={job_id}  error={e}")


def _run_linkedin_post(
    job_id: str,
    member_urn: str,
    access_token: str,
    text: str,
    file_path: Optional[str] = None,
):
    """Execute a scheduled LinkedIn post."""
    from app.services.linkedin_service import LinkedInService
    _job_meta[job_id]["status"] = "running"
    try:
        svc = LinkedInService()
        if file_path:
            post_id = svc.post_image(member_urn, text, file_path, access_token)
        else:
            post_id = svc.post_text(member_urn, text, access_token)
        _job_meta[job_id]["status"] = "published"
        _job_meta[job_id]["post_id"] = post_id
        print(f"✅ Scheduled LinkedIn post published — post_id={post_id}  job_id={job_id}")
    except Exception as e:
        _job_meta[job_id]["status"] = "failed"
        _job_meta[job_id]["error"] = str(e)
        print(f"❌ Scheduled LinkedIn post failed — job_id={job_id}  error={e}")


def _run_x_post(
    job_id: str,
    x_user_id: str,
    access_token: str,
    text: Optional[str] = None,
    file_path: Optional[str] = None,
):
    """Execute a scheduled X (Twitter) post."""
    import asyncio
    from app.services.x_client import x_client
    _job_meta[job_id]["status"] = "running"
    
    async def _async_logic():
        media_ids = []
        if file_path:
            media_id = await x_client.upload_media(access_token, file_path)
            media_ids.append(media_id)
            
        return await x_client.post_tweet(access_token, text, media_ids=media_ids if media_ids else None)

    try:
        tweet = asyncio.run(_async_logic())
        _job_meta[job_id]["status"] = "published"
        _job_meta[job_id]["post_id"] = tweet.get("id")
        print(f"✅ Scheduled X post published — tweet_id={tweet.get('id')}  job_id={job_id}")
    except Exception as e:
        _job_meta[job_id]["status"] = "failed"
        _job_meta[job_id]["error"] = str(e)
        print(f"❌ Scheduled X post failed — job_id={job_id}  error={e}")




# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def schedule_instagram_post(
    scheduler: "BackgroundScheduler",
    scheduled_at: datetime,
    user_id: int,
    hosted_image_url: str,
    caption: str,
) -> str:
    job_id = str(uuid.uuid4())
    _job_meta[job_id] = _make_meta(job_id, "instagram", scheduled_at, user_id)
    scheduler.add_job(
        _run_instagram_post,
        trigger="date",
        run_date=scheduled_at,
        kwargs={
            "job_id": job_id, 
            "user_id": user_id,
            "hosted_image_url": hosted_image_url, 
            "caption": caption
        },
        id=job_id,
        replace_existing=False,
        misfire_grace_time=300,
    )
    return job_id


def schedule_instagram_carousel(
    scheduler: "BackgroundScheduler",
    scheduled_at: datetime,
    user_id: int,
    hosted_image_urls: list[str],
    caption: str,
) -> str:
    job_id = str(uuid.uuid4())
    _job_meta[job_id] = _make_meta(job_id, "instagram_carousel", scheduled_at, user_id)
    scheduler.add_job(
        _run_instagram_carousel,
        trigger="date",
        run_date=scheduled_at,
        kwargs={
            "job_id": job_id, 
            "user_id": user_id,
            "hosted_image_urls": hosted_image_urls, 
            "caption": caption
        },
        id=job_id,
        replace_existing=False,
        misfire_grace_time=300,
    )
    return job_id


def schedule_linkedin_post(
    scheduler: "BackgroundScheduler",
    scheduled_at: datetime,
    user_id: int,
    member_urn: str,
    access_token: str,
    text: str,
    file_path: Optional[str] = None,
) -> str:
    job_id = str(uuid.uuid4())
    _job_meta[job_id] = _make_meta(job_id, "linkedin", scheduled_at, user_id)
    scheduler.add_job(
        _run_linkedin_post,
        trigger="date",
        run_date=scheduled_at,
        kwargs={
            "job_id": job_id,
            "member_urn": member_urn,
            "access_token": access_token,
            "text": text,
            "file_path": file_path,
        },
        id=job_id,
        replace_existing=False,
        misfire_grace_time=300,
    )
    return job_id


def schedule_x_post(
    scheduler: "BackgroundScheduler",
    scheduled_at: datetime,
    user_id: int,
    x_user_id: str,
    access_token: str,
    text: Optional[str] = None,
    file_path: Optional[str] = None,
) -> str:
    job_id = str(uuid.uuid4())
    _job_meta[job_id] = _make_meta(job_id, "x", scheduled_at, user_id)
    scheduler.add_job(
        _run_x_post,
        trigger="date",
        run_date=scheduled_at,
        kwargs={
            "job_id": job_id,
            "x_user_id": x_user_id,
            "access_token": access_token,
            "text": text,
            "file_path": file_path,
        },
        id=job_id,
        replace_existing=False,
        misfire_grace_time=300,
    )
    return job_id



def list_jobs(user_id: int) -> List[dict]:
    """Return metadata for all tracked jobs for a specific user."""
    return [meta for meta in _job_meta.values() if meta.get("user_id") == user_id]


def cancel_job(scheduler: "BackgroundScheduler", job_id: str, user_id: int) -> bool:
    """Remove a pending job if it belongs to the user. Returns True if found and removed."""
    if job_id in _job_meta and _job_meta[job_id].get("user_id") == user_id:
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass  # Already fired or doesn't exist in scheduler
        _job_meta[job_id]["status"] = "cancelled"
        return True
    return False
