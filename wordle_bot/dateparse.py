import calendar
import re
from datetime import date, datetime, timedelta

from wordle_bot import config

DAY_HELP = ("Try `!day 1936`, `!day #1936`, `!day oct 7`, `!day 10/7`, "
            "`!day 2026-10-07`, `!day 10/7/2026`, or `!day yesterday`.")

MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
MONTHS |= {name.lower(): i for i, name in enumerate(calendar.month_abbr) if name}


def wordle_no_for_date(d: date) -> int:
    return (d - config.WORDLE_EPOCH).days


def today_et() -> date:
    return datetime.now(config.TZ).date()


def _recent(month: int, day: int, today: date) -> date | None:
    """Most recent month/day on or before today."""
    for year in (today.year, today.year - 1):
        try:
            d = date(year, month, day)
        except ValueError:
            continue
        if d <= today:
            return d
    return None


def _to_date(arg: str, today: date) -> date | None:
    try:
        if m := re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", arg):
            return date(int(m[1]), int(m[2]), int(m[3]))
        if m := re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", arg):
            return date(int(m[3]), int(m[1]), int(m[2]))
    except ValueError:
        return None
    if m := re.fullmatch(r"(\d{1,2})/(\d{1,2})", arg):
        return _recent(int(m[1]), int(m[2]), today)
    if (m := re.fullmatch(r"([a-z]+)\.?\s+(\d{1,2})", arg)) and m[1] in MONTHS:
        return _recent(MONTHS[m[1]], int(m[2]), today)
    return None


def parse_day(arg: str | None, today: date) -> int | None:
    """Turn a !day argument into a Wordle #. Empty means yesterday; unparseable gives None."""
    arg = (arg or "").strip().lower()
    if arg in ("", "yesterday"):
        return wordle_no_for_date(today - timedelta(days=1))
    if arg == "today":
        return wordle_no_for_date(today)
    if m := re.fullmatch(r"#?(\d{1,5})", arg):
        return int(m[1])
    d = _to_date(arg, today)
    if d is None:
        return None
    n = wordle_no_for_date(d)
    return n if n >= 0 else None
