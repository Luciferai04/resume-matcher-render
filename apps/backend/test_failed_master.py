import asyncio
import traceback
from app.database import db

async def run():
    print("Testing failed master replacement flow...")
    try:
        user = db.create_user(name="Fail Test", email="fail@test.com", user_id="fail123")
        
        # 1. create a failed master resume
        resume1 = await db.create_resume_atomic_master(
            content="bad content",
            content_type="md",
            filename="bad.pdf",
            processing_status="failed",
            user_id="fail123",
        )
        print("Created failed master:", resume1["resume_id"])
        
        # 2. Re-upload a master resume for the SAME user.
        # This will trigger the branch: if current_master and current_master.get("processing_status") == "failed":
        resume2 = await db.create_resume_atomic_master(
            content="good content",
            content_type="md",
            filename="good.pdf",
            processing_status="processing",
            user_id="fail123",
        )
        print("Successfully created replacement master:", resume2["resume_id"])

    except Exception as e:
        print("ERROR:", type(e), str(e))
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run())
