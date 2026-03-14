from app.database import db, _unwrap_row
from app.models import User
from sqlalchemy import select

def check_users():
    with db.get_session() as session:
        users = session.exec(select(User)).all()
        print(f"Total entries: {len(users)}")
        for i, u in enumerate(users):
            unwrapped = _unwrap_row(u)
            print(f"[{i}] Original type: {type(u)}, Unwrapped type: {type(unwrapped)}")
            if unwrapped is None:
                print(f"[{i}] Unwrapped is None!")
                continue
            
            # Check if it has 'name'
            try:
                name = getattr(unwrapped, "name", "MISSING")
                print(f"[{i}] Name: {name}")
                if name is None:
                    print(f"[{i}] Name is explicitly NONE")
            except Exception as e:
                print(f"[{i}] Error accessing name: {e}")

if __name__ == "__main__":
    check_users()
