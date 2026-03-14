import asyncio
from app.database import db
from app.services.parser import parse_resume_to_json
from app.services.ats_scorer import calculate_ats_score
from app.services.improver import extract_job_keywords

async def test():
    user = db.create_user(name="Score Test 2", email="score2@test.com")
    uid = user["user_id"]
    job = db.create_job(content="Python, FastAPI, AWS", user_id=uid)
    jid = job["job_id"]
    
    with open("master.pdf", "rb") as f:
        content = f.read()
    
    from app.services.parser import parse_document
    md = await parse_document(content, "master.pdf")
    
    resume = await db.create_resume_atomic_master(
        content=md, filename="master.pdf", user_id=uid, processing_status="processing"
    )
    rid = resume["resume_id"]
    
    print("Running worker task logic for resume", rid)
    try:
        processed_data = await parse_resume_to_json(resume["content"])
        
        updates = {
            "processed_data": processed_data,
            "processing_status": "ready",
        }

        keywords = job.get("job_keywords")
        if not keywords:
            keywords = await extract_job_keywords(job["content"])
            db.update_job(jid, {"job_keywords": keywords})

        ats_result = await calculate_ats_score(
            resume_data=processed_data,
            job_description=job["content"],
            job_keywords=keywords or {},
        )
        if ats_result:
            updates["ats_score"] = ats_result.get("totalScore") or ats_result.get("overall_score")
            updates["ats_breakdown"] = ats_result.get("breakdown")

        print("Updates to save:", updates)
        db.update_resume(rid, updates)
        print("Task completed successfully!")
    except Exception as e:
        print("Worker error:", repr(e))
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
