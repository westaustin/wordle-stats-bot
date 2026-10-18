import asyncio
import re
from types import SimpleNamespace

import discord

from wordle_bot import views
from wordle_bot.views import PagerButton, day_view, history_view, pager_states


class Recorder:
    def __init__(self):
        self.calls = []

    async def send_message(self, *args, **kwargs):
        self.calls.append(("send_message", args, kwargs))

    async def defer(self, *args, **kwargs):
        self.calls.append(("defer", args, kwargs))

    async def edit_original_response(self, *args, **kwargs):
        self.calls.append(("edit_original_response", args, kwargs))


def _interaction(resp, user_id=1):
    return SimpleNamespace(user=SimpleNamespace(id=user_id), response=resp,
                           edit_original_response=resp.edit_original_response)


def _rebuilt(button):
    """What discord.py hands the bot when a button is pressed: a fresh item from the custom id alone."""
    custom_id = button.item.custom_id
    match = re.fullmatch(PagerButton.__discord_ui_compiled_template__, custom_id)
    return asyncio.run(PagerButton.from_custom_id(None, None, match))


def test_pager_states_single_page():
    assert pager_states(0, 1) == (True, True, True, True)


def test_pager_states_middle_and_ends():
    assert pager_states(1, 3) == (False, False, False, False)
    assert pager_states(0, 3) == (True, True, False, False)
    assert pager_states(2, 3) == (False, False, True, True)


def test_buttons_never_time_out():
    assert history_view(1, 42, 0, 3).timeout is None
    assert day_view(1, 1946, 1946).timeout is None


def test_history_buttons_carry_their_destination():
    view = history_view(owner_id=1, user_id=42, page=1, pages=5)
    assert [b.item.label for b in view.children] == ["⏮", "◀", "▶", "⏭"]
    assert [b.item.disabled for b in view.children] == [False, False, False, False]
    assert [_rebuilt(b).position for b in view.children] == [0, 0, 2, 4]
    pressed = _rebuilt(view.children[2])
    assert (pressed.kind, pressed.owner_id, pressed.subject) == ("h", 1, 42)
    assert len({b.item.custom_id for b in view.children}) == 4  # Discord requires unique ids


def test_history_buttons_at_ends():
    assert [b.item.disabled for b in history_view(1, 42, 0, 3).children] == [True, True, False, False]
    assert [b.item.disabled for b in history_view(1, 42, 2, 3).children] == [False, False, True, True]


def test_day_view_bounds():
    prev1, next1 = day_view(owner_id=1, wordle_no=1946, latest_no=1946).children
    assert next1.item.disabled and not prev1.item.disabled
    assert prev1.item.label == "◀ #1945"
    assert _rebuilt(prev1).position == 1945
    assert day_view(owner_id=1, wordle_no=0, latest_no=1946).children[0].item.disabled


def test_button_rejects_other_users():
    resp = Recorder()
    ok = asyncio.run(_rebuilt(history_view(1, 42, 0, 3).children[2]).interaction_check(_interaction(resp, 2)))
    assert ok is False
    name, args, kwargs = resp.calls[0]
    assert name == "send_message" and kwargs.get("ephemeral") is True
    assert "Run the command yourself to browse." in (args[0] if args else kwargs.get("content"))


def test_press_after_restart_renders_its_page(monkeypatch):
    seen = []

    async def handler(interaction, owner, subject, position):
        seen.append((owner, subject, position))
        return f"page {position}", None

    monkeypatch.setitem(views.HANDLERS, "h", handler)
    button = _rebuilt(history_view(1, 42, 0, 3).children[2])  # ▶ rebuilt with no prior state
    resp = Recorder()
    assert asyncio.run(button.interaction_check(_interaction(resp))) is True
    asyncio.run(button.callback(_interaction(resp)))
    assert seen == [(1, 42, 1)]
    assert [c[0] for c in resp.calls] == ["defer", "edit_original_response"]
    assert resp.calls[1][2] == {"embed": "page 1", "view": None}


def test_failed_defer_skips_render(monkeypatch):
    rendered = []

    async def handler(*args):
        rendered.append(args)

    class FailingDefer(Recorder):
        async def defer(self, *args, **kwargs):
            raise discord.HTTPException(SimpleNamespace(status=404, reason="Not Found"), "Unknown interaction")

    monkeypatch.setitem(views.HANDLERS, "h", handler)
    asyncio.run(_rebuilt(history_view(1, 42, 0, 3).children[2]).callback(_interaction(FailingDefer())))
    assert rendered == []
