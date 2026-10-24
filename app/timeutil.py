"""Time zone helpers. Timestamps are stored in UTC; "days" are the user's local days."""

from datetime import date, datetime, time, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def resolve_tz(name: str | None) -> tzinfo:
    """IANA name such as "Europe/Berlin"; unknown or empty names fall back to UTC."""
    if not name:
        return timezone.utc
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.utc


def to_local(moment: datetime, tz: tzinfo) -> datetime:
    """Convert a stored timestamp (naive values are UTC) to the user's time zone."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(tz)


def local_day(moment: datetime, tz: tzinfo) -> date:
    return to_local(moment, tz).date()


def today_local(tz: tzinfo) -> date:
    return datetime.now(timezone.utc).astimezone(tz).date()


def day_start_utc(day: date, tz: tzinfo) -> datetime:
    """UTC instant at which the local `day` begins (use for DB range filters)."""
    return datetime.combine(day, time.min, tzinfo=tz).astimezone(timezone.utc)


def next_day_start_utc(day: date, tz: tzinfo) -> datetime:
    return day_start_utc(day + timedelta(days=1), tz)
