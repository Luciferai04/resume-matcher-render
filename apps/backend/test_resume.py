import asyncio
import traceback
from app.database import db

async def run():
    print("Testing create user...")
    try:
        user = db.create_user(name="Test", email="test@test.com", user_id="test1234")
        print("User:", user)
    except Exception as e:
        print("CREATE USER ERROR:", type(e), str(e))
        
    print("Testing create resume...")
    try:
        resume = await db.create_resume_atomic_master(
            content="test content",
            content_type="md",
            filename="test.pdf",
            user_id="test1234"
        )
        print("Resume created:", resume["resume_id"])
        
        # Now try to update it inline as bulk_upload_resumes does
        updates = {
            "processed_data": {"skills": ["Python"]},
            "processing_status": "ready"
        }
        print("Testing update resume...")
        updated = db.update_resume(resume["resume_id"], updates, user_id="test1234")
        print("Update success:", updated["processing_status"])
        
    except Exception as e:
        print("RESUME ERROR:", type(e), str(e))
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run())
