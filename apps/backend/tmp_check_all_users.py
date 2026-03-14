from app.database import db, _unwrap_row
from app.models import User
from sqlalchemy import select

def check_all_users():
    with db.get_session() as session:
        users = session.exec(select(User)).all()
        null_names = []
        for u in users:
            unwrapped = _unwrap_row(u)
            if unwrapped.name is None:
                null_names.append(unwrapped.user_id)
        
        if null_names:
            print(f"Found {len(null_names)} users with NULL name: {null_names}")
        else:
            print("No users with NULL name found.")

if __name__ == "__main__":
    check_all_users()
