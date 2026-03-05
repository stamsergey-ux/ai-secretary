"""Utility functions."""
from __future__ import annotations

import os

CHAIRMAN_USERNAMES = set(
    u.strip().lower()
    for u in os.getenv("CHAIRMAN_USERNAMES", "").split(",")
    if u.strip()
)


def is_chairman(username: str | None) -> bool:
    if not username:
        return False
    return username.lower() in CHAIRMAN_USERNAMES
