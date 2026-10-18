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


def test_parse_day_leap_day_without_year():
    assert parse_day("feb 29", T) == wordle_no_for_date(date(2024, 2, 29))


def test_parse_day_more_forms():
    assert parse_day("sept 7", T) == wordle_no_for_date(date(2026, 9, 7))
    assert parse_day("oct 7th", T) == 1936
    assert parse_day("7 oct", T) == 1936
    assert parse_day("october 7 2025", T) == wordle_no_for_date(date(2025, 10, 7))
    assert parse_day("oct 7, 2025", T) == wordle_no_for_date(date(2025, 10, 7))


def test_day_help_lists_all_forms():
    from wordle_bot.dateparse import DAY_HELP
    for form in ["1936", "#1936", "oct 7", "october 7", "10/7", "2026-10-07", "10/7/2026", "yesterday", "today"]:
        assert f"`!day {form}`" in DAY_HELP, form
