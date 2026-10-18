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
