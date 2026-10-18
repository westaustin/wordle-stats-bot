import asyncio
from types import SimpleNamespace

import discord

from tests.conftest import SUMMARY
from wordle_bot import bot as botmod
from wordle_bot.bot import backfill, catch_up_point, display_name, user_label
from wordle_bot.db import mark_backfill_complete, upsert_results

READABLE = SimpleNamespace(read_message_history=True)


def test_display_name_fallback():
    gone = SimpleNamespace(get_member=lambda uid: None)
    assert display_name(gone, 42) == "Former member (42)"
    here = SimpleNamespace(get_member=lambda uid: SimpleNamespace(display_name="snowMAMA"))
    assert display_name(here, 42) == "snowMAMA"


def test_user_label_for_departed_user():
    gone = SimpleNamespace(get_member=lambda uid: None)
    assert user_label(gone, SimpleNamespace(id=42, name="Slicck")) == "Slicck"


def test_wordle_command_does_not_fall_back_to_caller():
    # Optional[Member] silently swallows a failed lookup and shows the caller's stats.
    assert botmod.wordle_cmd.clean_params["member"].annotation is discord.User


def _msg(mid):
    return SimpleNamespace(author=SimpleNamespace(id=1, bot=True), content=SUMMARY,
                           created_at=__import__("datetime").datetime(2026, 10, 18, 14, tzinfo=__import__("datetime").timezone.utc),
                           guild=SimpleNamespace(id=5), channel=SimpleNamespace(id=10), id=mid)


class FakeChannel:
    def __init__(self, name, messages=(), fail=False):
        self.name, self.messages, self.fail = name, list(messages), fail

    def permissions_for(self, me):
        return READABLE

    async def history(self, **kwargs):
        if self.fail:
            raise discord.HTTPException(SimpleNamespace(status=503, reason="Unavailable"), "boom")
        for m in self.messages:
            yield m

    async def archived_threads(self, **kwargs):
        return
        yield


def fake_guild(*channels):
    return SimpleNamespace(id=5, name="g", me=None, text_channels=list(channels),
                           voice_channels=[], threads=[])


def test_backfill_marks_complete_after_clean_pass(conn):
    asyncio.run(backfill(conn, fake_guild(FakeChannel("general", [_msg(100)]))))
    assert catch_up_point(conn, 5) == 100


def test_backfill_error_leaves_full_rescan_pending(conn):
    guild = fake_guild(FakeChannel("general", [_msg(100)]), FakeChannel("voice-chat", fail=True))
    asyncio.run(backfill(conn, guild))
    assert catch_up_point(conn, 5) is None  # next start does a full pass again


def test_backfill_logs_start_and_per_channel_progress(conn, caplog, monkeypatch):
    monkeypatch.setattr(botmod, "PROGRESS_EVERY", 2)
    noise = SimpleNamespace(author=SimpleNamespace(id=2, bot=False), content="hi", guild=SimpleNamespace(id=5))
    guild = fake_guild(FakeChannel("general", [noise, noise, _msg(100)]), FakeChannel("voice-chat", fail=True))
    with caplog.at_level("INFO", logger="wordle_bot.bot"):
        asyncio.run(backfill(conn, guild))
    lines = [r.getMessage() for r in caplog.records]
    assert "Backfill for g started (full scan, 2 channels)" in lines
    assert "  #general: 2 messages read so far, 0 summaries" in lines
    assert "  [1/2] #general: 3 messages, 1 summaries" in lines
    assert "  [2/2] #voice-chat: 0 messages, 0 summaries" in lines


def test_catch_up_point_requires_completed_backfill(conn, summary_lines):
    upsert_results(conn, 5, 1946, summary_lines, channel_id=10, message_id=900)
    assert catch_up_point(conn, 5) is None
    mark_backfill_complete(conn, 5)
    assert catch_up_point(conn, 5) == 900


def test_history_command_takes_user():
    assert botmod.history_cmd.clean_params["member"].annotation is discord.User
    assert "day" in [c.name for c in botmod.bot.commands]


def test_setup_logging_writes_utf8_file(tmp_path):
    import logging
    from wordle_bot.bot import setup_logging
    path = tmp_path / "bot.log"
    root = logging.getLogger()
    before = list(root.handlers)
    try:
        setup_logging(str(path))
        logging.getLogger("wordle_bot.test").warning("👑 4/6: <@1>")
        for h in root.handlers:
            h.flush()
        assert "👑 4/6" in path.read_text(encoding="utf-8")
    finally:
        for h in root.handlers[:]:
            if h not in before:
                root.removeHandler(h)
                h.close()
