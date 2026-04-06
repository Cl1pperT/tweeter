from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def resolve_tzinfo(timezone_name: str):
    if timezone_name.startswith("/"):
        return datetime.now().astimezone().tzinfo
    return ZoneInfo(timezone_name)
