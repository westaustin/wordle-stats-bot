import logging
from collections.abc import Awaitable, Callable
from datetime import date, timedelta

import aiohttp

from wordle_bot import config
from wordle_bot.db import cached_answers, store_answer

log = logging.getLogger(__name__)

UNKNOWN_WORD = "?????"

Fetcher = Callable[[date], Awaitable[str | None]]


def date_for(wordle_no: int) -> date:
    return config.WORDLE_EPOCH + timedelta(days=wordle_no)


def make_fetcher(session: aiohttp.ClientSession) -> Fetcher:
    async def fetch(d: date) -> str | None:
        url = config.ANSWER_URL.format(date=d.isoformat())
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    log.warning("Answer fetch %s returned %s", url, resp.status)
                    return None
                word = (await resp.json(content_type=None)).get("solution")
        except Exception as e:  # network, timeout, bad JSON: show ????? and retry next time
            log.warning("Answer fetch %s failed: %s", url, e)
            return None
        return word if isinstance(word, str) and len(word) == 5 else None
    return fetch


async def get_answers(conn, nos: list[int], latest_no: int | None, fetch: Fetcher) -> dict[int, str | None]:
    """Answer words for the given Wordle #s. Days past `latest_no` are never fetched or shown."""
    safe = [n for n in nos if latest_no is not None and 0 <= n <= latest_no]
    found: dict[int, str | None] = {n: None for n in nos}
    found.update(cached_answers(conn, safe))
    for n in safe:
        if found[n] is None:
            word = await fetch(date_for(n))
            if not word:
                break  # NYT is failing; don't wait on a timeout for every remaining row
            found[n] = word.upper()
            store_answer(conn, n, found[n])
    return found
