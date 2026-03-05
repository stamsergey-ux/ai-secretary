"""Utility functions."""
from __future__ import annotations

import os

# Users with full admin access: chairman + controller (Виктория М)
ADMIN_USERNAMES = set(
    u.strip().lower()
    for u in os.getenv("CHAIRMAN_USERNAMES", "").split(",")
    if u.strip()
)


def is_chairman(username: str | None) -> bool:
    """Check if user has admin-level access (chairman or controller)."""
    if not username:
        return False
    return username.lower() in ADMIN_USERNAMES
