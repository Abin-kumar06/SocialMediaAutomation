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


from app.database import db

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _store_meta(job_id: str, platform: str, scheduled_at: datetime, user_id: int, image_url: str = None, caption: str = None):
    with db.get_connection() as conn:
        conn.execute("""
            INSERT INTO scheduled_posts (job_id, user_id, platform, scheduled_at, status, image_url, caption)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (job_id, user_id, platform, scheduled_at.isoformat(), "pending", image_url, caption))
        conn.commit()

def _update_status(job_id: str, status: str, post_id: str = None, error: str = None):
    with db.get_connection() as conn:
        if post_id:
            conn.execute("UPDATE scheduled_posts SET status = ?, post_id = ? WHERE job_id = ?", (status, post_id, job_id))
        elif error:
            conn.execute("UPDATE scheduled_posts SET status = ?, error = ? WHERE job_id = ?", (status, error, job_id))
        else:
            conn.execute("UPDATE scheduled_posts SET status = ? WHERE job_id = ?", (status, job_id))
        conn.commit()


# ---------------------------------------------------------------------------
# Job functions (called by APScheduler at run-time)
# ---------------------------------------------------------------------------

def _run_instagram_post(job_id: str, user_id: int, hosted_image_url: str, caption: str):
    """Execute a scheduled Instagram single-image post."""
    from app.services import InstagramService
    _update_status(job_id, "running")
    try:
        from app.services.instagram_token_service import InstagramTokenService
        token_svc = InstagramTokenService()
        access_token = token_svc.get_access_token_for_user(user_id)
        
        svc = InstagramService()
        creation_id = svc.create_media_container(hosted_image_url, caption, access_token)
        import time; time.sleep(2)
        post_id = svc.publish_media_container(creation_id, access_token)
        _update_status(job_id, "published", post_id=post_id)
        print(f"✅ Scheduled Instagram post published — post_id={post_id}  job_id={job_id}")
    except Exception as e:
        _update_status(job_id, "failed", error=str(e))
        print(f"❌ Scheduled Instagram post failed — job_id={job_id}  error={e}")


def _run_instagram_carousel(job_id: str, user_id: int, hosted_image_urls: list[str], caption: str):
    """Execute a scheduled Instagram carousel post."""
    from app.services import InstagramService
    _update_status(job_id, "running")
    try:
        from app.services.instagram_token_service import InstagramTokenService
        token_svc = InstagramTokenService()
        access_token = token_svc.get_access_token_for_user(user_id)

        svc = InstagramService()
        creation_id = svc.create_carousel_media(hosted_image_urls, caption, access_token)
        import time; time.sleep(2)
        post_id = svc.publish_media_container(creation_id, access_token)
        _update_status(job_id, "published", post_id=post_id)
        print(f"✅ Scheduled Instagram carousel published — post_id={post_id}  job_id={job_id}")
    except Exception as e:
        _update_status(job_id, "failed", error=str(e))
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
    _update_status(job_id, "running")
    try:
        svc = LinkedInService()
        if file_path:
            post_id = svc.post_image(member_urn, text, file_path, access_token)
        else:
            post_id = svc.post_text(member_urn, text, access_token)
        _update_status(job_id, "published", post_id=post_id)
        print(f"✅ Scheduled LinkedIn post published — post_id={post_id}  job_id={job_id}")
    except Exception as e:
        _update_status(job_id, "failed", error=str(e))
        print(f"❌ Scheduled LinkedIn post failed — job_id={job_id}  error={e}")


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
    _store_meta(job_id, "instagram", scheduled_at, user_id, image_url=hosted_image_url, caption=caption)
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
    _store_meta(job_id, "instagram_carousel", scheduled_at, user_id, caption=caption)
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
    _store_meta(job_id, "linkedin", scheduled_at, user_id, caption=text)
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


    return job_id


def list_jobs(user_id: int) -> List[dict]:
    """Return metadata for all tracked jobs for a specific user from database."""
    with db.get_connection() as conn:
        cursor = conn.execute("SELECT * FROM scheduled_posts WHERE user_id = ? ORDER BY scheduled_at DESC", (user_id,))
        return [dict(row) for row in cursor.fetchall()]


def get_stats(user_id: int) -> dict:
    """Return aggregated status counts for the user."""
    with db.get_connection() as conn:
        cursor = conn.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE status = 'published') as published,
                COUNT(*) FILTER (WHERE status = 'pending') as scheduled,
                COUNT(*) FILTER (WHERE status = 'failed') as failed
            FROM scheduled_posts 
            WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        return {
            "published": row['published'] or 0,
            "scheduled": row['scheduled'] or 0,
            "failed": row['failed'] or 0
        }


def cancel_job(scheduler: "BackgroundScheduler", job_id: str, user_id: int) -> bool:
    """Remove a pending job if it belongs to the user. Returns True if found and removed."""
    with db.get_connection() as conn:
        cursor = conn.execute("SELECT user_id FROM scheduled_posts WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        if row and row['user_id'] == user_id:
            try:
                scheduler.remove_job(job_id)
            except Exception:
                pass  # Already fired or doesn't exist in scheduler
            _update_status(job_id, "cancelled")
            return True
    return False
