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

    In SQLAlchemy 2.0 / SQLModel, queries often return Row objects instead
    of model instances. This helper ensures we work with the actual model.
    """
    if obj is None:
        return None
    if hasattr(obj, "model_dump"):
        return obj
    
    # Try different ways to get the model from a Row
    # 1. Row._mapping.values()
    if hasattr(obj, "_mapping"):
        mapping = obj._mapping
        if mapping:
            return next(iter(mapping.values()))
    
    # 2. Row._tuple() or tuple(Row)
    if hasattr(obj, "_tuple"):
        tpl = obj._tuple()
        if tpl:
            return tpl[0]
            
    if isinstance(obj, (tuple, list)) and len(obj) > 0:
        return obj[0]
        
    return obj


def _to_dict(obj: Any) -> dict[str, Any]:
    """Convert a SQLModel instance to a dict with ISO-formatted datetimes.

    The rest of the codebase (routers, services) expects dicts with string
    timestamps, matching the old TinyDB format.
    """
    unwrapped = _unwrap_row(obj)
    if not unwrapped:
        return {}
    
    # Ensure it's a dict
    if hasattr(unwrapped, "model_dump"):
        data = unwrapped.model_dump()
    elif hasattr(unwrapped, "dict"):
        data = unwrapped.dict()
    elif isinstance(unwrapped, dict):
        data = unwrapped
    else:
        # Fallback for unexpected types
        return {}

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
            # Fix for Railway providing postgres:// instead of postgresql://
            if self.db_url.startswith("postgres://"):
                self.db_url = self.db_url.replace("postgres://", "postgresql://", 1)
                
            self.engine = create_engine(self.db_url, pool_pre_ping=True)
            SQLModel.metadata.create_all(self.engine)
            self._run_migrations()
            logger.info("Initialized SQL database at %s", self.db_url)
        else:
            # Fallback to local SQLite for development
            sqlite_path = settings.data_dir / "database.db"
            sqlite_path.parent.mkdir(parents=True, exist_ok=True)
            self.db_url = f"sqlite:///{sqlite_path}"
            self.engine = create_engine(
                self.db_url, connect_args={"check_same_thread": False}, pool_pre_ping=True
            )
            SQLModel.metadata.create_all(self.engine)
            self._run_migrations()
            logger.info("Initialized SQLite fallback database at %s", self.db_url)

    def _run_migrations(self):
        """Run lightweight schema migrations for new columns."""
        migrations = [
            # table, column, type
            ("job", "job_keywords", "JSON"),
            ("job", "resume_id", "VARCHAR"),
            ("job", "preview_hash", "VARCHAR"),
            ("job", "preview_prompt_id", "VARCHAR"),
            ("job", "preview_hashes", "JSON"),
            ("user", "cohort_id", "VARCHAR"),
            ("user", "college", "VARCHAR"),
            ("user", "roll_number", "VARCHAR"),
            ("cohort", "created_at", "TIMESTAMP"),
            ("cohort", "start_date", "TIMESTAMP"),
            ("resume", "ats_score", "INTEGER"),
            ("resume", "ats_breakdown", "JSON"),
            ("resume", "processing_status", "VARCHAR"),
            ("resume", "error_message", "TEXT"),
        ]
        
        for table, column, col_type in migrations:
            # Connect separately for each migration to avoid transaction block errors in Postgres
            with self.engine.connect() as conn:
                try:
                    # Check if column exists - quote table/column names for Postgres safety
                    conn.execute(text(f'SELECT "{column}" FROM "{table}" LIMIT 1'))
                except Exception:
                    # Column likely doesn't exist, try adding it in a fresh transaction
                    logger.info("Adding column %s.%s (%s)", table, column, col_type)
                    with self.engine.begin() as begin_conn:
                        try:
                            # Attempt to add column
                            begin_conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {col_type}'))
                        except Exception as e:
                            logger.warning("Migration for %s.%s failed: %s", table, column, e)

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

    def create_user(
        self,
        name: str,
        email: str,
        cohort_id: Optional[str] = None,
        user_id: Optional[str] = None,
        college: Optional[str] = None,
        roll_number: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create or update a user."""
        with self.get_session() as session:
            existing = None
            if user_id:
                existing = session.get(User, user_id)
            
            if existing:
                # Update existing user
                existing.name = name
                if email:
                    existing.email = email
                if cohort_id:
                    existing.cohort_id = cohort_id
                if college:
                    existing.college = college
                if roll_number:
                    existing.roll_number = roll_number
                session.add(existing)
                session.commit()
                session.refresh(existing)
                return _to_dict(existing)
            else:
                # Create new user
                user_data = {
                    "name": name,
                    "email": email,
                    "cohort_id": cohort_id,
                    "college": college,
                    "roll_number": roll_number,
                }
                if user_id:
                    user_data["user_id"] = user_id
                user = User(**user_data)
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
            is_master = True # For bulk uploads, we often want the newest to be master.

            if current_master:
                # Demote old master
                with self.get_session() as session:
                    old_master_row = session.get(Resume, current_master["resume_id"])
                    if old_master_row:
                        old_master = _unwrap_row(old_master_row)
                        old_master.is_master = False
                        session.add(old_master)
                        session.commit()

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
            resume_obj = session.get(Resume, resume_id)
            if resume_obj and user_id and resume_obj.user_id != user_id:
                return None
            
            if resume_obj:
                resume = _unwrap_row(resume_obj)
                if resume.is_master:
                    # Apply effective score sync
                    self._get_effective_score(session, resume.user_id)
                return _to_dict(resume)
            return None

    def get_master_resume(self, user_id: Optional[str] = None) -> Optional[dict[str, Any]]:
        """Get the master resume if exists."""
        with self.get_session() as session:
            statement = select(Resume).where(Resume.is_master == True)
            if user_id:
                statement = statement.where(Resume.user_id == user_id)
            resume_obj = session.exec(statement).first()
            if resume_obj:
                resume = _unwrap_row(resume_obj)
                # Apply effective score sync
                self._get_effective_score(session, resume.user_id)
                return _to_dict(resume)
            return None

    def update_resume(self, resume_id: str, updates: dict[str, Any], user_id: Optional[str] = None) -> dict[str, Any]:
        """Update resume by ID."""
        with self.get_session() as session:
            resume_obj = session.get(Resume, resume_id)
            resume = _unwrap_row(resume_obj)
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
            
            # Sync scores for the master resume in the list
            results = []
            for row in resumes:
                resume = _unwrap_row(row)
                if resume.is_master:
                    # Apply effective score sync
                    self._get_effective_score(session, resume.user_id)
                results.append(_to_dict(resume))
            return results

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
            job_obj = session.get(Job, job_id)
            job = _unwrap_row(job_obj)
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

    def list_jobs(self, user_id: Optional[str] = None) -> list[dict[str, Any]]:
        """List all jobs."""
        with self.get_session() as session:
            statement = select(Job)
            if user_id:
                statement = statement.where(Job.user_id == user_id)
            jobs = session.exec(statement).all()
            return [_to_dict(j) for j in jobs]

    def bulk_create_users(self, cohort_id: str, students: list[dict[str, str]]) -> list[dict[str, Any]]:
        """Bulk create or update users for a cohort."""
        results = []
        with self.get_session() as session:
            for s in students:
                user_id = s.get("user_id")
                existing = None
                if user_id:
                    existing = session.get(User, user_id)
                
                if existing:
                    # Update existing user
                    existing.name = s.get("name", existing.name)
                    existing.email = s.get("email", existing.email)
                    existing.college = s.get("college", existing.college)
                    existing.roll_number = s.get("roll_number", existing.roll_number)
                    existing.cohort_id = cohort_id
                    session.add(existing)
                    results.append(existing)
                else:
                    # Create new user
                    user = User(
                        user_id=user_id or str(uuid4()),
                        name=s["name"],
                        email=s.get("email"),
                        college=s.get("college"),
                        roll_number=s.get("roll_number"),
                        cohort_id=cohort_id,
                    )
                    session.add(user)
                    results.append(user)
            session.commit()
            # Note: Results might need refreshing if they are to be returned as full dicts
            return [_to_dict(u) for u in results]

    def _get_effective_score(self, session: Session, user_id: str) -> tuple[Optional[int], Optional[dict[str, Any]]]:
        """Internal helper to find the best ATS score across all resumes for a user."""
        # Get master resume first
        master_stmt = select(Resume).where(
            Resume.user_id == user_id,
            Resume.is_master == True,
        )
        master = session.exec(master_stmt).first()
        master_obj = _unwrap_row(master) if master else None

        # Prefer master resume's score if it exists
        effective_ats_score = master_obj.ats_score if master_obj else None
        effective_ats_breakdown = master_obj.ats_breakdown if master_obj else None

        # Fallback to best score from ANY resume for this user
        if effective_ats_score is None:
            best_scored_stmt = (
                select(Resume)
                .where(
                    Resume.user_id == user_id,
                    Resume.ats_score.isnot(None),
                )
                .order_by(Resume.ats_score.desc())
                .limit(1)
            )
            best_scored = session.exec(best_scored_stmt).first()
            if best_scored:
                best_obj = _unwrap_row(best_scored)
                effective_ats_score = best_obj.ats_score
                effective_ats_breakdown = best_obj.ats_breakdown
                
                # Propagate to master if it exists (even if it's not fully parsed/ready)
                if master_obj:
                    master_obj.ats_score = effective_ats_score
                    master_obj.ats_breakdown = effective_ats_breakdown
                    session.add(master_obj)
                    session.commit()
                    session.refresh(master_obj)

        return effective_ats_score, effective_ats_breakdown

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

                master_obj = _unwrap_row(master) if master else None

                # Get ATS score: use consistent shared fallback logic
                effective_ats_score, effective_ats_breakdown = self._get_effective_score(session, user.user_id)

                # Determine status
                if not master:
                    status = "not_started"
                elif master_obj and master_obj.processing_status == "failed":
                    status = "upload_failed"
                elif master_obj and master_obj.processing_status == "processing":
                    status = "processing"
                elif effective_ats_score is not None:
                    status = "scored"
                elif tailored_count > 0:
                    status = "improved"
                elif job_count > 0:
                    status = "scored"
                else:
                    status = "uploaded"

                user_dict["progress"] = {
                    "status": status,
                    "has_resume": master is not None,
                    "resume_filename": master_obj.filename if master_obj else None,
                    "processing_status": master_obj.processing_status if master_obj else None,
                    "ats_score": effective_ats_score,
                    "ats_breakdown": effective_ats_breakdown,
                    "total_resumes": int(total_resumes),
                    "tailored_count": int(tailored_count),
                    "job_count": int(job_count),
                    "resume_uploaded_at": master_obj.created_at.isoformat() if master_obj else None,
                    "error": master_obj.error_message if master_obj else None,
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

    def delete_cohort(self, cohort_id: str) -> bool:
        """Delete a cohort and all associated data (users, resumes, jobs, improvements)."""
        with self.get_session() as session:
            cohort = session.get(Cohort, cohort_id)
            if not cohort:
                return False
            
            # Find all users in this cohort
            users = session.exec(select(User).where(User.cohort_id == cohort_id)).all()
            for u in users:
                user = _unwrap_row(u)
                self.delete_user_data(user.user_id, session=session)
                session.delete(user)
            
            session.delete(cohort)
            session.commit()
            return True

    def delete_user_data(self, user_id: str, session: Optional[Session] = None) -> bool:
        """Delete all resume and job data for a user."""
        should_commit = False
        if session is None:
            session = self.get_session()
            should_commit = True
        
        try:
            # Delete jobs
            session.exec(delete(Job).where(Job.user_id == user_id))
            
            # Delete improvements associated with resumes
            # Improvements don't have user_id, but they reference resume_ids
            resumes = session.exec(select(Resume).where(Resume.user_id == user_id)).all()
            resume_ids = [r.resume_id for r in resumes]
            if resume_ids:
                session.exec(delete(Improvement).where(Improvement.original_resume_id.in_(resume_ids)))
                session.exec(delete(Improvement).where(Improvement.tailored_resume_id.in_(resume_ids)))
            
            # Delete resumes
            session.exec(delete(Resume).where(Resume.user_id == user_id))
            
            if should_commit:
                session.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting user data: {e}")
            if should_commit:
                session.rollback()
            return False
        finally:
            if should_commit:
                session.close()

    def reset_database_files(self) -> None:
        """Clean up uploaded files."""


# Global database instance
db = Database()

