from dataclasses import dataclass

from wordle_bot.db import Result


@dataclass(frozen=True)
class HistoryRow:
    wordle_no: int
    result: Result | None  # None = didn't play


def history_rows(results: list[Result], summary_days: set[int]) -> list[HistoryRow]:
    """Newest first. Missed days count only between the first and last game, on days the server has a summary."""
    if not results:
        return []
    by_no = {r.wordle_no: r for r in results}
    first, last = min(by_no), max(by_no)
    days = set(by_no) | {n for n in summary_days if first <= n <= last}
    return [HistoryRow(n, by_no.get(n)) for n in sorted(days, reverse=True)]


def page_count(n: int, size: int) -> int:
    return max(1, -(-n // size))


def paginate(rows: list, page: int, size: int) -> list:
    return rows[page * size:(page + 1) * size]
