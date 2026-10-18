from wordle_bot.db import Result
from wordle_bot.history import HistoryRow, history_rows, page_count, paginate


def test_history_rows_fills_missed_days_with_summaries():
    rs = [Result(10, 3, False), Result(13, 4, True), Result(14, None, False)]
    rows = history_rows(rs, {9, 10, 11, 13, 14, 15})
    assert [r.wordle_no for r in rows] == [14, 13, 11, 10]
    assert rows[2] == HistoryRow(11, None)
    assert rows[0].result == Result(14, None, False)


def test_history_rows_empty():
    assert history_rows([], {1, 2}) == []


def test_page_count():
    assert page_count(0, 10) == 1
    assert page_count(10, 10) == 1
    assert page_count(11, 10) == 2


def test_paginate():
    assert paginate(list(range(25)), 2, 10) == [20, 21, 22, 23, 24]
