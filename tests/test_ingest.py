from datetime import datetime, timezone
from types import SimpleNamespace

from tests.conftest import SUMMARY
from wordle_bot import config
from wordle_bot.ingest import ingest_message

POSTED = datetime(2026, 10, 18, 14, 0, tzinfo=timezone.utc)


def fake_message(content, author_id=1, channel_id=10, message_id=20, guild_id=5, bot=True):
    return SimpleNamespace(
        author=SimpleNamespace(id=author_id, bot=bot), content=content, created_at=POSTED,
        guild=SimpleNamespace(id=guild_id), channel=SimpleNamespace(id=channel_id), id=message_id)


def count(conn):
    return conn.execute("SELECT COUNT(*) FROM results").fetchone()[0]


def test_ingest_summary(conn):
    assert ingest_message(conn, fake_message(SUMMARY)) == 1946
    assert count(conn) == 4


def test_ingest_ignores_non_summary(conn):
    assert ingest_message(conn, fake_message("Wordle: \nSlicck was playing")) is None
    assert count(conn) == 0


def test_ingest_ignores_wrong_author(conn, monkeypatch):
    monkeypatch.setattr(config, "WORDLE_AUTHOR_ID", 999)
    assert ingest_message(conn, fake_message(SUMMARY, author_id=1)) is None


def test_ingest_same_summary_twice(conn):
    ingest_message(conn, fake_message(SUMMARY, channel_id=10, message_id=20))
    ingest_message(conn, fake_message(SUMMARY, channel_id=11, message_id=21))
    assert count(conn) == 4


def test_ingest_ignores_human_when_author_id_unset(conn, monkeypatch):
    monkeypatch.setattr(config, "WORDLE_AUTHOR_ID", None)
    assert ingest_message(conn, fake_message(SUMMARY, author_id=777, bot=False)) is None
    assert count(conn) == 0
