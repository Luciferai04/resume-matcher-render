"""Authentication layer for Resume Matcher."""

from typing import Optional
from fastapi import Header

def get_current_user(x_user_id: Optional[str] = Header(None, alias="X-User-ID")) -> Optional[str]:
    """
    Extract the X-User-ID from the incoming request headers.
    Returns the user_id string if present, or None.
    If you want to enforce auth strictly, you could raise an HTTP 401 here.
    For this MVP, we return it optionally to allow existing tests/routes without header to fallback to None.
    """
    return x_user_id
