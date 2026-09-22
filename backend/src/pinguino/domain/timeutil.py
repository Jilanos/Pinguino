"""UTC discipline shared by every timestamped contract."""

from __future__ import annotations

from datetime import datetime


def require_utc(value: datetime) -> datetime:
    offset = value.utcoffset()
    if offset is None:
        raise ValueError("timestamp must declare a timezone")
    if offset.total_seconds() != 0:
        raise ValueError("timestamp must be UTC")
    return value
