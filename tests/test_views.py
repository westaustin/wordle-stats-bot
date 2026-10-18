import asyncio
from types import SimpleNamespace

from wordle_bot.views import DayView, HistoryView, pager_states


class Recorder:
    def __init__(self):
        self.calls = []

    async def send_message(self, *args, **kwargs):
        self.calls.append(("send_message", args, kwargs))

    async def defer(self, *args, **kwargs):
        self.calls.append(("defer", args, kwargs))

    async def edit_original_response(self, *args, **kwargs):
        self.calls.append(("edit_original_response", args, kwargs))


async def _render(n):
    return None


def test_pager_states_single_page():
    assert pager_states(0, 1) == (True, True, True, True)


def test_pager_states_middle_and_ends():
    assert pager_states(1, 3) == (False, False, False, False)
    assert pager_states(0, 3) == (True, True, False, False)
    assert pager_states(2, 3) == (False, False, True, True)


def test_view_rejects_other_users():
    async def go():
        view = HistoryView(owner_id=1, pages=3, render=_render)
        resp = Recorder()
        ok = await view.interaction_check(SimpleNamespace(user=SimpleNamespace(id=2), response=resp))
        return ok, resp.calls
    ok, calls = asyncio.run(go())
    assert ok is False
    name, args, kwargs = calls[0]
    assert name == "send_message" and kwargs.get("ephemeral") is True
    assert "Run the command yourself to browse." in (args[0] if args else kwargs.get("content"))


def test_owner_passes_check_and_paging_edits_message():
    async def go():
        view = HistoryView(owner_id=1, pages=3, render=_render)
        resp = Recorder()
        inter = SimpleNamespace(user=SimpleNamespace(id=1), response=resp,
                                edit_original_response=resp.edit_original_response)
        ok = await view.interaction_check(inter)
        await view.go_to(inter, 2)
        return ok, view, resp.calls
    ok, view, calls = asyncio.run(go())
    assert ok is True
    assert view.page == 2
    assert [c[0] for c in calls] == ["defer", "edit_original_response"]
    assert [b.disabled for b in view.children] == [False, False, True, True]


def test_day_view_bounds():
    async def go():
        v1 = DayView(owner_id=1, wordle_no=1946, latest_no=1946, render=_render)
        v2 = DayView(owner_id=1, wordle_no=0, latest_no=1946, render=_render)
        return v1, v2
    v1, v2 = asyncio.run(go())
    prev1, next1 = v1.children
    assert next1.disabled and not prev1.disabled
    assert prev1.label == "◀ #1945"
    assert v2.children[0].disabled
