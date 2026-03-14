import asyncio
import traceback
from app.database import db
from app.services.parser import parse_resume_to_json

async def run():
    print("Testing parse_resume_to_json and full resume creation flow...")
    try:
        user = db.create_user(name="Worker Test", email="worker@test.com", user_id="worker123")
        with open("test.pdf", "rb") as f:
            content = f.read()

        from app.services.parser import parse_document
        markdown_content = await parse_document(content, "test.pdf")

        resume = await db.create_resume_atomic_master(
            content=markdown_content,
            content_type="md",
            filename="test.pdf",
            processing_status="processing",
            user_id="worker123",
        )
        print("Master resume created:", resume["resume_id"])

        # emulate inline try/except from admin.py
        processed_data = await parse_resume_to_json(markdown_content)
        db.update_resume(resume["resume_id"], {
            "processed_data": processed_data,
            "processing_status": "ready",
        }, user_id="worker123")
        
        print("Success inline update")
    except Exception as e:
        print("ERROR:", type(e), str(e))
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run())
