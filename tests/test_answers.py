import asyncio
from datetime import date

from wordle_bot.answers import date_for, get_answers


class FakeFetch:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    async def __call__(self, d):
        self.calls.append(d)
        return self.responses.pop(0) if self.responses else None


def run(coro):
    return asyncio.run(coro)


def test_date_for():
    assert date_for(1936) == date(2026, 10, 7)
    assert date_for(0) == date(2021, 6, 19)


def test_get_answers_fetches_and_caches(conn):
    fetch = FakeFetch("prove")
    assert run(get_answers(conn, [1936], 1946, fetch)) == {1936: "PROVE"}
    assert run(get_answers(conn, [1936], 1946, fetch)) == {1936: "PROVE"}
    assert len(fetch.calls) == 1


def test_failed_fetch_not_cached(conn):
    fetch = FakeFetch(None, "prove")
    assert run(get_answers(conn, [1936], 1946, fetch)) == {1936: None}
    assert run(get_answers(conn, [1936], 1946, fetch)) == {1936: "PROVE"}


def test_get_answers_never_fetches_past_cutoff(conn):
    fetch = FakeFetch("crane", "never")
    out = run(get_answers(conn, [1946, 1947], 1946, fetch))
    assert out[1947] is None
    assert date_for(1947) not in fetch.calls
    fetch2 = FakeFetch("x")
    assert run(get_answers(conn, [1900], None, fetch2)) == {1900: None}
    assert fetch2.calls == []
