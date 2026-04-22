import settings
from datetime import datetime, tzinfo, timezone
from functools import lru_cache


def datetime_to_timezone(dt: datetime, tz: tzinfo):
    if dt.tzinfo == tz:
        return dt
    return dt.replace(tzinfo=tz) if dt.tzinfo is None else dt.astimezone(tz)


@lru_cache(maxsize=10_000)
def utc_datetime(dt: datetime) -> datetime:
    return datetime_to_timezone(dt=dt, tz=timezone.utc)


@lru_cache(maxsize=10_000)
def localize_datetime(dt: datetime) -> datetime:
    return datetime_to_timezone(dt=dt, tz=settings.PROJECT_TIMEZONE)
