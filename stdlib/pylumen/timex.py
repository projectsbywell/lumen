"""Time utilities for the Lumen standard library."""

import time
import datetime
import calendar
from typing import Optional, Tuple


def now() -> float:
    """Return current Unix timestamp (UTC)."""
    return time.time()


def now_utc() -> float:
    """Return current Unix timestamp (UTC)."""
    return time.time()


def from_timestamp(ts: float) -> datetime.datetime:
    """Convert Unix timestamp to datetime."""
    return datetime.datetime.fromtimestamp(ts)


def to_timestamp(dt: Optional[datetime.datetime] = None) -> float:
    """Convert datetime to Unix timestamp."""
    if dt is None:
        dt = datetime.datetime.now()
    return dt.timestamp()


def format_date(dt: Optional[datetime.datetime] = None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime as string."""
    if dt is None:
        dt = datetime.datetime.now()
    return dt.strftime(fmt)


def parse_date(s: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> datetime.datetime:
    """Parse date string to datetime."""
    return datetime.datetime.strptime(s, fmt)


def timedelta(seconds: float = 0, **kwargs) -> datetime.timedelta:
    """Create a timedelta (seconds + kwargs repassados a datetime.timedelta)."""
    return datetime.timedelta(seconds=seconds, **kwargs)


def date_add(dt: Optional[datetime.datetime], delta: datetime.timedelta) -> datetime.datetime:
    """Add timedelta to datetime."""
    if dt is None:
        dt = datetime.datetime.now()
    return dt + delta


def date_diff(dt1: datetime.datetime, dt2: datetime.datetime) -> datetime.timedelta:
    """Return timedelta between two datetimes."""
    return dt1 - dt2


def sleep(seconds: float) -> None:
    """Sleep for given seconds."""
    time.sleep(seconds)


def ldate(dt: Optional[datetime.datetime] = None) -> str:
    """Return date portion as string."""
    if dt is None:
        dt = datetime.datetime.now()
    return dt.strftime("%Y-%m-%d")


def ltime(dt: Optional[datetime.datetime] = None) -> str:
    """Return time portion as string."""
    if dt is None:
        dt = datetime.datetime.now()
    return dt.strftime("%H:%M:%S")


def ldatetime(dt: Optional[datetime.datetime] = None) -> str:
    """Return full datetime as string."""
    if dt is None:
        dt = datetime.datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def year(dt: Optional[datetime.datetime] = None) -> int:
    """Get year."""
    if dt is None:
        dt = datetime.datetime.now()
    return dt.year


def month(dt: Optional[datetime.datetime] = None) -> int:
    """Get month."""
    if dt is None:
        dt = datetime.datetime.now()
    return dt.month


def day(dt: Optional[datetime.datetime] = None) -> int:
    """Get day."""
    if dt is None:
        dt = datetime.datetime.now()
    return dt.day


def weekday(dt: Optional[datetime.datetime] = None) -> int:
    """Get weekday (0=Monday, 6=Sunday)."""
    if dt is None:
        dt = datetime.datetime.now()
    return dt.weekday()


def days_in_month(year: int, month: int) -> int:
    """Get number of days in a month."""
    return calendar.monthrange(year, month)[1]


def is_leap_year(year: int) -> bool:
    """Check if year is a leap year."""
    return calendar.isleap(year)
