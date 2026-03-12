"""Scalable SQL database layer using SQLModel."""

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import select, delete, func, text
from sqlmodel import Session, create_engine, SQLModel

from app.config import settings
from app.models import Resume, Job, Improvement, User, Cohort

logger = logging.getLogger(__name__)


def _unwrap_row(obj: Any) -> Any:
    """Unwrap a SQLAlchemy Row to get the underlying SQLModel instance.

    session.exec(select(Model)).all() can return Row objects (tuples)
    instead of model instances in some SQLModel/SQLAlchemy versions.
    """
    if hasattr(obj, "model_dump"):
        return obj
    # Row object - try to extract the first element (the model instance)
    if hasattr(obj, "_tuple"):
        return obj._tuple()[0]
    if isinstance(obj, tuple):
        return obj[0]
    return obj


def _to_dict(obj: Any) -> dict[str, Any]:
    """Convert a SQLModel instance to a dict with ISO-formatted datetimes.

    The rest of the codebase (routers, services) expects dicts with string
    timestamps, matching the old TinyDB format.
    """
    unwrapped = _unwrap_row(obj)
    data = unwrapped.model_dump()
    for key, value in data.items():
        if isinstance(value, datetime):
            data[key] = value.isoformat()
    return data


class Database:
    """SQL database wrapper for resume matcher data."""

    _master_resume_lock = asyncio.Lock()

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or settings.database_url
        if self.db_url:
            self.engine = create_engine(self.db_url)
            SQLModel.metadata.create_all(self.engine)
            logger.info("Initialized SQL database at %s", self.db_url)
        else:
            # Fallback to local SQLite for development
            sqlite_path = settings.data_dir / "database.db"
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            self.db_url = f"sqlite:///{sqlite_path}"
            self.engine = create_engine(
                self.db_url, connect_args={"check_same_thread": False}
            )
            SQLModel.metadata.create_all(self.engine)
            logger.info("Initialized SQLite fallback database at %s", self.db_url)

    def get_session(self):
        return Session(self.engine)

    # User / Cohort operations
    def create_cohort(self, name: str, start_date: Optional[datetime] = None) -> dict[str, Any]:
        """Create a new cohort."""
        cohort = Cohort(name=name, start_date=start_date or datetime.now(timezone.utc))
        with self.get_session() as session:
            session.add(cohort)
            session.commit()
            session.refresh(cohort)
            return _to_dict(cohort)

    def get_cohort(self, cohort_id: str) -> Optional[dict[str, Any]]:
        """Get cohort by ID."""
        with self.get_session() as session:
            cohort = session.get(Cohort, cohort_id)
            return _to_dict(cohort) if cohort else None

    def create_user(self, name: str, email: str, cohort_id: Optional[str] = None, user_id: Optional[str] = None) -> dict[str, Any]:
        """Create a new user."""
        user_data = {"name": name, "email": email, "cohort_id": cohort_id}
        if user_id:
            user_data["user_id"] = user_id
        user = User(**user_data)
        with self.get_session() as session:
            session.add(user)
            session.commit()
            session.refresh(user)
            return _to_dict(user)

    def get_user(self, user_id: str) -> Optional[dict[str, Any]]:
        """Get user by ID."""
        with self.get_session() as session:
            user = session.get(User, user_id)
            return _to_dict(user) if user else None

    def get_users_by_cohort(self, cohort_id: str) -> list[dict[str, Any]]:
        """Get users in a cohort."""
        with self.get_session() as session:
            users = session.exec(select(User).where(User.cohort_id == cohort_id)).all()
            return [_to_dict(u) for u in users]

    # Resume operations
    def create_resume(
        self,
        content: str,
        content_type: str = "md",
        filename: Optional[str] = None,
        is_master: bool = False,
        parent_id: Optional[str] = None,
        processed_data: Optional[dict[str, Any]] = None,
        processing_status: str = "pending",
        cover_letter: Optional[str] = None,
        outreach_message: Optional[str] = None,
        title: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create a new resume entry."""
        resume = Resume(
            user_id=user_id,
            content=content,
            content_type=content_type,
            filename=filename,
            is_master=is_master,
            parent_id=parent_id,
            processed_data=processed_data,
            processing_status=processing_status,
            cover_letter=cover_letter,
            outreach_message=outreach_message,
            title=title,
        )
        with self.get_session() as session:
            session.add(resume)
            session.commit()
            session.refresh(resume)
            return _to_dict(resume)

    async def create_resume_atomic_master(
        self,
        content: str,
        content_type: str = "md",
        filename: Optional[str] = None,
        processed_data: Optional[dict[str, Any]] = None,
        processing_status: str = "pending",
        cover_letter: Optional[str] = None,
        outreach_message: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create a new resume with atomic master assignment."""
        async with self._master_resume_lock:
            current_master = self.get_master_resume(user_id=user_id)
            is_master = current_master is None

            if current_master and current_master.get("processing_status") == "failed":
                with self.get_session() as session:
                    stmt = select(Resume).where(Resume.resume_id == current_master["resume_id"])
                    old_master = session.exec(stmt).first()
                    if old_master:
                        old_master.is_master = False
                        session.add(old_master)
                        session.commit()
                is_master = True

            return self.create_resume(
                content=content,
                content_type=content_type,
                filename=filename,
                is_master=is_master,
                processed_data=processed_data,
                processing_status=processing_status,
                cover_letter=cover_letter,
                outreach_message=outreach_message,
                user_id=user_id,
            )

    def get_resume(self, resume_id: str, user_id: Optional[str] = None) -> Optional[dict[str, Any]]:
        """Get resume by ID."""
        with self.get_session() as session:
            resume = session.get(Resume, resume_id)
            if resume and user_id and resume.user_id != user_id:
                return None
            return _to_dict(resume) if resume else None

    def get_master_resume(self, user_id: Optional[str] = None) -> Optional[dict[str, Any]]:
        """Get the master resume if exists."""
        with self.get_session() as session:
            statement = select(Resume).where(Resume.is_master == True)
            if user_id:
                statement = statement.where(Resume.user_id == user_id)
            resume = session.exec(statement).first()
            return _to_dict(resume) if resume else None

    def update_resume(self, resume_id: str, updates: dict[str, Any], user_id: Optional[str] = None) -> dict[str, Any]:
        """Update resume by ID."""
        with self.get_session() as session:
            resume = session.get(Resume, resume_id)
            if not resume or (user_id and resume.user_id != user_id):
                raise ValueError(f"Resume not found: {resume_id}")

            for key, value in updates.items():
                if hasattr(resume, key):
                    setattr(resume, key, value)

            resume.updated_at = datetime.now(timezone.utc)
            session.add(resume)
            session.commit()
            session.refresh(resume)
            return _to_dict(resume)

    def delete_resume(self, resume_id: str, user_id: Optional[str] = None) -> bool:
        """Delete resume by ID."""
        with self.get_session() as session:
            resume = session.get(Resume, resume_id)
            if resume and (not user_id or resume.user_id == user_id):
                session.delete(resume)
                session.commit()
                return True
            return False

    def list_resumes(self, user_id: Optional[str] = None) -> list[dict[str, Any]]:
        """List all resumes."""
        with self.get_session() as session:
            statement = select(Resume)
            if user_id:
                statement = statement.where(Resume.user_id == user_id)
            resumes = session.exec(statement).all()
            return [_to_dict(r) for r in resumes]

    def set_master_resume(self, resume_id: str, user_id: Optional[str] = None) -> bool:
        """Set a resume as the master."""
        with self.get_session() as session:
            target = session.get(Resume, resume_id)
            if not target or (user_id and target.user_id != user_id):
                return False

            query = select(Resume).where(Resume.is_master == True)
            if user_id:
                query = query.where(Resume.user_id == user_id)
                
            current_masters = session.exec(query).all()
            for row in current_masters:
                m = _unwrap_row(row)
                m.is_master = False
                session.add(m)

            target.is_master = True
            session.add(target)
            session.commit()
            return True

    # Job operations
    def create_job(self, content: str, resume_id: Optional[str] = None, user_id: Optional[str] = None) -> dict[str, Any]:
        """Create a new job description entry."""
        job = Job(content=content, resume_id=resume_id, user_id=user_id)
        with self.get_session() as session:
            session.add(job)
            session.commit()
            session.refresh(job)
            return _to_dict(job)

    def get_job(self, job_id: str, user_id: Optional[str] = None) -> Optional[dict[str, Any]]:
        """Get job by ID."""
        with self.get_session() as session:
            job = session.get(Job, job_id)
            if job and user_id and job.user_id != user_id:
                return None
            return _to_dict(job) if job else None

    def update_job(self, job_id: str, updates: dict[str, Any], user_id: Optional[str] = None) -> Optional[dict[str, Any]]:
        """Update a job by ID."""
        with self.get_session() as session:
            job = session.get(Job, job_id)
            if not job or (user_id and job.user_id != user_id):
                return None
            for key, value in updates.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            session.add(job)
            session.commit()
            session.refresh(job)
            return _to_dict(job)

    # Improvement operations
    def create_improvement(
        self,
        original_resume_id: str,
        tailored_resume_id: str,
        job_id: str,
        improvements: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Create an improvement result entry."""
        imp = Improvement(
            original_resume_id=original_resume_id,
            tailored_resume_id=tailored_resume_id,
            job_id=job_id,
            improvements=improvements,
        )
        with self.get_session() as session:
            session.add(imp)
            session.commit()
            session.refresh(imp)
            return _to_dict(imp)

    def get_improvement_by_tailored_resume(
        self, tailored_resume_id: str
    ) -> Optional[dict[str, Any]]:
        """Get improvement record by tailored resume ID."""
        with self.get_session() as session:
            stmt = select(Improvement).where(
                Improvement.tailored_resume_id == tailored_resume_id
            )
            result = session.exec(stmt).first()
            return _to_dict(result) if result else None

    # Stats
    def get_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        with self.get_session() as session:
            total_resumes = session.scalar(
                select(func.count()).select_from(Resume)
            ) or 0
            total_jobs = session.scalar(
                select(func.count()).select_from(Job)
            ) or 0
            total_improvements = session.scalar(
                select(func.count()).select_from(Improvement)
            ) or 0
            has_master = (
                session.exec(
                    select(Resume).where(Resume.is_master == True)
                ).first()
                is not None
            )

            return {
                "total_resumes": int(total_resumes),
                "total_jobs": int(total_jobs),
                "total_improvements": int(total_improvements),
                "has_master_resume": has_master,
            }

    def list_cohorts(self) -> list[dict[str, Any]]:
        """List all cohorts."""
        with self.get_session() as session:
            cohorts = session.exec(select(Cohort)).all()
            return [_to_dict(c) for c in cohorts]

    def bulk_create_users(self, cohort_id: str, students: list[dict[str, str]]) -> list[dict[str, Any]]:
        """Bulk create users for a cohort. Each student dict should have 'name' and optionally 'email', 'user_id'."""
        created = []
        with self.get_session() as session:
            for s in students:
                user_id = s.get("user_id", str(uuid4()))
                user = User(
                    user_id=user_id,
                    name=s["name"],
                    email=s.get("email"),
                    college=s.get("college"),
                    roll_number=s.get("roll_number"),
                    cohort_id=cohort_id,
                )
                session.add(user)
                created.append(user)
            session.commit()
            for u in created:
                session.refresh(u)
            return [_to_dict(u) for u in created]

    def get_cohort_students_progress(self, cohort_id: str) -> list[dict[str, Any]]:
        """Get all students in a cohort with their resume progress and ATS scores."""
        with self.get_session() as session:
            users = session.exec(select(User).where(User.cohort_id == cohort_id)).all()
            results = []
            for row in users:
                user = _unwrap_row(row)
                user_dict = _to_dict(user)

                # Get master resume for this user
                master_stmt = select(Resume).where(
                    Resume.user_id == user.user_id,
                    Resume.is_master == True,
                )
                master = session.exec(master_stmt).first()

                # Count all resumes and tailored resumes
                total_resumes = session.scalar(
                    select(func.count()).select_from(Resume).where(Resume.user_id == user.user_id)
                ) or 0
                tailored_count = session.scalar(
                    select(func.count()).select_from(Resume).where(
                        Resume.user_id == user.user_id,
                        Resume.parent_id.isnot(None),
                    )
                ) or 0
                job_count = session.scalar(
                    select(func.count()).select_from(Job).where(Job.user_id == user.user_id)
                ) or 0

                # Determine status
                if not master:
                    status = "not_started"
                elif master and _unwrap_row(master).processing_status == "failed":
                    status = "upload_failed"
                elif master and _unwrap_row(master).processing_status == "processing":
                    status = "processing"
                elif tailored_count > 0:
                    status = "improved"
                elif job_count > 0:
                    status = "scored"
                else:
                    status = "uploaded"

                master_obj = _unwrap_row(master) if master else None
                user_dict["progress"] = {
                    "status": status,
                    "has_resume": master is not None,
                    "resume_filename": master_obj.filename if master_obj else None,
                    "processing_status": master_obj.processing_status if master_obj else None,
                    "ats_score": master_obj.ats_score if master_obj else None,
                    "ats_breakdown": master_obj.ats_breakdown if master_obj else None,
                    "total_resumes": int(total_resumes),
                    "tailored_count": int(tailored_count),
                    "job_count": int(job_count),
                    "resume_uploaded_at": master_obj.created_at.isoformat() if master_obj else None,
                }
                results.append(user_dict)
            return results

    def reset_database(self) -> None:
        """Reset the database."""
        with self.get_session() as session:
            session.exec(delete(Improvement))
            session.exec(delete(Job))
            session.exec(delete(Resume))
            session.exec(delete(User))
            session.exec(delete(Cohort))
            session.commit()

        uploads_dir = settings.data_dir / "uploads"
        if uploads_dir.exists():
            import shutil

            shutil.rmtree(uploads_dir)
            uploads_dir.mkdir(parents=True, exist_ok=True)


# Global database instance
db = Database()

