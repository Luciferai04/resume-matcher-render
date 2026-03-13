from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import JSON, String, Boolean
from sqlmodel import Field, SQLModel


class Cohort(SQLModel, table=True):
    """Cohort model for SQL storage."""
    cohort_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    name: str = Field(index=True)
    start_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class User(SQLModel, table=True):
    """User model for SQL storage."""
    user_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    name: str
    email: Optional[str] = Field(default=None, index=True)
    college: Optional[str] = Field(default=None, index=True)
    roll_number: Optional[str] = Field(default=None, index=True)
    cohort_id: Optional[str] = Field(default=None, foreign_key="cohort.cohort_id", index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Resume(SQLModel, table=True):
    """Resume model for SQL storage."""
    resume_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.user_id", index=True)
    content: str = Field(sa_type=String)
    content_type: str = Field(default="md")
    filename: Optional[str] = None
    is_master: bool = Field(default=False, sa_type=Boolean, index=True)
    parent_id: Optional[str] = Field(default=None, index=True)
    processed_data: Optional[dict[str, Any]] = Field(default=None, sa_type=JSON)
    processing_status: str = Field(default="pending", index=True)
    cover_letter: Optional[str] = None
    outreach_message: Optional[str] = None
    title: Optional[str] = None
    ats_score: Optional[int] = Field(default=None, index=True)
    ats_breakdown: Optional[dict[str, Any]] = Field(default=None, sa_type=JSON)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Job(SQLModel, table=True):
    """Job description model for SQL storage."""
    job_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: str = Field(foreign_key="user.user_id", index=True)
    content: str = Field(sa_type=String)
    job_keywords: Optional[dict[str, Any]] = Field(default=None, sa_type=JSON)
    resume_id: Optional[str] = Field(default=None, index=True)
    preview_hash: Optional[str] = None
    preview_prompt_id: Optional[str] = None
    preview_hashes: Optional[dict[str, Any]] = Field(default=None, sa_type=JSON)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Improvement(SQLModel, table=True):
    """Improvement result model for SQL storage."""
    request_id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    original_resume_id: str = Field(index=True)
    tailored_resume_id: str = Field(index=True)
    job_id: str = Field(index=True)
    improvements: list[dict[str, Any]] = Field(sa_type=JSON)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
