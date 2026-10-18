# Wordle History, Answers & Day Lookup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `!history [@user]` and `!day <number|date>` to the existing Wordle bot. Each shows the answer word next to scores and pages with Discord buttons.

**Architecture:** Pure modules handle date parsing, history-row building, and embeds. A cached answer lookup (SQLite plus an injected async fetcher) wraps the NYT endpoint. A small `views.py` holds the button paginators. `bot.py` wires the commands. Everything reuses the existing `Result`, `display_name`/`user_label`, and `latest_wordle_no`.

**Tech Stack:** Python 3.11+, discord.py 2.x (`discord.ui.View`), aiohttp (already a discord.py dependency), sqlite3, pytest.

**Spec:** `docs/superpowers/specs/2026-10-18-wordle-history-design.md`, which builds on `docs/superpowers/specs/2026-10-18-wordle-stats-bot-design.md`.

## Global Constraints

- Answer source: `https://www.nytimes.com/svc/wordle/v2/YYYY-MM-DD.json` → `solution`. Date = `WORDLE_EPOCH + wordle_no` days. Store uppercase.
- Cache answers forever. Never cache a failed fetch. Show `?????` when a word is unknown.
- Safe-to-show: a word is shown or fetched only if `0 <= wordle_no <= latest_wordle_no(guild)`. Anything past that gives `That day's results haven't posted yet.` and never fetches.
- Fetch lazily, only for the rows on the page being shown. Never bulk prefetch.
- `!history` rows: newest first, 10 per page, footer `Page N / M`. Row format is `#1946 · Oct 17 · CRANE · 4/6 👑`, or `#1943 · Oct 14 · TRAIN · didn't play`.
- "didn't play" rows only cover days between the user's first and last game where the server has a summary (anyone has a result for that #).
- `!history` buttons: ⏮ ◀ ▶ ⏭, disabled at the ends. `!day` buttons: `◀ #N-1` and `#N+1 ▶`. ▶ is disabled past the safe cutoff, and ◀ is disabled at #0.
- Only the command's invoker can press buttons. Anyone else gets an ephemeral `Run the command yourself to browse.` Views time out after 300 s and the buttons are then disabled. A press edits the same message.
- `!day` arguments: `1936`, `#1936`, `oct 7`, `october 7`, `10/7`, `2026-10-07`, `10/7/2026`, `yesterday`, and `today`. No argument means `yesterday`. A date without a year means the most recent past occurrence on or before today. "Today" is America/New_York.
- An unparseable `!day` argument gets a help reply listing the accepted forms.
- `!day` output: title `Wordle #1936 · Oct 7 · PROVE`, lines sorted best to worst with fails last, and 👑 on crown lines. With no results, it shows `No results recorded for this day.`
- `!history` on a bad or departed mention errors the same way `!wordle` does. No results gives `No Wordle results yet.`
- No new heavy dependencies. Keep TDD, real SQLite in tests, and constants in `config.py`.

## Review Focus

1. **A day past the cutoff** (`!day today`, `!day 99999`, or ▶ into tomorrow) replies "haven't posted yet" and never calls the fetcher. Pinned in Task 2 (`test_get_answers_never_fetches_past_cutoff`).
2. **NYT down or odd JSON** shows `?????`, is not cached, and is retried next time. Pinned in Task 2 (`test_failed_fetch_not_cached`).
3. **Garbage dates** (`13/45`, `feb 30`, `abc`, an empty string) parse to None, so the user gets help and nothing crashes. Pinned in Task 1 (`test_parse_day_rejects_garbage`).
4. **Someone other than the invoker** pressing a button gets an ephemeral rejection, and the page doesn't move. Pinned in Task 4 (`test_view_rejects_other_users`).
5. **A one-page history** has all four buttons disabled. Pinned in Task 4 (`test_pager_states_single_page`).

---

## File Structure

```
wordle_bot/
  dateparse.py   NEW  !day argument → Wordle #
  answers.py     NEW  date_for, fetch_answer (aiohttp), get_answers (cache + safe cutoff)
  history.py     NEW  HistoryRow, history_rows(), paginate()
  views.py       NEW  OwnedView base, HistoryView, DayView, pager_states()
  db.py          MOD  answers table + cache fns, summary_days(), day_results()
  embeds.py      MOD  history_embed(), day_embed()
  bot.py         MOD  aiohttp session lifecycle, !history, !day
tests/test_dateparse.py, test_answers.py, test_history.py, test_views.py (new); test_db.py, test_embeds.py (extend)
```

---

### Task 1: Day argument parsing

**Files:** Create `wordle_bot/dateparse.py` and `tests/test_dateparse.py`.

**Interfaces:**
- Consumes: `config.WORDLE_EPOCH`, `config.TZ`
- Produces:
  - `wordle_no_for_date(d: date) -> int`
  - `today_et() -> date`
  - `parse_day(arg: str | None, today: date) -> int | None`. Returns a Wordle #. `None`/empty means yesterday. Unparseable gives None.
  - `DAY_HELP: str`, which lists the accepted forms.

- [ ] **Step 1: Write failing tests** (`T = date(2026, 10, 18)`):

```python
def test_parse_day_numbers():
    assert parse_day("1936", T) == 1936
    assert parse_day("#1936", T) == 1936

def test_parse_day_dates():
    for arg in ["oct 7", "October 7", "10/7", "2026-10-07", "10/7/2026"]:
        assert parse_day(arg, T) == 1936, arg

def test_parse_day_relative():
    assert parse_day("yesterday", T) == 1946
    assert parse_day("today", T) == 1947
    assert parse_day(None, T) == 1946
    assert parse_day("", T) == 1946

def test_parse_day_year_rollover():
    assert parse_day("dec 25", T) == wordle_no_for_date(date(2025, 12, 25))
    assert parse_day("oct 18", T) == 1947   # today counts as "on or before today"

def test_parse_day_rejects_garbage():
    for arg in ["13/45", "feb 30", "abc", "-5", "2020-01-01"]:  # last is before #0
        assert parse_day(arg, T) is None, arg
```

- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_dateparse.py -q`. Expected: FAIL (ImportError).
- [ ] **Step 3: Implement.** Hand-rolled: lowercase and strip, then try `#?\d+` (≤ 5 digits is a Wordle #), ISO, `m/d[/y]`, and `month-name d` using `calendar.month_name`/`month_abbr`. Wrap `date()` construction in try/except ValueError → None. Reject a result < 0.
- [ ] **Step 4: Run.** Expected: 5 passed.
- [ ] **Step 5: Commit** `feat: parse !day arguments`.

---

### Task 2: Answer cache and fetch

**Files:** Create `wordle_bot/answers.py` and `tests/test_answers.py`. Modify `wordle_bot/db.py`, adding to the SCHEMA script: `CREATE TABLE IF NOT EXISTS answers (wordle_no INTEGER PRIMARY KEY, word TEXT NOT NULL)`. Extend `tests/test_db.py`.

**Interfaces:**
- Produces in `db.py`:
  - `cached_answers(conn, nos: list[int]) -> dict[int, str]`
  - `store_answer(conn, wordle_no: int, word: str) -> None`
- Produces in `answers.py`:
  - `ANSWER_URL = "https://www.nytimes.com/svc/wordle/v2/{date}.json"` (in `config.py`)
  - `UNKNOWN_WORD = "?????"`
  - `date_for(wordle_no: int) -> date`
  - `Fetcher = Callable[[date], Awaitable[str | None]]`
  - `make_fetcher(session: aiohttp.ClientSession) -> Fetcher`. GET with a 10 s timeout. Any exception, non-200 status, or missing or non-5-letter `solution` gives None.
  - `async get_answers(conn, nos: list[int], latest_no: int | None, fetch: Fetcher) -> dict[int, str | None]`. Numbers outside `0..latest_no` map to None and are never fetched. Cache hits come from the DB. Misses are fetched sequentially, and successes are uppercased and stored.

- [ ] **Step 1: Write failing tests.** Use a fake `fetch` that records calls.
  - `test_date_for`: `date_for(1936) == date(2026,10,7)` and `date_for(0) == date(2021,6,19)`.
  - `test_get_answers_fetches_and_caches`: fetch returns `"prove"`. The first call gives `{1936: "PROVE"}`. A second call gives the same result with zero new fetch calls.
  - `test_failed_fetch_not_cached`: fetch returns None the first time and `"prove"` the second. The first call gives `{1936: None}` and the second `{1936: "PROVE"}`.
  - `test_get_answers_never_fetches_past_cutoff`: `latest_no=1946`, nos `[1946, 1947]`. The result has 1947 → None, and the fetch call list doesn't contain `date_for(1947)`. With `latest_no=None`, everything is None and there are zero calls.
  - In `test_db.py`, `test_answer_cache_roundtrip`: storing then reading gives the word, and the cache doesn't contain unknown numbers.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_answers.py tests/test_db.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** No test touches the network. `make_fetcher` is exercised manually in Task 5.
- [ ] **Step 4: Run.** Expected: all pass.
- [ ] **Step 5: Commit** `feat: cached Wordle answer lookup`.

---

### Task 3: History rows, day results, embeds

**Files:** Create `wordle_bot/history.py` and `tests/test_history.py`. Modify `wordle_bot/db.py` and `wordle_bot/embeds.py`. Extend `tests/test_db.py` and `tests/test_embeds.py`.

**Interfaces:**
- Consumes: `Result` (db), `date_for`, `UNKNOWN_WORD` (Task 2)
- Produces:
  - `db.summary_days(conn, guild_id: int) -> set[int]`. Distinct Wordle #s with any result.
  - `db.day_results(conn, guild_id: int, wordle_no: int) -> list[tuple[int, Result]]`. Pairs of (user_id, Result).
  - `history.HISTORY_PAGE_SIZE = 10` (in config)
  - `@dataclass(frozen=True) history.HistoryRow(wordle_no: int, result: Result | None)`. `None` means didn't play.
  - `history.history_rows(results: list[Result], summary_days: set[int]) -> list[HistoryRow]`. Newest first.
  - `history.paginate(rows: list, page: int, size: int) -> list`
  - `history.page_count(n: int, size: int) -> int`. Minimum 1.
  - `embeds.history_embed(name: str, rows: list[HistoryRow], words: dict[int, str | None], page: int, pages: int) -> Embed`. `page` is 0-based and displays 1-based.
  - `embeds.day_embed(wordle_no: int, word: str | None, entries: list[tuple[str, Result]]) -> Embed`
  - `embeds.format_score(r: Result) -> str`. Gives `"4/6 👑"`, `"X/6"`.

- [ ] **Step 1: Write failing tests:**
  - `test_history_rows_fills_missed_days_with_summaries`: the user has #10, #13, and #14. summary_days is {9, 10, 11, 13, 14, 15}, with 12 having no summary. Rows are [14, 13, 11(None), 10]. That excludes 12 (no summary), 9 (before their first game), and 15 (after their last).
  - `test_history_rows_empty`: `history_rows([], {1, 2}) == []`.
  - `test_page_count`: `page_count(0, 10) == 1`, `page_count(10, 10) == 1`, `page_count(11, 10) == 2`.
  - `test_day_results` (db): after the conftest summary upsert at #1942, there are 4 entries and user 444's guesses are None.
  - `test_history_embed_row_format`: one row with Result(1946, 4, True) and words `{1946: "CRANE"}` gives a description containing `#1946 · Oct 17 · CRANE · 4/6 👑`. A None row with a None word contains `?????` and `didn't play`. The footer is `Page 1 / 3`.
  - `test_day_embed_order_and_title`: entries a=6, b=4👑, c=X give the title `Wordle #1936 · Oct 7 · PROVE`, with description line order b, a, c. No entries gives the description `No results recorded for this day.`
- [ ] **Step 2: Run** `.venv/bin/pytest -q`. Expected: the new tests FAIL.
- [ ] **Step 3: Implement.** For dates, use `f"{d:%b} {d.day}"` (no zero pad). Missed-day rows are numbers in `[min(user), max(user)]` ∩ summary_days that the user has no result for.
- [ ] **Step 4: Run.** Expected: all pass.
- [ ] **Step 5: Commit** `feat: history rows, day results, and their embeds`.

---

### Task 4: Button views

**Files:** Create `wordle_bot/views.py` and `tests/test_views.py`.

**Interfaces:**
- Produces:
  - `VIEW_TIMEOUT = 300` (config)
  - `pager_states(page: int, pages: int) -> tuple[bool, bool, bool, bool]`. The disabled flags for ⏮ ◀ ▶ ⏭.
  - `class OwnedView(discord.ui.View)`, built with `__init__(owner_id: int)`. `interaction_check` returns False and sends the ephemeral `Run the command yourself to browse.` for non-owners. `on_timeout` disables all children and edits `self.message` if it is set.
  - `class HistoryView(OwnedView)`, built with `__init__(owner_id, pages: int, render: Callable[[int], Awaitable[Embed]])`. It has four buttons. Each press updates `self.page`, re-applies `pager_states`, and runs `interaction.response.edit_message(embed=await render(page), view=self)`.
  - `class DayView(OwnedView)`, built with `__init__(owner_id, wordle_no: int, latest_no: int, render: Callable[[int], Awaitable[Embed]])`. It has two buttons, with labels refreshed to `◀ #{n-1}` / `#{n+1} ▶`. ◀ is disabled at 0, and ▶ when `n + 1 > latest_no`.
  - Long renders (up to 10 fetches) call `interaction.response.defer()` first, then `interaction.edit_original_response(...)`. Either is acceptable as long as the test fakes support it. Pick one and use it consistently.

- [ ] **Step 1: Write failing tests.** Construct views inside `asyncio.run` (View needs a running loop) and use SimpleNamespace interactions with async `response.send_message`/`edit_message` recorders.
  - `test_pager_states_single_page`: `pager_states(0, 1) == (True, True, True, True)`.
  - `test_pager_states_middle_and_ends`: (1, 3) gives all False. (0, 3) gives (True, True, False, False). (2, 3) gives (False, False, True, True).
  - `test_view_rejects_other_users`: owner 1 and interaction user 2 make `interaction_check` return False, with the ephemeral message sent.
  - `test_day_view_bounds`: DayView(wordle_no=1946, latest_no=1946) has ▶ disabled and ◀ labelled `◀ #1945`. DayView(wordle_no=0, …) has ◀ disabled.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_views.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run.** Expected: 4 passed.
- [ ] **Step 5: Commit** `feat: paginated button views`.

---

### Task 5: Wire `!history` and `!day`

**Files:** Modify `wordle_bot/bot.py` and `README.md`. Extend `tests/test_bot.py`.

**Interfaces:**
- Consumes: everything above, plus the existing `user_label`, `display_name`, `latest_wordle_no`, `user_results`.
- Produces:
  - In bot.py, `http_session: aiohttp.ClientSession | None`. It is created in `bot.setup_hook` and closed on `bot.close`. `fetcher = make_fetcher(http_session)`.
  - `!history [member: discord.User = None]`. It builds rows once, and `render(page)` runs `get_answers` for that page's numbers. It sends the page-0 embed with a `HistoryView` (no view when pages == 1 or there are no rows), then sets `view.message`.
  - `!day [*, arg: str = None]` (rest-of-message). It calls `parse_day(arg, today_et())`. None → `DAY_HELP`. `n > latest` or latest None → `That day's results haven't posted yet.` Otherwise `render(n)` runs `day_results` + `get_answers([n])` + `display_name`, and it sends with a `DayView`.
  - The `on_command_error` UserNotFound handling already covers `!history`.

- [ ] **Step 1: Write failing test** `test_history_command_takes_user`: `botmod.history_cmd.clean_params["member"].annotation is discord.User`, and `"day"` is in `[c.name for c in botmod.bot.commands]`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** Add both commands to the README command list.
- [ ] **Step 4: Run** `.venv/bin/pytest -q`. Expected: all pass.
- [ ] **Step 5: Manual network check.** Run `.venv/bin/python -c "import asyncio,aiohttp;from datetime import date;from wordle_bot.answers import make_fetcher\nasync def m():\n  async with aiohttp.ClientSession() as s: print(await make_fetcher(s)(date(2026,10,7)))\nasyncio.run(m())"`. Expected: `prove` (or `PROVE`).
- [ ] **Step 6: Commit** `feat: !history and !day commands`.
- [ ] **Step 7: Live check (Austin, after the bot runs).** `!history` shows words and pages with buttons, and someone else's click is rejected. `!day oct 7` shows PROVE with scores. `!day today` says it hasn't posted yet.
