from datetime import datetime, timezone, tzinfo
from functools import lru_cache
import settings


log = settings.ProjectLoggerFactory.get_for("utils.datetime")


@lru_cache(maxsize=10_000)
def datetime_to_timezone(dt: datetime, tz: tzinfo):
    if dt.tzinfo == tz:
        return dt
    return dt.replace(tzinfo=tz) if dt.tzinfo is None else dt.astimezone(tz)


def utc_datetime(dt: datetime) -> datetime:
    log.debug(f"Setting {dt.isoformat()} to utc")
    return datetime_to_timezone(dt=dt, tz=timezone.utc)


def localize_datetime(dt: datetime) -> datetime:
    log.debug(f"Localize {dt.isoformat()}")
    return datetime_to_timezone(dt=dt, tz=settings.PROJECT_TIMEZONE)
