import pytest

from wordle_bot.db import Result
from wordle_bot.stats import compute_stats, leaderboard


def solves(*nos, guesses=4):
    return [Result(n, guesses, False) for n in nos]


def test_basic_numbers():
    rs = [Result(1, 3, True), Result(2, 4, False), Result(3, None, False)]
    s = compute_stats(rs, latest_no=3)
    assert s.played == 3
    assert s.wins == 2
    assert s.win_pct == pytest.approx(66.67, abs=0.01)
    assert s.avg == pytest.approx((3 + 4 + 7) / 3)
    assert s.crowns == 1
    assert (s.best_score, s.best_score_count) == (3, 1)
    assert s.distribution == {"1": 0, "2": 0, "3": 1, "4": 1, "5": 0, "6": 0, "X": 1}
    assert (s.first_no, s.last_no) == (1, 3)


def test_streaks():
    s = compute_stats(solves(1, 2, 3, 5, 6), latest_no=6)
    assert (s.best_streak, s.current_streak) == (3, 2)


def test_current_streak_zero_when_missed_latest():
    s = compute_stats(solves(1, 2), latest_no=3)
    assert (s.best_streak, s.current_streak) == (2, 0)


def test_fail_breaks_streak():
    rs = [Result(1, 3, False), Result(2, None, False), Result(3, 4, False)]
    s = compute_stats(rs, latest_no=3)
    assert (s.best_streak, s.current_streak) == (1, 1)


def test_empty():
    s = compute_stats([], None)
    assert s.played == 0
    assert s.avg == 0.0
    assert s.best_score is None


def test_leaderboard_min_games_and_order():
    a = [Result(n, 4, False) for n in range(20)]
    b = [Result(n, 3 if n % 2 else 4, False) for n in range(25)]
    c = [Result(n, 2, False) for n in range(5)]
    rows = leaderboard({1: a, 2: b, 3: c}, latest_no=24)
    assert [r.user_id for r in rows] == [2, 1]
