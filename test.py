import asyncio
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
        print("Resume:", resume)
    except Exception as e:
        print("CREATE RESUME ERROR:", type(e), str(e))
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run())
