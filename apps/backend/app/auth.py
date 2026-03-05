"""Authentication layer for Resume Matcher."""

from typing import Optional
from fastapi import Header
from app.database import db

def get_current_user(x_user_id: Optional[str] = Header(None, alias="X-User-ID")) -> Optional[str]:
    """
    Extract the X-User-ID from the incoming request headers.
    Auto-provisions the user in the database if they don't exist yet,
    to avoid Foreign Key constraint errors on PostgreSQL.
    """
    if x_user_id:
        user = db.get_user(x_user_id)
        if not user:
            # Auto-provision a basic user record for the MVP
            db.create_user(
                name=f"User {x_user_id}", 
                email=f"{x_user_id}@demo.com",
                user_id=x_user_id
            )
    return x_user_id
