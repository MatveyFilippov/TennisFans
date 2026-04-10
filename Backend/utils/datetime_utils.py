import settings
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo


UTC_TIMEZONE = ZoneInfo("UTC")


def __datetime_to_timezone(dt: datetime, tz: ZoneInfo):
    if dt.tzinfo == tz:
        return dt
    return dt.replace(tzinfo=tz) if dt.tzinfo is None else dt.astimezone(tz)


@lru_cache(maxsize=10_000)
def utc_datetime(dt: datetime) -> datetime:
    return __datetime_to_timezone(dt=dt, tz=UTC_TIMEZONE)


@lru_cache(maxsize=10_000)
def localize_datetime(dt: datetime) -> datetime:
    return __datetime_to_timezone(dt=dt, tz=settings.BACKEND_TIMEZONE)
