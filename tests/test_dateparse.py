from datetime import date

from wordle_bot.dateparse import parse_day, wordle_no_for_date

T = date(2026, 10, 18)


def test_parse_day_numbers():
    assert parse_day("1936", T) == 1936
    assert parse_day("#1936", T) == 1936


def test_parse_day_dates():
    for arg in ["oct 7", "October 7", "10/7", "2026-10-07", "10/7/2026"]:
        assert parse_day(arg, T) == 1936, arg


def test_parse_day_relative():
    assert parse_day("yesterday", T) == 1946
    assert parse_day("today", T) == 1947
    assert parse_day(None, T) == 1946
    assert parse_day("", T) == 1946


def test_parse_day_year_rollover():
    assert parse_day("dec 25", T) == wordle_no_for_date(date(2025, 12, 25))
    assert parse_day("oct 18", T) == 1947  # today counts as "on or before today"


def test_parse_day_rejects_garbage():
    for arg in ["13/45", "feb 30", "abc", "-5", "2020-01-01"]:  # last is before #0
        assert parse_day(arg, T) is None, arg
