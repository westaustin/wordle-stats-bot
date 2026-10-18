from wordle_bot.db import Result
from wordle_bot.embeds import format_distribution, leaderboard_embed, stats_embed
from wordle_bot.stats import compute_stats


def _bar_lines(text):
    return {l.split()[0]: l for l in text.strip("`\n").splitlines()}


def test_format_distribution():
    out = format_distribution({"1": 0, "2": 2, "3": 10, "4": 5, "5": 0, "6": 1, "X": 0})
    assert out.startswith("```") and out.endswith("```")
    lines = _bar_lines(out)
    assert lines["3"].count("█") == 15
    assert lines["6"].count("█") >= 1
    assert lines["1"].count("█") == 0
    assert list(lines) == ["1", "2", "3", "4", "5", "6", "X"]


def test_stats_embed_fields():
    s = compute_stats([Result(1, 3, True), Result(2, None, False)], latest_no=2)
    e = stats_embed("OnlyTees", s)
    assert "OnlyTees" in e.title
    names = [f.name for f in e.fields]
    assert "Played" in names and "Guess Distribution" in names


def test_stats_embed_no_games():
    e = stats_embed("Slicck", compute_stats([], None))
    assert e.description == "No Wordle results yet."
    assert e.fields == []


def test_leaderboard_embed_medals():
    s = compute_stats([Result(1, 3, False)], latest_no=1)
    e = leaderboard_embed([("a", s), ("b", s), ("c", s)])
    d = e.description
    assert d.index("🥇") < d.index("🥈") < d.index("🥉")
    assert leaderboard_embed([]).description == "No one has 20 games yet."


def test_history_embed_row_format():
    from wordle_bot.embeds import history_embed
    from wordle_bot.history import HistoryRow
    rows = [HistoryRow(1946, Result(1946, 4, True)), HistoryRow(1943, None)]
    e = history_embed("OnlyTees", rows, {1946: "CRANE", 1943: None}, page=0, pages=3)
    assert "#1946 · Oct 17 · CRANE · 4/6 👑" in e.description
    assert "#1943 · Oct 14 · ????? · didn't play" in e.description
    assert e.footer.text == "Page 1 / 3"


def test_day_embed_order_and_title():
    from wordle_bot.embeds import day_embed
    e = day_embed(1936, "PROVE", [("a", Result(1936, 6, False)), ("b", Result(1936, 4, True)),
                                  ("c", Result(1936, None, False))])
    assert e.title == "Wordle #1936 · Oct 7 · PROVE"
    lines = e.description.splitlines()
    assert [l.split()[-1] for l in lines] == ["b", "a", "c"]
    assert "👑" in lines[0]
    assert day_embed(1936, None, []).description == "No results recorded for this day."
