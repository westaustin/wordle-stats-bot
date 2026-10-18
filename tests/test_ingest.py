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


def _member(uid, name, global_name=None, nick=None):
    return SimpleNamespace(id=uid, name=name, global_name=global_name, nick=nick)


PLAIN = ("Your group is on a 439 day streak! 🔥🔥🔥 Here are yesterday's results:\n"
         "👑 3/6: @OnlyTees\n4/6: @snowMAMA @That Good Kwat @Ghost")


def test_ingest_resolves_plain_text_names(conn):
    from wordle_bot.db import day_results
    msg = fake_message(PLAIN)
    msg.guild = SimpleNamespace(id=5, name="g", members=[
        _member(1, "onlytees"), _member(2, "snow", global_name="snowMAMA"),
        _member(3, "kwat", nick="That Good Kwat")])
    assert ingest_message(conn, msg) == 1946
    assert [(uid, r.guesses) for uid, r in day_results(conn, 5, 1946)] == [(1, 3), (2, 4), (3, 4)]


def test_ambiguous_name_is_skipped(conn):
    from wordle_bot.ingest import member_id_for
    guild = SimpleNamespace(name="g", members=[_member(1, "a", global_name="Sam"), _member(2, "b", global_name="Sam")])
    assert member_id_for(guild, "Sam") is None
    # a server nickname wins over someone else's global name
    guild.members.append(_member(3, "c", nick="Sam"))
    assert member_id_for(guild, "sam") == 3
