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


def _make_meta(job_id: str, platform: str, scheduled_at: datetime) -> dict:
    return {
        "job_id": job_id,
        "platform": platform,
        "scheduled_at": scheduled_at.isoformat(),
        "status": "pending",
    }


# ---------------------------------------------------------------------------
# Job functions (called by APScheduler at run-time)
# ---------------------------------------------------------------------------

def _run_instagram_post(job_id: str, hosted_image_url: str, caption: str):
    """Execute a scheduled Instagram single-image post."""
    from app.services import InstagramService
    _job_meta[job_id]["status"] = "running"
    try:
        svc = InstagramService()
        creation_id = svc.create_media_container(hosted_image_url, caption)
        import time; time.sleep(2)
        post_id = svc.publish_media_container(creation_id)
        _job_meta[job_id]["status"] = "published"
        _job_meta[job_id]["post_id"] = post_id
        print(f"✅ Scheduled Instagram post published — post_id={post_id}  job_id={job_id}")
    except Exception as e:
        _job_meta[job_id]["status"] = "failed"
        _job_meta[job_id]["error"] = str(e)
        print(f"❌ Scheduled Instagram post failed — job_id={job_id}  error={e}")


def _run_instagram_carousel(job_id: str, hosted_image_urls: list[str], caption: str):
    """Execute a scheduled Instagram carousel post."""
    from app.services import InstagramService
    _job_meta[job_id]["status"] = "running"
    try:
        svc = InstagramService()
        creation_id = svc.create_carousel_media(hosted_image_urls, caption)
        import time; time.sleep(2)
        post_id = svc.publish_media_container(creation_id)
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def schedule_instagram_post(
    scheduler: "BackgroundScheduler",
    scheduled_at: datetime,
    hosted_image_url: str,
    caption: str,
) -> str:
    job_id = str(uuid.uuid4())
    _job_meta[job_id] = _make_meta(job_id, "instagram", scheduled_at)
    scheduler.add_job(
        _run_instagram_post,
        trigger="date",
        run_date=scheduled_at,
        kwargs={"job_id": job_id, "hosted_image_url": hosted_image_url, "caption": caption},
        id=job_id,
        replace_existing=False,
        misfire_grace_time=300,
    )
    return job_id


def schedule_instagram_carousel(
    scheduler: "BackgroundScheduler",
    scheduled_at: datetime,
    hosted_image_urls: list[str],
    caption: str,
) -> str:
    job_id = str(uuid.uuid4())
    _job_meta[job_id] = _make_meta(job_id, "instagram_carousel", scheduled_at)
    scheduler.add_job(
        _run_instagram_carousel,
        trigger="date",
        run_date=scheduled_at,
        kwargs={"job_id": job_id, "hosted_image_urls": hosted_image_urls, "caption": caption},
        id=job_id,
        replace_existing=False,
        misfire_grace_time=300,
    )
    return job_id


def schedule_linkedin_post(
    scheduler: "BackgroundScheduler",
    scheduled_at: datetime,
    member_urn: str,
    access_token: str,
    text: str,
    file_path: Optional[str] = None,
) -> str:
    job_id = str(uuid.uuid4())
    _job_meta[job_id] = _make_meta(job_id, "linkedin", scheduled_at)
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


def list_jobs() -> List[dict]:
    """Return metadata for all tracked jobs (pending, running, published, failed)."""
    return list(_job_meta.values())


def cancel_job(scheduler: "BackgroundScheduler", job_id: str) -> bool:
    """Remove a pending job. Returns True if found and removed."""
    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass  # Already fired or doesn't exist in scheduler
    if job_id in _job_meta:
        _job_meta[job_id]["status"] = "cancelled"
        return True
    return False
