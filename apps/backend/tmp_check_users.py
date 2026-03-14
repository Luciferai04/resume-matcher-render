from app.database import db
from app.models import User
from sqlalchemy import select

def check_users():
    with db.get_session() as session:
        users = session.exec(select(User)).all()
        print(f"Total users: {len(users)}")
        for u in users:
            if u.name is None:
                print(f"User {u.user_id} has NULL name!")
            else:
                try:
                    u.name.lower().strip()
                except Exception as e:
                    print(f"User {u.user_id} name error: {e}")

if __name__ == "__main__":
    check_users()
