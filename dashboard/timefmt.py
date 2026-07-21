"""Display timestamps in Asia/Dhaka (UTC+6)."""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DHAKA = ZoneInfo("Asia/Dhaka")


def now_dhaka() -> datetime:
    return datetime.now(DHAKA)


def stamp_fs(dt: datetime | None = None) -> str:
    """Filesystem-safe stamp: 2026-07-22T01-49-00+0600"""
    d = (dt or now_dhaka()).astimezone(DHAKA)
    return d.strftime("%Y-%m-%dT%H-%M-%S%z")


def stamp_iso(dt: datetime | None = None) -> str:
    """ISO-8601 with Dhaka offset: 2026-07-22T01:49:00+06:00"""
    d = (dt or now_dhaka()).astimezone(DHAKA)
    return d.isoformat(timespec="seconds")


def format_dhaka(value: str | None) -> str:
    """Parse stored UTC/Z or offset stamp → human Dhaka string for UI."""
    if not value:
        return ""
    raw = str(value).strip()
    # Writer historically used 2026-07-21T17-57-55Z (hyphens in time)
    normalized = raw
    if normalized.endswith("Z") and normalized.count("-") >= 4:
        # 2026-07-21T17-57-55Z → 2026-07-21T17:57:55Z
        date_part, _, rest = normalized.partition("T")
        if rest:
            body = rest[:-1] if rest.endswith("Z") else rest
            parts = body.split("-")
            if len(parts) == 3 and all(p.isdigit() for p in parts):
                normalized = f"{date_part}T{parts[0]}:{parts[1]}:{parts[2]}Z"
    try:
        if normalized.endswith("Z"):
            dt = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local = dt.astimezone(DHAKA)
        return local.strftime("%Y-%m-%d %H:%M Asia/Dhaka")
    except ValueError:
        return raw
