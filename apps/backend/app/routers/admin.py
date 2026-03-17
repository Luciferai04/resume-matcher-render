"""Admin endpoints for cohort and student management."""

import logging
import datetime
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile, Query
from pydantic import BaseModel, Field

from sqlalchemy import select
from app.database import db
from app.services.parser import parse_document, parse_resume_to_json
from app.services.downloader import download_file
from app.services.ats_scorer import score_and_update_resume, calculate_ats_score

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


# ─── Pydantic Models ───────────────────────────────────────────────────────────

class CreateCohortRequest(BaseModel):
    name: str
    

class StudentEntry(BaseModel):
    name: str
    email: Optional[str] = None
    user_id: Optional[str] = None
    college: Optional[str] = None
    roll_number: Optional[str] = None


class AddStudentsRequest(BaseModel):
    students: list[StudentEntry]


class CohortResponse(BaseModel):
    cohort_id: str
    name: str
    created_at: str


class StudentProgress(BaseModel):
    user_id: str
    name: str
    email: Optional[str] = None
    college: Optional[str] = None
    roll_number: Optional[str] = None
    progress: dict[str, Any]


class CohortStatsResponse(BaseModel):
    total_students: int
    resumes_uploaded: int
    resumes_scored: int
    resumes_improved: int
    average_ats_score: Optional[float] = None
    status_breakdown: dict[str, int]


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: str
    name: str
    email: Optional[str] = None
    ats_score: Optional[int] = None
    resume_filename: Optional[str] = None
    tailored_count: int = 0
    status: str = "not_started"


# ─── Diagnostic Endpoints ─────────────────────────────────────────────────────

@router.get("/diag/ping")
async def diag_ping():
    return {"status": "ok", "message": "Admin diag is accessible"}

@router.get("/diag/schema")
async def check_schema():
    """Check database schema for Resume table."""
    try:
        from sqlalchemy import text
        with db.engine.connect() as conn:
            # Query columns for Resume table
            # For Postgres:
            result = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'resume'"))
            columns = [{"column": r[0], "type": r[1]} for r in result]
            return {"table": "resume", "columns": columns}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/diag/resumes")
async def get_resume_stats():
    """Get breakdown of all resumes by status."""
    try:
        from sqlalchemy import func, select
        from app.models import Resume
        with db.get_session() as session:
            # Count by status
            stmt = select(Resume.processing_status, func.count(Resume.resume_id)).group_by(Resume.processing_status)
            stats_results = session.exec(stmt).all()
            
            # Get last 5 resumes for inspection
            last_resumes = session.exec(select(Resume).order_by(Resume.created_at.desc()).limit(5)).all()
            
            from app.database import _unwrap_row
            
            return {
                "status_breakdown": {row[0]: row[1] for row in stats_results},
                "recent_resumes": [
                    {
                        "id": obj.resume_id if (obj := _unwrap_row(r)) else None,
                        "filename": obj.filename if obj else None,
                        "status": obj.processing_status if obj else None,
                        "ats_score": obj.ats_score if obj else None,
                        "parent_id": obj.parent_id if obj else None,
                        "error": obj.error_message if obj else None,
                        "created_at": obj.created_at.isoformat() if obj and obj.created_at else None
                    }
                    for r in last_resumes
                ]
            }
    except Exception as e:
        import traceback
        return {"status": "error", "message": str(e), "traceback": traceback.format_exc()}


@router.get("/diag/llm")
async def test_llm_connectivity():
    """Test LLM connectivity with current configuration."""
    try:
        from app.llm import complete_json
        from app.config import settings
        
        config_path = settings.config_path
        config_info = {}
        if config_path.exists():
            import json
            config_info = json.loads(config_path.read_text())
            # Mask API key
            if "api_key" in config_info:
                config_info["api_key"] = config_info["api_key"][:6] + "..." + config_info["api_key"][-4:] if len(config_info["api_key"]) > 10 else "***"
        
        prompt = "Return a JSON object with a single key 'status' and value 'ok'. This is a connectivity test."
        result = await complete_json(prompt=prompt)
        
        return {
            "status": "success",
            "config": config_info,
            "test_result": result
        }
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }


@router.get("/diag/config-fix")
async def fix_production_config():
    """Correct persistent invalid configuration in production."""
    try:
        from app.config import settings
        import json
        import os
        
        config_path = settings.config_path
        if not config_path.exists():
            return {"status": "skipped", "message": "No config.json found to fix."}
            
        config_info = json.loads(config_path.read_text())
        old_model = config_info.get("model")
        
        # known broken values
        BROKEN_MODELS = {"gemini-3.1-flash-lite-preview", "gemini-flash-latest"}
        CORRECT_MODEL = "gemini-flash-lite-latest"
        
        if old_model in BROKEN_MODELS:
            config_info["model"] = CORRECT_MODEL
            config_path.write_text(json.dumps(config_info, indent=2))
            return {
                "status": "success", 
                "message": f"Updated model from {old_model} to {CORRECT_MODEL}",
                "new_config": config_info
            }
            
        return {
            "status": "not_needed", 
            "message": f"Current model '{old_model}' does not need auto-fixing.",
            "current_config": config_info
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/diag/failures")
async def get_failed_resumes():
    """Diagnostic route to check failed resumes and error messages."""
    try:
        from sqlalchemy import select
        from app.models import Resume
        from app.database import _unwrap_row
        import traceback
        
        with db.get_session() as session:
            statement = select(Resume).where(Resume.processing_status == "failed").order_by(Resume.created_at.desc()).limit(20)
            results = session.exec(statement).all()
            return [
                {
                    "resume_id": obj.resume_id if (obj := _unwrap_row(r)) else None,
                    "filename": obj.filename if obj else None,
                    "error": obj.error_message if obj else None,
                    "created_at": obj.created_at.isoformat() if obj and obj.created_at else None
                }
                for r in results
            ]
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }


@router.get("/diag/rescore/{resume_id}")
async def diag_rescore_resume(resume_id: str, job_id: Optional[str] = None):
    """Manually trigger scoring for a resume."""
    try:
        from app.models import Resume, Job
        from app.database import _unwrap_row
        from app.services.ats_scorer import score_and_update_resume
        from sqlalchemy import select
        
        with db.get_session() as session:
            resume = session.get(Resume, resume_id)
            if not resume:
                return {"status": "error", "message": f"Resume {resume_id} not found"}
            
            obj = _unwrap_row(resume)
            if not obj.processed_data:
                return {"status": "error", "message": "Resume not processed yet (no processed_data)"}
            
            # If no job_id provided, try to find the last created job
            if not job_id:
                stmt = select(Job).order_by(Job.created_at.desc()).limit(1)
                job_res = session.exec(stmt).first()
                if job_res:
                    job_obj = _unwrap_row(job_res)
                    job_id = job_obj.job_id
                else:
                    logger.info("No job provided or found for manual rescore, using general scoring")
                    job_id = None

            logger.info("Triggering manual re-score for resume %s against job %s", resume_id, job_id)
            result = await score_and_update_resume(resume_id, obj.processed_data, job_id, user_id=obj.user_id)
            
            return {
                "status": "success",
                "resume_id": resume_id,
                "job_id": job_id,
                "result": result
            }
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }




# ─── Cohort Endpoints ──────────────────────────────────────────────────────────

@router.post("/cohorts", response_model=CohortResponse)
async def create_cohort(request: CreateCohortRequest) -> CohortResponse:
    """Create a new cohort for a batch of students."""
    cohort = db.create_cohort(name=request.name)
    return CohortResponse(
        cohort_id=cohort["cohort_id"],
        name=cohort["name"],
        created_at=cohort["created_at"],
    )


@router.get("/cohorts")
async def list_cohorts():
    """List all cohorts."""
    cohorts = db.list_cohorts()
    return {"cohorts": cohorts}


@router.get("/cohorts/{cohort_id}")
async def get_cohort(cohort_id: str):
    """Get cohort details."""
    cohort = db.get_cohort(cohort_id)
    if not cohort:
        raise HTTPException(status_code=404, detail="Cohort not found")
    return cohort


@router.delete("/cohorts/{cohort_id}")
async def delete_cohort_endpoint(cohort_id: str):
    """Delete a cohort and all its associated data."""
    # Check if the cohort exists first to distinguish 404 from 500
    cohort = db.get_cohort(cohort_id)
    if not cohort:
        raise HTTPException(status_code=404, detail="Cohort not found")
    
    success = db.delete_cohort(cohort_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete cohort. Check server logs for details.")
    return {"message": "Cohort and all associated data deleted successfully"}


# ─── Student Management ───────────────────────────────────────────────────────

@router.post("/cohorts/{cohort_id}/students")
async def add_students(cohort_id: str, request: AddStudentsRequest):
    """Add students to a cohort (bulk create)."""
    cohort = db.get_cohort(cohort_id)
    if not cohort:
        raise HTTPException(status_code=404, detail="Cohort not found")

    students_data = [s.model_dump() for s in request.students]
    created = db.bulk_create_users(cohort_id, students_data)
    return {
        "message": f"Created {len(created)} students",
        "students": created,
    }


@router.get("/cohorts/{cohort_id}/students")
async def get_students_progress(cohort_id: str):
    """Get all students in a cohort with progress tracking."""
    cohort = db.get_cohort(cohort_id)
    if not cohort:
        raise HTTPException(status_code=404, detail="Cohort not found")

    students = db.get_cohort_students_progress(cohort_id)
    return {"cohort": cohort, "students": students}


@router.delete("/students/{user_id}/resume")
async def delete_student_resume_endpoint(user_id: str):
    """Delete all resume and job data for a specific student."""
    success = db.delete_user_data(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Student data not found or could not be deleted")
    return {"message": "Student resumes and jobs deleted successfully"}


# ─── Bulk Resume Upload ───────────────────────────────────────────────────────

@router.post("/cohorts/{cohort_id}/bulk-upload-resumes")
async def bulk_upload_resumes(
    cohort_id: str,
    files: list[UploadFile] = File(default=[]),
    job_id: Optional[str] = None,
    as_tailored: bool = Query(False),
    drive_url: Optional[str] = Query(None),
):
    """Bulk upload resume PDFs for students in a cohort.
    
    Filenames are used to match students by user_id or name.
    Files named like 'student_001.pdf' will be assigned to user_id='student_001'.
    """
    try:
        cohort = db.get_cohort(cohort_id)
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")

        import csv
        import io

        csv_file = next((f for f in files if f.filename and f.filename.lower().endswith(".csv")), None)
        filename_map = {}
        results = []
        
        unique_students = []
        if csv_file:
            content = await csv_file.read()
            try:
                # Detect encoding
                text_content = None
                for encoding in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
                    try:
                        text_content = content.decode(encoding)
                        logger.info("Successfully decoded CSV using %s", encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                
                if text_content is None:
                    raise ValueError("Could not decode CSV file with supported encodings (utf-8, latin-1, etc)")

                reader = csv.DictReader(io.StringIO(text_content))
                students_to_create = []
                
                for row in reader:
                    # Normalized keys for fuzzy matching
                    keys = [str(k).lower().strip() for k in row.keys() if k]
                    
                    def find_key(patterns: list[str]) -> Optional[str]:
                        for p in patterns:
                            for k in row.keys():
                                if k and p.lower() in str(k).lower():
                                    return k
                        return None

                    name_key = find_key(["Full Name", "Name", "Student Name", "Username"])
                    roll_key = find_key(["Roll Number", "Student ID", "Roll No", "ID", "UID"])
                    email_key = find_key(["Email Address", "Email"])
                    college_key = find_key(["College", "Institution", "University", "School"])
                    resume_url_key = find_key(["Resume", "Link", "URL", "Upload Your Resume"])
                    
                    name = row.get(name_key, "").strip() if name_key else None
                    roll = row.get(roll_key, "").strip() if roll_key else None
                    email = row.get(email_key, "").strip() if email_key else None
                    college = row.get(college_key, "").strip() if college_key else None
                    resume_url = row.get(resume_url_key, "").strip() if resume_url_key else None
                    
                    if not name and not roll and not email:
                        continue
                        
                    user_id = roll or email or str(uuid4())
                    name = name or f"Student {user_id}"
                    
                    info = {
                        "user_id": user_id,
                        "name": name,
                        "email": email,
                        "college": college,
                        "roll_number": roll,
                        "resume_url": resume_url
                    }
                    students_to_create.append(info)
                
                seen_ids = set()
                for s in students_to_create:
                    uid = s["user_id"]
                    if uid not in seen_ids:
                        seen_ids.add(uid)
                        unique_students.append(s)
                
                count: int = 0
                if unique_students:
                    logger.info("Attempting to create %d students for cohort %s", len(unique_students), cohort_id)
                    # Pre-fetch existing students to avoid re-creating
                    existing_students = db.get_cohort_students_progress(cohort_id)
                    user_by_id = {s["user_id"]: s for s in existing_students}

                    for s in unique_students:
                        user_id = s["user_id"]
                        name = s["name"]
                        email = s.get("email") or ""
                        college = s.get("college")
                        roll_number = s.get("roll_number")
                        drive_url_val = s.get("resume_url")
                        markdown_content = s.get("markdown_content") # Assuming this might come from CSV in future

                        matched_user = user_by_id.get(user_id)

                        if not matched_user:
                            # Auto-create user
                            try:
                                user = db.create_user(
                                    name=name,
                                    email=email,
                                    cohort_id=cohort_id,
                                    college=s.get("college"),
                                    roll_number=s.get("roll_number"),
                                )
                                count += 1
                            except Exception as e:
                                logger.error("Failed to create student %s: %s", s["name"], e)
                    
                results.append({
                    "filename": csv_file.filename,
                    "status": "uploaded",
                    "message": f"Processed {len(unique_students)} rows, created/updated {count} students"
                })
            except Exception as e:
                logger.error("Failed to parse CSV: %s", e)
                results.append({
                    "filename": csv_file.filename if csv_file else "unknown.csv",
                    "status": "error",
                    "error": f"CSV Error: {str(e)}",
                })

            # Process resume URLs from CSV
            for student in unique_students:
                resume_url = student.get("resume_url")
                if not resume_url or not resume_url.startswith("http"):
                    continue
                
                user_id = student["user_id"]
                filename = f"resume_{user_id}.pdf"
                
                try:
                    # Create placeholder resume
                    resume = await db.create_resume_atomic_master(
                        content="Pending background capture...",
                        content_type="md",
                        filename=filename,
                        processing_status="pending",
                        user_id=user_id,
                    )
                    
                    # Queue the background task
                    from app.worker import capture_pdf_snapshot_task
                    capture_pdf_snapshot_task.delay(resume["resume_id"], resume_url, job_id=job_id, user_id=user_id)
                    
                    results.append({
                        "filename": filename,
                        "user_id": user_id,
                        "resume_id": resume["resume_id"],
                        "status": "processing",
                        "message": "Queued for background capture and scoring"
                    })
                except Exception as proc_err:
                    logger.error("Failed to queue background processing for %s: %s", user_id, proc_err, exc_info=True)
                    results.append({
                        "filename": filename,
                        "user_id": user_id,
                        "status": "error",
                        "error": f"Queuing failed: {str(proc_err)}",
                    })

        # Process stand-alone drive_url if provided
        if drive_url and drive_url.strip().startswith("http"):
            url = drive_url.strip()
            
            # Check if it's a folder
            is_folder = "/folders/" in url or "embeddedfolderview" in url
            urls_to_process = [url]
            
            if is_folder:
                logger.info("Detected Drive folder, scanning for files...")
                from app.services.drive_scanner import discover_drive_files
                urls_to_process = await discover_drive_files(url)
                if not urls_to_process:
                     # Fallback to treat as single URL if scan fails or returns nothing
                     urls_to_process = [url]
            
            for target_url in urls_to_process:
                # Try to infer user from URL or use a generic one
                from datetime import datetime
                user_id = f"drive_{int(datetime.now().timestamp())}_{uuid4().hex[:4]}"
                try:
                    db.create_user(name=f"Drive Upload {user_id[-4:]}", email="", cohort_id=cohort_id, user_id=user_id)
                    filename = f"drive_resume_{user_id}.pdf"
                    resume = await db.create_resume_atomic_master(
                        content="Pending background capture...",
                        content_type="md",
                        filename=filename,
                        processing_status="pending",
                        user_id=user_id,
                    )
                    from app.worker import capture_pdf_snapshot_task
                    capture_pdf_snapshot_task.delay(resume["resume_id"], target_url, job_id=job_id, user_id=user_id)
                    results.append({
                        "filename": f"Drive File ({len(results)+1})",
                        "status": "processing",
                        "message": "Queued for background capture"
                    })
                except Exception as e:
                    logger.error("Failed to process Drive URL %s: %s", target_url, e)
                    results.append({"filename": "Google Drive Link", "status": "error", "error": str(e)})

        # Match files to students
        students = db.get_cohort_students_progress(cohort_id)
        user_by_id = {s["user_id"]: s for s in students if s.get("user_id")}
        user_by_name = {s["name"].lower().strip(): s for s in students if s.get("name")}

        # Filter out the CSV file from the actual processing loop
        files_to_process = [f for f in files if f.filename and not f.filename.lower().endswith(".csv")]

        for file in files_to_process:
            filename = file.filename or "resume.pdf"
            stem = filename.rsplit(".", 1)[0].strip()

            # Match by user_id or name
            matched_user = user_by_id.get(stem) or user_by_name.get(stem.lower())
            logger.debug("Processing file %s for user match: %s", filename, stem)

            if not matched_user:
                # Auto-create user with filename as ID if no match found
                try:
                    logger.info("No match found for %s, auto-creating student", stem)
                    user = db.create_user(
                        name=stem.replace("_", " ").title(),
                        email=f"{stem}@cohort.local",
                        cohort_id=cohort_id,
                        user_id=stem,
                    )
                    matched_user = user
                    user_by_id[stem] = user
                    user_by_name[stem.lower()] = user
                except Exception as e:
                    logger.error("Failed to auto-create user for %s: %s", stem, e)
                    results.append({
                        "filename": filename,
                        "status": "error",
                        "error": f"Failed to create user: {str(e)}",
                    })
                    continue

            user_id = matched_user["user_id"]
            logger.info("Uploading for student %s (user_id: %s)", matched_user.get("name", stem), user_id)

            try:
                content = await file.read()
                if len(content) == 0:
                    results.append({
                        "filename": filename,
                        "user_id": user_id,
                        "status": "error",
                        "error": "Empty file",
                    })
                    continue

                markdown_content = await parse_document(content, filename)
                
                if as_tailored:
                    # Link to master resume as parent
                    master_resume = db.get_master_resume(user_id=user_id)
                    parent_id = master_resume["resume_id"] if master_resume else None
                    
                    resume = db.create_resume(
                        content=markdown_content,
                        content_type="md",
                        filename=filename,
                        is_master=False,
                        parent_id=parent_id,
                        processing_status="processing",
                        user_id=user_id,
                    )
                else:
                    resume = await db.create_resume_atomic_master(
                        content=markdown_content,
                        content_type="md",
                        filename=filename,
                        processing_status="processing",
                        user_id=user_id,
                    )

                try:
                    from app.worker import process_and_score_resume_task
                    process_and_score_resume_task.delay(resume["resume_id"], job_id=job_id)
                except Exception as worker_err:
                    logger.warning("Celery dispatch failed for %s, trying inline: %s", filename, worker_err)
                    try:
                        processed_data = await parse_resume_to_json(markdown_content)
                        db.update_resume(resume["resume_id"], {
                            "processed_data": processed_data,
                            "processing_status": "ready",
                        }, user_id=user_id)
                        
                        # Auto-find a job to score against if none provided
                        effective_job_id = job_id
                        if not effective_job_id:
                            from app.models import Job as JobModel
                            with db.get_session() as jsession:
                                latest_job = jsession.exec(select(JobModel).order_by(JobModel.created_at.desc()).limit(1)).first()
                                if latest_job:
                                    from app.database import _unwrap_row
                                    job_obj = _unwrap_row(latest_job)
                                    effective_job_id = job_obj.job_id
                                    logger.info("Auto-selected job %s for scoring resume %s", effective_job_id, resume["resume_id"])
                        
                        if effective_job_id:
                            await score_and_update_resume(resume["resume_id"], processed_data, effective_job_id, user_id=user_id)
                    except Exception as inline_err:
                        logger.error("Inline processing failed for %s: %s", filename, inline_err, exc_info=True)
                        db.update_resume(resume["resume_id"], {
                            "processing_status": "failed",
                            "error_message": str(inline_err),
                        }, user_id=user_id)

                results.append({
                    "filename": filename,
                    "user_id": user_id,
                    "resume_id": resume["resume_id"],
                    "status": "uploaded",
                })
            except Exception as e:
                logger.error("Failed to process %s: %s", filename, e)
                results.append({
                    "filename": filename,
                    "user_id": user_id,
                    "status": "error",
                    "error": str(e),
                })

        uploaded = sum(1 for r in results if r["status"] == "uploaded")
        failed = sum(1 for r in results if r["status"] == "error")
        return {
            "message": f"Bulk upload completed: {uploaded} successful, {failed} failed",
            "results": results,
        }
    except Exception as e:
        logger.exception("Critical error in bulk_upload_resumes")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.post("/students/{user_id}/retry")
async def retry_student_processing(user_id: str, job_id: Optional[str] = None):
    """Manually trigger background processing and scoring for a student's master resume."""
    from app.models import Resume
    from app.database import _unwrap_row
    
    with db.get_session() as session:
        stmt = select(Resume).where(Resume.user_id == user_id, Resume.is_master == True)
        resume_row = session.exec(stmt).first()
        if not resume_row:
            raise HTTPException(status_code=404, detail="Master resume not found for this student")
        
        resume = _unwrap_row(resume_row)
        resume_id = resume.resume_id
        has_processed_data = resume.processed_data is not None
        
        # Reset status to processing
        resume.processing_status = "processing"
        resume.error_message = None
        session.add(resume)
        session.commit()
    
    # Auto-find job if none provided
    if not job_id:
        from app.models import Job as JobModel
        with db.get_session() as jsession:
            latest_job = jsession.exec(select(JobModel).order_by(JobModel.created_at.desc()).limit(1)).first()
            if latest_job:
                job_obj = _unwrap_row(latest_job)
                job_id = job_obj.job_id
                logger.info("Auto-selected job %s for retry of user %s", job_id, user_id)
    
    # Try Celery first, fall back to inline
    try:
        from app.worker import process_and_score_resume_task
        process_and_score_resume_task.delay(resume_id, job_id=job_id)
        return {"status": "success", "message": "Processing task dispatched"}
    except Exception as worker_err:
        logger.warning("Celery unavailable for retry, trying inline: %s", worker_err)
        try:
            resume_data = db.get_resume(resume_id)
            if resume_data and resume_data.get("processed_data") and job_id:
                # Already parsed, just score
                await score_and_update_resume(resume_id, resume_data["processed_data"], job_id, user_id=user_id)
                return {"status": "success", "message": "Scored inline (Celery unavailable)"}
            elif resume_data and resume_data.get("content"):
                # Need to parse first, then score
                processed_data = await parse_resume_to_json(resume_data["content"])
                db.update_resume(resume_id, {
                    "processed_data": processed_data,
                    "processing_status": "ready",
                }, user_id=user_id)
                if job_id:
                    await score_and_update_resume(resume_id, processed_data, job_id, user_id=user_id)
                return {"status": "success", "message": "Processed and scored inline (Celery unavailable)"}
            else:
                db.update_resume(resume_id, {"processing_status": "failed", "error_message": "No content to process"}, user_id=user_id)
                return {"status": "error", "message": "Resume has no content to process"}
        except Exception as inline_err:
            logger.error("Inline retry failed for %s: %s", user_id, inline_err, exc_info=True)
            db.update_resume(resume_id, {"processing_status": "failed", "error_message": str(inline_err)}, user_id=user_id)
            return {"status": "error", "message": f"Inline processing failed: {str(inline_err)}"}


@router.post("/cohorts/{cohort_id}/rescore-all")
async def rescore_all_unscored(cohort_id: str, job_id: Optional[str] = None):
    """Retroactively score all unscored master resumes in a cohort."""
    from app.models import Resume, Job as JobModel
    from app.database import _unwrap_row
    
    cohort = db.get_cohort(cohort_id)
    if not cohort:
        raise HTTPException(status_code=404, detail="Cohort not found")
    
    # Auto-find job if none provided
    if not job_id:
        with db.get_session() as jsession:
            latest_job = jsession.exec(select(JobModel).order_by(JobModel.created_at.desc()).limit(1)).first()
            if latest_job:
                job_obj = _unwrap_row(latest_job)
                job_id = job_obj.job_id
            else:
                logger.info("No job provided or found for bulk rescore, using general scoring")
                job_id = None
    
    # Fetch all master resumes for users in this cohort who don't have an ATS score
    from app.models import User, Resume
    from app.database import _unwrap_row
    
    with db.get_session() as session:
        stmt = select(Resume).join(User, Resume.user_id == User.user_id).where(
            User.cohort_id == cohort_id,
            Resume.is_master == True,
            Resume.ats_score == None
        )
        candidates = session.exec(stmt).all()
        to_score = [_unwrap_row(c) for c in candidates]
    
    scored = 0
    failed = 0
    skipped = 0
    
    logger.info("Found %d unscored resumes to process in cohort %s", len(to_score), cohort_id)

    for master in to_score:
        resume_id = master.resume_id
        user_id = master.user_id
        processed_data = master.processed_data
        
        if not processed_data:
            logger.info("Resume %s missing processed_data, attempting to parse...", resume_id)
            try:
                processed_data = await parse_resume_to_json(master.content)
                db.update_resume(resume_id, {
                    "processed_data": processed_data,
                    "processing_status": "ready"
                }, user_id=user_id)
            except Exception as parse_err:
                logger.error("Failed to parse resume %s during bulk rescore: %s", resume_id, parse_err)
                failed += 1
                continue
        
        try:
            await score_and_update_resume(resume_id, processed_data, job_id, user_id=user_id)
            scored += 1
            logger.info("Rescored resume %s for user %s", resume_id, user_id)
        except Exception as e:
            failed += 1
            logger.error("Failed to rescore %s: %s", resume_id, e)
    
    return {
        "status": "success",
        "job_id": job_id,
        "scored": scored,
        "failed": failed,
        "skipped": skipped,
    }

# ─── Stats & Leaderboard ──────────────────────────────────────────────────────

@router.get("/cohorts/{cohort_id}/stats", response_model=CohortStatsResponse)
async def get_cohort_stats(cohort_id: str) -> CohortStatsResponse:
    """Get aggregated stats for a cohort."""
    cohort = db.get_cohort(cohort_id)
    if not cohort:
        raise HTTPException(status_code=404, detail="Cohort not found")

    students = db.get_cohort_students_progress(cohort_id)

    status_counts: dict[str, int] = {}
    ats_scores: list[float] = []
    resumes_uploaded: int = 0
    resumes_scored: int = 0
    resumes_improved: int = 0

    for s in students:
        progress = s.get("progress", {})
        status = progress.get("status", "not_started")
        status_counts[status] = status_counts.get(status, 0) + 1

        if progress.get("has_resume"):
            resumes_uploaded += 1
        if progress.get("ats_score") is not None:
            ats_scores.append(progress["ats_score"])
            resumes_scored += 1
        if progress.get("tailored_count", 0) > 0:
            resumes_improved += 1

    avg_score = round(sum(ats_scores) / len(ats_scores), 1) if ats_scores else None

    return CohortStatsResponse(
        total_students=len(students),
        resumes_uploaded=resumes_uploaded,
        resumes_scored=resumes_scored,
        resumes_improved=resumes_improved,
        average_ats_score=avg_score,
        status_breakdown=status_counts,
    )


@router.get("/cohorts/{cohort_id}/leaderboard")
async def get_leaderboard(cohort_id: str):
    """Get student leaderboard ranked by ATS score."""
    cohort = db.get_cohort(cohort_id)
    if not cohort:
        raise HTTPException(status_code=404, detail="Cohort not found")

    students = db.get_cohort_students_progress(cohort_id)

    # Build entries and sort by ATS score (nulls last)
    entries = []
    for s in students:
        progress = s.get("progress", {})
        entries.append({
            "user_id": s["user_id"],
            "name": s["name"],
            "email": s.get("email"),
            "ats_score": progress.get("ats_score"),
            "resume_filename": progress.get("resume_filename"),
            "tailored_count": progress.get("tailored_count", 0),
            "status": progress.get("status", "not_started"),
        })

    # Sort: scored students first (by score desc), then unscored
    scored = [e for e in entries if e["ats_score"] is not None]
    unscored = [e for e in entries if e["ats_score"] is None]
    scored.sort(key=lambda x: x["ats_score"] or 0, reverse=True)

    ranked = []
    for i, entry in enumerate(scored + unscored, 1):
        ranked.append({"rank": i, **entry})

    return {"cohort": cohort, "leaderboard": ranked}


# ─── Executive Report ─────────────────────────────────────────────────────────

@router.get("/cohorts/{cohort_id}/report")
async def get_executive_report(cohort_id: str):
    """Get executive report data for leadership (directors, VCs).

    Returns funnel metrics, before/after ATS score averages,
    top 10 performers, and aggregated skill gaps.
    """
    cohort = db.get_cohort(cohort_id)
    if not cohort:
        raise HTTPException(status_code=404, detail="Cohort not found")

    students = db.get_cohort_students_progress(cohort_id)
    total = len(students)

    # ── Funnel ──
    enrolled = total
    uploaded = sum(1 for s in students if s.get("progress", {}).get("has_resume"))
    scored = sum(1 for s in students if s.get("progress", {}).get("ats_score") is not None)
    improved = sum(1 for s in students if s.get("progress", {}).get("tailored_count", 0) > 0)

    funnel = [
        {"stage": "Enrolled", "count": enrolled, "pct": 100},
        {"stage": "Uploaded Resume", "count": uploaded, "pct": round(uploaded / max(total, 1) * 100)},
        {"stage": "ATS Scored", "count": scored, "pct": round(scored / max(total, 1) * 100)},
        {"stage": "Improved Resume", "count": improved, "pct": round(improved / max(total, 1) * 100)},
    ]

    # ── Before / After Scores ──
    initial_scores = []
    improved_scores = []
    for s in students:
        progress = s.get("progress", {})
        ats = progress.get("ats_score")
        if ats is not None:
            initial_scores.append(ats)
        # If the student has tailored resumes, treat their ATS score as "improved"
        if ats is not None and progress.get("tailored_count", 0) > 0:
            improved_scores.append(ats)

    avg_initial = round(sum(initial_scores) / len(initial_scores), 1) if initial_scores else None
    avg_improved = round(sum(improved_scores) / len(improved_scores), 1) if improved_scores else None

    score_growth = {
        "average_initial_score": avg_initial,
        "average_improved_score": avg_improved,
        "total_scored": len(initial_scores),
        "total_improved": len(improved_scores),
        "score_distribution": {
            "excellent_90_plus": sum(1 for s in initial_scores if s >= 90),
            "good_75_89": sum(1 for s in initial_scores if 75 <= s < 90),
            "average_50_74": sum(1 for s in initial_scores if 50 <= s < 75),
            "needs_work_below_50": sum(1 for s in initial_scores if s < 50),
        },
    }

    # ── Journey Details for ALL Students ──
    all_students_journey = []
    for s in students:
        prog = s.get("progress", {})
        all_students_journey.append({
            "name": s["name"],
            "user_id": s["user_id"],
            "email": s.get("email"),
            "status": prog.get("status", "not_started"),
            "ats_score": prog.get("ats_score"),
            "tailored_count": prog.get("tailored_count", 0),
            "last_updated": prog.get("updated_at"),
        })
    
    # Sort journey: Scored first (desc), then processing, then not started
    def journey_sort(x):
        status = x["status"]
        if status == "ready": return (0, -(x["ats_score"] or 0))
        if status == "processing": return (1, 0)
        return (2, 0)
    
    all_students_journey.sort(key=journey_sort)

    # ── Top Performers ──
    top_performers = [s for s in all_students_journey if s["ats_score"] is not None]
    top_performers = sorted(top_performers, key=lambda x: x["ats_score"], reverse=True)[:10]

    # ── Skill Gaps (Enhanced) ──
    skill_gap_counts: dict[str, int] = {}
    for s in students:
        breakdown = s.get("progress", {}).get("ats_breakdown")
        if breakdown and isinstance(breakdown, dict):
            for key, value in breakdown.items():
                if isinstance(value, (int, float)) and value < 60:
                    readable_key = key.replace("_", " ").title()
                    skill_gap_counts[readable_key] = skill_gap_counts.get(readable_key, 0) + 1

    skill_gaps = [
        {"skill": k, "students_affected": v}
        for k, v in sorted(skill_gap_counts.items(), key=lambda x: x[1], reverse=True)
    ][:10]

    return {
        "cohort": cohort,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "summary": {
            "total_students": total,
            "engagement_rate": round(uploaded / max(total, 1) * 100),
            "completion_rate": round(improved / max(total, 1) * 100),
        },
        "funnel": funnel,
        "score_growth": score_growth,
        "top_performers": top_performers,
        "all_students": all_students_journey,
        "skill_gaps": skill_gaps,
    }
