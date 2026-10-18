import sqlite3
from collections import defaultdict
from dataclasses import dataclass

from wordle_bot.parser import ParsedLine

SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
    guild_id   INTEGER NOT NULL,
    wordle_no  INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    guesses    INTEGER,          -- NULL = fail
    crown      INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    PRIMARY KEY (guild_id, wordle_no, user_id)
);
CREATE TABLE IF NOT EXISTS backfill_state (
    guild_id INTEGER PRIMARY KEY  -- present = a full history pass finished cleanly
);
"""


@dataclass(frozen=True)
class Result:
    wordle_no: int
    guesses: int | None
    crown: bool


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def upsert_results(conn, guild_id: int, wordle_no: int, lines: list[ParsedLine],
                   channel_id: int, message_id: int) -> int:
    rows = [(guild_id, wordle_no, uid, line.guesses, int(line.crown), channel_id, message_id)
            for line in lines for uid in line.user_ids]
    conn.executemany(
        """INSERT INTO results VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT (guild_id, wordle_no, user_id) DO UPDATE SET
             guesses = excluded.guesses, crown = excluded.crown,
             channel_id = excluded.channel_id, message_id = excluded.message_id""",
        rows,
    )
    conn.commit()
    return len(rows)


def user_results(conn, guild_id: int, user_id: int) -> list[Result]:
    cur = conn.execute(
        "SELECT wordle_no, guesses, crown FROM results "
        "WHERE guild_id = ? AND user_id = ? ORDER BY wordle_no",
        (guild_id, user_id),
    )
    return [Result(n, g, bool(c)) for n, g, c in cur]


def guild_results(conn, guild_id: int) -> dict[int, list[Result]]:
    by_user: dict[int, list[Result]] = defaultdict(list)
    cur = conn.execute(
        "SELECT user_id, wordle_no, guesses, crown FROM results "
        "WHERE guild_id = ? ORDER BY wordle_no",
        (guild_id,),
    )
    for uid, n, g, c in cur:
        by_user[uid].append(Result(n, g, bool(c)))
    return dict(by_user)


def latest_wordle_no(conn, guild_id: int) -> int | None:
    return conn.execute(
        "SELECT MAX(wordle_no) FROM results WHERE guild_id = ?", (guild_id,)
    ).fetchone()[0]


def has_any(conn, guild_id: int) -> bool:
    return conn.execute(
        "SELECT 1 FROM results WHERE guild_id = ? LIMIT 1", (guild_id,)
    ).fetchone() is not None


def latest_message_id(conn, guild_id: int) -> int | None:
    return conn.execute(
        "SELECT MAX(message_id) FROM results WHERE guild_id = ?", (guild_id,)
    ).fetchone()[0]


def mark_backfill_complete(conn, guild_id: int) -> None:
    conn.execute("INSERT OR IGNORE INTO backfill_state VALUES (?)", (guild_id,))
    conn.commit()


def backfill_complete(conn, guild_id: int) -> bool:
    return conn.execute(
        "SELECT 1 FROM backfill_state WHERE guild_id = ?", (guild_id,)
    ).fetchone() is not None
