import logging
from typing import Optional
from fastapi import Header
from app.database import db

logger = logging.getLogger(__name__)

def get_current_user(x_user_id: Optional[str] = Header(None, alias="X-User-ID")) -> Optional[str]:
    """
    Extract the X-User-ID from the incoming request headers.
    Auto-provisions the user in the database if they don't exist yet,
    to avoid Foreign Key constraint errors on PostgreSQL.
    """
    if x_user_id:
        logger.info(f"Checking user record for X-User-ID: {x_user_id}")
        user = db.get_user(x_user_id)
        if not user:
            logger.info(f"User {x_user_id} not found. Auto-provisioning basic user record.")
            try:
                db.create_user(
                    name=f"User {x_user_id}", 
                    email=f"{x_user_id}@demo.com",
                    user_id=x_user_id
                )
                logger.info(f"Successfully auto-provisioned user {x_user_id}")
            except Exception as e:
                logger.error(f"Failed to auto-provision user {x_user_id}: {e}")
                # We don't raise here to allow the primary request to attempt to proceed
                # though it will likely fail with a Foreign Key violation later.
        else:
            logger.debug(f"User {x_user_id} already exists.")
    else:
        logger.warning("No X-User-ID header provided in request.")
    return x_user_id
