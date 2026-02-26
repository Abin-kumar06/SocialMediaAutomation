"""
Pydantic models for request/response validation
"""
from pydantic import BaseModel
from typing import Optional, List


class InstagramPostResponse(BaseModel):
    """Response model for Instagram post"""
    success: bool
    creation_id: Optional[str] = None
    post_id: Optional[str] = None
    message: str
    instagram_post_url: Optional[str] = None
    uploaded_image_url: Optional[str] = None
    caption: Optional[str] = None


class HealthCheck(BaseModel):
    """Health check response"""
    status: str
    instagram_account_id: str
    api_version: str
    upload_dir: str
    config_status: dict


class InstagramMultiPostResponse(BaseModel):
    """Response model for multi-photo (carousel) Instagram post"""
    success: bool
    creation_id: Optional[str] = None
    post_id: Optional[str] = None
    message: str
    instagram_post_url: Optional[str] = None
    uploaded_image_urls: Optional[List[str]] = None
    caption: Optional[str] = None


class LinkedInAccount(BaseModel):
    """Storage for a connected LinkedIn member account"""
    user_id: str
    member_urn: str
    access_token: str
    name: str
    status: str = "active"


class XAccount(BaseModel):
    """Storage for a connected X (Twitter) account"""
    user_id: str
    x_user_id: str
    username: str
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: float  # UTC timestamp
    status: str = "active"


class LinkedInPostResponse(BaseModel):
    """Response model for LinkedIn post"""
    success: bool
    post_id: Optional[str] = None
    message: str
    linkedin_post_url: Optional[str] = None
    uploaded_image_url: Optional[str] = None
    caption: Optional[str] = None


    caption: Optional[str] = None


class ScheduledPostResponse(BaseModel):
    """Response when a post is successfully scheduled"""
    success: bool
    job_id: str
    scheduled_at: str
    platform: str
    message: str


class ScheduledJobInfo(BaseModel):
    """Info about a single scheduled job"""
    job_id: str
    platform: str
    scheduled_at: str
    status: str
    post_id: Optional[str] = None
    error: Optional[str] = None


class ScheduledJobsListResponse(BaseModel):
    """List of all scheduled jobs"""
    jobs: List[ScheduledJobInfo]
    total: int
