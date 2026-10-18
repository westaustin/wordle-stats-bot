import discord

from wordle_bot import config
from wordle_bot.answers import UNKNOWN_WORD, date_for
from wordle_bot.db import Result
from wordle_bot.history import HistoryRow
from wordle_bot.stats import DIST_KEYS, UserStats

GREEN = 0x6AAA64
MEDALS = ["🥇", "🥈", "🥉"]


def format_distribution(dist: dict[str, int], width: int = 15) -> str:
    top = max(dist.values(), default=0)
    lines = []
    for key in DIST_KEYS:
        count = dist.get(key, 0)
        blocks = max(1, round(count / top * width)) if count else 0
        lines.append(f"{key} {'█' * blocks} {count}")
    return "```\n" + "\n".join(lines) + "\n```"


def stats_embed(name: str, s: UserStats) -> discord.Embed:
    e = discord.Embed(title=f"🟩 {name} — Wordle Stats", color=GREEN)
    if s.played == 0:
        e.description = "No Wordle results yet."
        return e
    best = f"{s.best_score}/6 (×{s.best_score_count})" if s.best_score else "—"
    for label, value in [
        ("Played", s.played),
        ("Win %", f"{s.win_pct:.0f}%"),
        ("Avg Guesses", f"{s.avg:.2f}"),
        ("👑 Crowns", s.crowns),
        ("Current Streak", f"🔥 {s.current_streak}"),
        ("Best Streak", s.best_streak),
        ("Best Score", best),
    ]:
        e.add_field(name=label, value=str(value), inline=True)
    e.add_field(name="Guess Distribution", value=format_distribution(s.distribution), inline=False)
    e.set_footer(text=f"Wordle #{s.first_no} – #{s.last_no}")
    return e


def leaderboard_embed(rows: list[tuple[str, UserStats]]) -> discord.Embed:
    e = discord.Embed(title="🏆 Server Wordle Leaderboard", color=GREEN)
    e.set_footer(text=f"Ranked by average guesses · min {config.MIN_GAMES} games")
    if not rows:
        e.description = f"No one has {config.MIN_GAMES} games yet."
        return e
    table = [f"{'#':<3}{'Player':<16}{'Avg':>5}{'Played':>7}{'👑':>4}{'Streak':>7}"]
    for i, (name, s) in enumerate(rows):
        rank = MEDALS[i] if i < len(MEDALS) else f"{i + 1}."
        table.append(f"{rank:<3}{name[:15]:<16}{s.avg:>5.2f}{s.played:>7}"
                     f"{s.crowns:>4}{s.current_streak:>7}")
    e.description = "```\n" + "\n".join(table) + "\n```"
    return e


def _short_date(wordle_no: int) -> str:
    d = date_for(wordle_no)
    return f"{d:%b} {d.day}"


def format_score(r: Result) -> str:
    score = "X/6" if r.guesses is None else f"{r.guesses}/6"
    return f"{score} 👑" if r.crown else score


def history_embed(name: str, rows: list[HistoryRow], words: dict[int, str | None],
                  page: int, pages: int) -> discord.Embed:
    e = discord.Embed(title=f"📜 {name} — Recent Wordles", color=GREEN)
    if not rows:
        e.description = "No Wordle results yet."
        return e
    lines = []
    for row in rows:
        word = words.get(row.wordle_no) or UNKNOWN_WORD
        score = format_score(row.result) if row.result else "didn't play"
        lines.append(f"#{row.wordle_no} · {_short_date(row.wordle_no)} · {word} · {score}")
    e.description = "\n".join(lines)
    e.set_footer(text=f"Page {page + 1} / {pages}")
    return e


def day_embed(wordle_no: int, word: str | None, entries: list[tuple[str, Result]]) -> discord.Embed:
    e = discord.Embed(title=f"Wordle #{wordle_no} · {_short_date(wordle_no)} · {word or UNKNOWN_WORD}",
                      color=GREEN)
    if not entries:
        e.description = "No results recorded for this day."
        return e
    ranked = sorted(entries, key=lambda e: (e[1].guesses is None, e[1].guesses or 0, e[0].lower()))
    e.description = "\n".join(f"{format_score(r)} {name}" for name, r in ranked)
    return e
