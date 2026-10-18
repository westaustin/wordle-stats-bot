from dataclasses import dataclass

from wordle_bot import config
from wordle_bot.db import Result

DIST_KEYS = ["1", "2", "3", "4", "5", "6", "X"]


@dataclass(frozen=True)
class UserStats:
    played: int
    wins: int
    win_pct: float
    avg: float
    crowns: int
    current_streak: int
    best_streak: int
    best_score: int | None
    best_score_count: int
    distribution: dict[str, int]
    first_no: int | None
    last_no: int | None


@dataclass(frozen=True)
class LeaderRow:
    user_id: int
    stats: UserStats


def _streaks(results: list[Result], latest_no: int | None) -> tuple[int, int]:
    """Return (current, best) runs of consecutive solved Wordle numbers."""
    best = run = 0
    prev = None
    for r in sorted(results, key=lambda r: r.wordle_no):
        if r.guesses is None:
            run, prev = 0, None
            continue
        run = run + 1 if prev is not None and r.wordle_no == prev + 1 else 1
        prev = r.wordle_no
        best = max(best, run)
    current = run if latest_no is not None and prev == latest_no else 0
    return current, best


def compute_stats(results: list[Result], latest_no: int | None) -> UserStats:
    dist = {k: 0 for k in DIST_KEYS}
    for r in results:
        dist["X" if r.guesses is None else str(r.guesses)] += 1
    played = len(results)
    wins = played - dist["X"]
    scores = [config.FAIL_SCORE if r.guesses is None else r.guesses for r in results]
    solved = [r.guesses for r in results if r.guesses is not None]
    best = min(solved) if solved else None
    current, best_streak = _streaks(results, latest_no)
    nos = [r.wordle_no for r in results]
    return UserStats(
        played=played,
        wins=wins,
        win_pct=100 * wins / played if played else 0.0,
        avg=sum(scores) / played if played else 0.0,
        crowns=sum(r.crown for r in results),
        current_streak=current,
        best_streak=best_streak,
        best_score=best,
        best_score_count=solved.count(best) if best is not None else 0,
        distribution=dist,
        first_no=min(nos) if nos else None,
        last_no=max(nos) if nos else None,
    )


def leaderboard(by_user: dict[int, list[Result]], latest_no: int | None) -> list[LeaderRow]:
    rows = [LeaderRow(uid, compute_stats(rs, latest_no)) for uid, rs in by_user.items()]
    rows = [r for r in rows if r.stats.played >= config.MIN_GAMES]
    return sorted(rows, key=lambda r: (r.stats.avg, -r.stats.played))
