import asyncio
from sqlmodel import Session, select
from app.database import db
from app.models import User, Cohort
from datetime import datetime

async def seed_data():
    print("Seeding multi-tenant data...")
    
    with Session(db.engine) as session:
        # Create a Cohort
        cohort = session.exec(select(Cohort).where(Cohort.name == "March 2026 Batch")).first()
        if not cohort:
            cohort = Cohort(
                cohort_id="cohort_march_2026",
                name="March 2026 Batch",
                start_date=datetime(2026, 3, 1)
            )
            session.add(cohort)
            print(f"Created Cohort: {cohort.name}")
        
        # Create Users
        users_to_create = [
            {"id": "student_001", "name": "Student 1", "email": "student1@example.com"},
            {"id": "student_002", "name": "Student 2", "email": "student2@example.com"},
            {"id": "student_003", "name": "Student 3", "email": "student3@example.com"},
            {"id": "admin_demo", "name": "Admin User", "email": "admin@example.com"},
        ]
        
        for u_data in users_to_create:
            user = session.exec(select(User).where(User.user_id == u_data["id"])).first()
            if not user:
                user = User(
                    user_id=u_data["id"],
                    name=u_data["name"],
                    email=u_data["email"],
                    cohort_id=cohort.cohort_id
                )
                session.add(user)
                print(f"Created User: {user.name} ({user.user_id})")
        
        session.commit()
    
    print("Seeding complete.")

if __name__ == "__main__":
    asyncio.run(seed_data())
