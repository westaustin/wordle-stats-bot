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


def test_catch_up_point_requires_completed_backfill(conn, summary_lines):
    upsert_results(conn, 5, 1946, summary_lines, channel_id=10, message_id=900)
    assert catch_up_point(conn, 5) is None
    mark_backfill_complete(conn, 5)
    assert catch_up_point(conn, 5) == 900


def test_history_command_takes_user():
    assert botmod.history_cmd.clean_params["member"].annotation is discord.User
    assert "day" in [c.name for c in botmod.bot.commands]
