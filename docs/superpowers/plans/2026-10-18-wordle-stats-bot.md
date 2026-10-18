# Wordle Stats Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Discord bot that reads the Wordle Activity's daily summary messages, stores each member's daily result, and answers `!wordle`, `!wordle @user`, and `!leaderboard` with Discord embeds.

**Architecture:** The pure parsing, stats, and formatting modules have no Discord dependency and are fully unit-tested. A SQLite layer stores one row per (guild, Wordle #, user). A thin discord.py layer ingests live messages, backfills channel history, and renders the embeds.

**Tech Stack:** Python 3.11+, discord.py 2.x, sqlite3 (stdlib), zoneinfo (stdlib), pytest, python-dotenv.

**Spec:** `docs/superpowers/specs/2026-10-18-wordle-stats-bot-design.md`

## Global Constraints

- Source is the daily summary text only. No image parsing, no avatar matching.
- Score line format: `N/6:` or `X/6:` (fail), optionally prefixed by 👑, followed by one or more mentions `<@id>` / `<@!id>`.
- Wordle #0 = 2021-06-19. Wordle # = (summary post date in America/New_York − 1 day) − 2021-06-19, in days. Sanity check: #1946 = 2026-10-17.
- One record per (guild, Wordle #, user). Re-ingest must not double-count.
- Unparseable lines are logged and skipped, never guessed.
- A fail counts as 7 in the average guesses.
- Streak = consecutive Wordle numbers solved. A fail or a missed day breaks it. The current streak is computed through the guild's latest Wordle # that has a summary.
- Everyone on the 👑 line gets a crown.
- Leaderboard: ranked by average guesses ascending, minimum 20 games, with columns rank, player, avg, played, crowns, current streak. The top 3 get 🥇🥈🥉.
- Output style is a Discord embed (mockup option A): text fields plus a monospace block-character bar chart.
- Austin's style: TDD, real SQLite in tests (no DB mocks), constants at the top of `config.py`.

## Review Focus

1. **Duplicate summaries.** Backfill re-run, or the same summary posted in two channels, must leave exactly one row per (guild, Wordle #, user). Pinned in Task 2 (`test_upsert_is_idempotent`) and Task 5 (`test_ingest_same_summary_twice`).
2. **Timezone near midnight.** A summary posted at 2026-10-18 03:30 UTC (= 23:30 ET on 10-17) must map to #1945, not #1946. Pinned in Task 1 (`test_wordle_number_uses_eastern_time`).
3. **User who left the server.** Stats and leaderboard must still render, with a fallback name. Pinned in Task 6 (`test_display_name_fallback`).
4. **No games yet.** `!wordle` from someone with no results returns a friendly message, not a crash or an empty embed. Pinned in Task 4 (`test_stats_embed_no_games`).
5. **Nickname mention form.** `<@!123>` parses the same as `<@123>`. Pinned in Task 1 (`test_parse_nickname_mentions`).

---

## File Structure

```
wordle_bot/
  __init__.py
  config.py     constants + env loading
  parser.py     summary text → ParsedSummary; post datetime → Wordle #
  db.py         SQLite schema, upsert, queries
  stats.py      results → UserStats; leaderboard rows
  embeds.py     UserStats / leaderboard → discord.Embed
  ingest.py     message-like object → parsed → db
  bot.py        discord.py client, commands, on_message, backfill
scripts/probe.py   one-off: print recent Wordle summaries (author id, raw text, date → #)
tests/             one test file per module
requirements.txt, .env.example, .gitignore, deploy/wordle-bot.service, README.md
```

---

### Task 1: Project scaffold, config, and parser

**Files:**
- Create: `.gitignore`, `requirements.txt`, `wordle_bot/__init__.py`, `wordle_bot/config.py`, `wordle_bot/parser.py`, `tests/test_parser.py`

**Interfaces:**
- Produces:
  - `config.WORDLE_EPOCH: date = date(2021, 6, 19)`, `config.TZ = ZoneInfo("America/New_York")`, `config.MIN_GAMES = 20`, `config.FAIL_SCORE = 7`, `config.SUMMARY_MARKER = "Here are yesterday's results"`, `config.DB_PATH` (env `WORDLE_DB_PATH`, default `"wordle.db"`), `config.DISCORD_TOKEN` (env), `config.WORDLE_AUTHOR_ID: int | None` (env `WORDLE_AUTHOR_ID`, optional)
  - `@dataclass(frozen=True) ParsedLine(guesses: int | None, crown: bool, user_ids: list[int])`. `guesses=None` means fail.
  - `@dataclass(frozen=True) ParsedSummary(lines: list[ParsedLine], skipped: list[str])`
  - `is_summary(text: str) -> bool`
  - `parse_summary(text: str) -> ParsedSummary`
  - `wordle_number_for(posted_at: datetime) -> int`. `posted_at` is tz-aware, as discord.py gives.

- [ ] **Step 1: Scaffold.** `git init`. Add a `.gitignore` covering `.venv/`, `.env`, `*.db`, `__pycache__/`, `.superpowers/`. Add `requirements.txt` with `discord.py>=2.4`, `python-dotenv>=1.0`, `pytest>=8`. Create a venv and install. Commit with `docs/` included: `chore: scaffold project with spec and plan`.

- [ ] **Step 2: Write failing tests** in `tests/test_parser.py`:

```python
from datetime import datetime, timezone
from wordle_bot.parser import parse_summary, is_summary, wordle_number_for

SUMMARY = ("Wordle: Your group is on a 432 day streak! 🔥🔥🔥 Here are yesterday's results:\n"
           "👑 4/6: <@111> <@222>\n6/6: <@333>\nX/6: <@444>")

def test_is_summary():
    assert is_summary(SUMMARY)
    assert not is_summary("Wordle: \nSlicck was playing")

def test_parse_lines():
    s = parse_summary(SUMMARY)
    assert [(l.guesses, l.crown, l.user_ids) for l in s.lines] == [
        (4, True, [111, 222]), (6, False, [333]), (None, False, [444])]
    assert s.skipped == []

def test_parse_nickname_mentions():
    s = parse_summary("Here are yesterday's results:\n3/6: <@!555>")
    assert s.lines[0].user_ids == [555]

def test_parse_skips_garbage_line():
    s = parse_summary("Here are yesterday's results:\n7/6: <@1>\n2/6: <@2>")
    assert [l.guesses for l in s.lines] == [2]
    assert s.skipped == ["7/6: <@1>"]

def test_wordle_number_known_day():
    assert wordle_number_for(datetime(2026, 10, 18, 14, 0, tzinfo=timezone.utc)) == 1946

def test_wordle_number_uses_eastern_time():
    # 03:30 UTC on 10-18 is 23:30 ET on 10-17, so "yesterday" is 10-16
    assert wordle_number_for(datetime(2026, 10, 18, 3, 30, tzinfo=timezone.utc)) == 1945
```

- [ ] **Step 3: Run** `pytest tests/test_parser.py -v`. Expected: FAIL (ImportError).

- [ ] **Step 4: Implement `config.py` and `parser.py`.** For the line regex, use `^(👑\s*)?([1-6X])/6:\s*(.+)$` per line, and pull mentions with `<@!?(\d+)>`. Skip the header line and blank lines silently. A line that contains `/6:` but fails the regex, or has no mentions, goes in `skipped` and is logged via `logging.getLogger(__name__).warning`.

- [ ] **Step 5: Run** `pytest tests/test_parser.py -v`. Expected: 6 passed.

- [ ] **Step 6: Commit** `feat: parse Wordle summary text and compute Wordle number`.

---

### Task 2: SQLite storage

**Files:**
- Create: `wordle_bot/db.py`, `tests/test_db.py`

**Interfaces:**
- Consumes: `ParsedLine` (Task 1)
- Produces:
  - `connect(path: str) -> sqlite3.Connection`. Creates the schema if it is missing.
  - `@dataclass(frozen=True) Result(wordle_no: int, guesses: int | None, crown: bool)`
  - `upsert_results(conn, guild_id: int, wordle_no: int, lines: list[ParsedLine], channel_id: int, message_id: int) -> int`. Returns the number of rows written.
  - `user_results(conn, guild_id: int, user_id: int) -> list[Result]`, ordered by `wordle_no`.
  - `guild_results(conn, guild_id: int) -> dict[int, list[Result]]`, keyed by user_id.
  - `latest_wordle_no(conn, guild_id: int) -> int | None`
  - `has_any(conn, guild_id: int) -> bool`

Schema: table `results(guild_id INTEGER, wordle_no INTEGER, user_id INTEGER, guesses INTEGER NULL, crown INTEGER, channel_id INTEGER, message_id INTEGER, PRIMARY KEY (guild_id, wordle_no, user_id))`. Upsert with `ON CONFLICT ... DO UPDATE`.

- [ ] **Step 1: Write failing tests.** Use a real SQLite file in pytest's `tmp_path`.
  - `test_upsert_and_read`: upsert the Task 1 SUMMARY lines for #1942. `user_results(conn, g, 111) == [Result(1942, 4, True)]`, and user 444 has `guesses is None`.
  - `test_upsert_is_idempotent`: upsert the same lines twice, then `SELECT COUNT(*)` gives 4.
  - `test_latest_wordle_no`: upsert #1940 and #1942. Latest is 1942. An empty guild gives None and `has_any` is False.
  - `test_guilds_isolated`: a row in guild 1 is not returned for guild 2.
- [ ] **Step 2: Run** `pytest tests/test_db.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement `db.py`.**
- [ ] **Step 4: Run.** Expected: 4 passed.
- [ ] **Step 5: Commit** `feat: sqlite storage for daily results`.

---

### Task 3: Stats

**Files:**
- Create: `wordle_bot/stats.py`, `tests/test_stats.py`

**Interfaces:**
- Consumes: `Result` (Task 2), `config.FAIL_SCORE`, `config.MIN_GAMES`
- Produces:
  - `@dataclass(frozen=True) UserStats(played: int, wins: int, win_pct: float, avg: float, crowns: int, current_streak: int, best_streak: int, best_score: int | None, best_score_count: int, distribution: dict[str, int], first_no: int | None, last_no: int | None)`. Distribution keys are `"1"`…`"6"` and `"X"`, all present.
  - `compute_stats(results: list[Result], latest_no: int | None) -> UserStats`
  - `@dataclass(frozen=True) LeaderRow(user_id: int, stats: UserStats)`
  - `leaderboard(by_user: dict[int, list[Result]], latest_no: int | None) -> list[LeaderRow]`. Filters to `played >= MIN_GAMES`, sorts by `avg` ascending, then `played` descending.

Streaks: walk the solved Wordle numbers in order. A run continues while each number is the previous number + 1 and was solved. The current streak is the run ending at `latest_no`, or 0 if the user did not solve `latest_no`.

- [ ] **Step 1: Write failing tests:**
  - `test_basic_numbers`: results #1 =3, #2 =4, #3 =fail (crown on #1). Expect played 3, wins 2, win_pct ≈ 66.7, avg = (3+4+7)/3, crowns 1, best_score 3 with count 1, distribution `{"3":1,"4":1,"X":1,...zeros}`, first_no 1, last_no 3.
  - `test_streaks`: solves #1, #2, #3, #5, #6, with latest_no 6. best 3, current 2.
  - `test_current_streak_zero_when_missed_latest`: solves #1, #2, latest_no 3. current 0, best 2.
  - `test_fail_breaks_streak`: #1 =3, #2 =fail, #3 =4, latest 3. current 1, best 1.
  - `test_empty`: `compute_stats([], None)` gives played 0, avg 0.0, best_score None.
  - `test_leaderboard_min_games_and_order`: user A has 20 games averaging 4, user B has 25 averaging 3.5, user C has 5 games averaging 2. Order is [B, A] and C is excluded.
- [ ] **Step 2: Run** `pytest tests/test_stats.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement `stats.py`.**
- [ ] **Step 4: Run.** Expected: 6 passed.
- [ ] **Step 5: Commit** `feat: compute per-user stats and leaderboard`.

---

### Task 4: Embeds

**Files:**
- Create: `wordle_bot/embeds.py`, `tests/test_embeds.py`

**Interfaces:**
- Consumes: `UserStats`, `LeaderRow` (Task 3)
- Produces:
  - `format_distribution(dist: dict[str, int], width: int = 15) -> str`. One line per key `1`…`6`, `X`, in the form `"{key} {bar} {count}"`. The bar is `"█" * round(count / max * width)`. A nonzero count always gets at least 1 block, and a zero count gets an empty bar. The output is wrapped in a ```` ``` ```` code block.
  - `stats_embed(name: str, s: UserStats) -> discord.Embed`
  - `leaderboard_embed(rows: list[tuple[str, UserStats]]) -> discord.Embed`. The caller resolves names.

Layout follows mockup A:
- Title: `🟩 {name} — Wordle Stats`, color `0x6AAA64`.
- Inline fields: Played, Win %, Avg Guesses (2 decimals), 👑 Crowns, Current Streak (`🔥 N`), Best Streak, Best Score (`"{n}/6 (×{count})"`).
- A non-inline "Guess Distribution" field holding `format_distribution`.
- Footer: `Wordle #{first_no} – #{last_no}`.

Leaderboard: title `🏆 Server Wordle Leaderboard`. The description is a code-block table, with 🥇🥈🥉 for the top 3 and `4.`, `5.`… after. Footer: `Ranked by average guesses · min 20 games`. With no rows, the description reads `No one has 20 games yet.`

- [ ] **Step 1: Write failing tests:**
  - `test_format_distribution`: given `{"1":0,"2":2,"3":10,"4":5,"5":0,"6":1,"X":0}`, line "3" has 15 blocks, line "6" has 2 (rounding 1.5 up via `round`; assert `>= 1`), and line "1" has 0 blocks.
  - `test_stats_embed_fields`: the embed title contains the name, and the field names include "Played" and "Guess Distribution".
  - `test_stats_embed_no_games`: played 0 returns an embed whose description is `"No Wordle results yet."` and has no fields.
  - `test_leaderboard_embed_medals`: three rows give a description containing 🥇, 🥈, and 🥉 in order. Zero rows give the empty message.
- [ ] **Step 2: Run** `pytest tests/test_embeds.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement `embeds.py`.**
- [ ] **Step 4: Run.** Expected: 4 passed.
- [ ] **Step 5: Commit** `feat: stats and leaderboard embeds`.

---

### Task 5: Ingest

**Files:**
- Create: `wordle_bot/ingest.py`, `tests/test_ingest.py`

**Interfaces:**
- Consumes: `is_summary`, `parse_summary`, `wordle_number_for` (Task 1); `upsert_results` (Task 2); `config.WORDLE_AUTHOR_ID`
- Produces: `ingest_message(conn, message) -> int | None`. Returns the Wordle # ingested, or None if the message was ignored. `message` is duck-typed and uses only `.author.id`, `.content`, `.created_at`, `.guild.id`, `.channel.id`, `.id`, so tests pass `types.SimpleNamespace` objects (fakes for Discord, real DB).

The message is ignored if any of these hold:
- `guild` is None
- `WORDLE_AUTHOR_ID` is set and the author doesn't match
- `not is_summary(content)`
- the parse gives zero lines

- [ ] **Step 1: Write failing tests:**
  - `test_ingest_summary`: a fake message posted 2026-10-18 14:00 UTC with the SUMMARY returns 1946, and the DB has 4 rows.
  - `test_ingest_ignores_non_summary`: "Slicck was playing" returns None.
  - `test_ingest_ignores_wrong_author`: monkeypatch `config.WORDLE_AUTHOR_ID = 999` and use author 1, which returns None.
  - `test_ingest_same_summary_twice`: the same summary ingested from two channels/message ids still gives 4 rows.
- [ ] **Step 2: Run** `pytest tests/test_ingest.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement `ingest.py`.**
- [ ] **Step 4: Run** `pytest -v`. Expected: all pass.
- [ ] **Step 5: Commit** `feat: ingest summary messages into db`.

---

### Task 6: Discord bot, backfill, probe, and deploy

**Files:**
- Create: `wordle_bot/bot.py`, `wordle_bot/__main__.py`, `scripts/probe.py`, `tests/test_bot.py`, `.env.example`, `deploy/wordle-bot.service`, `README.md`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `display_name(guild, user_id: int) -> str`. Uses `guild.get_member(user_id).display_name`, falling back to `f"Former member ({user_id})"`.
  - `iter_history_channels(guild) -> list` covering text channels, voice channels (their text chat), and active plus archived threads of text channels, filtered to those where the bot has `read_message_history`.
  - `async backfill(conn, guild) -> int`. Returns the number of summaries ingested, iterating `channel.history(limit=None, oldest_first=True)` through `ingest_message`.
  - Bot uses `commands.Bot(command_prefix="!", intents=...)` with `message_content` and `guilds` enabled. `members` stays off; get_member falls back as above.
  - Commands:
    - `!wordle [member]`
    - `!leaderboard`
    - `!rescan` (requires `manage_guild`, runs `backfill`, replies with the count)
  - `on_ready`: for each guild with `not has_any(conn, guild.id)`, run `backfill`.
  - `on_message`: `ingest_message`, then `bot.process_commands`.
  - Entry: `python -m wordle_bot`.

- [ ] **Step 1: Write failing test** `test_display_name_fallback`. A fake guild whose `get_member` returns None gives `"Former member (42)"`. A fake member gives its display_name.
- [ ] **Step 2: Run.** Expected: FAIL. **Step 3:** Implement `display_name` and the rest of `bot.py`. **Step 4:** Run `pytest -v`. Expected: all pass.
- [ ] **Step 5: Write `scripts/probe.py`.** It logs in with the token and, for each readable channel, prints up to 5 recent messages where `is_summary(content)`: channel, author id, author name, `created_at`, `wordle_number_for(created_at)`, raw `content`, and attachment URLs. It then exits.
- [ ] **Step 6: Write `.env.example`** with `DISCORD_TOKEN=`, `WORDLE_AUTHOR_ID=`, and `WORDLE_DB_PATH=wordle.db`. Write `deploy/wordle-bot.service`, a systemd unit running `.venv/bin/python -m wordle_bot` with `EnvironmentFile=.env` and `Restart=always`. Write `README.md` covering Developer Portal setup (enable the Message Content intent, invite with View Channels, Read Message History, Send Messages, Embed Links), running probe, and running the bot.
- [ ] **Step 7: Commit** `feat: discord bot with commands, backfill, and deploy files`.
- [ ] **Step 8: Live verification with Austin. This needs the bot token, so Austin runs it.**
  1. Austin runs `python scripts/probe.py`.
  2. Confirm summaries are found, including in voice-channel chats if any.
  3. Note the author id and put it in `.env` as `WORDLE_AUTHOR_ID`.
  4. Open one summary's image URL and confirm "Wordle No." equals the printed computed number. If it's off by one, adjust `wordle_number_for`, add a regression test, and commit.
  5. Start the bot and let the backfill finish.
  6. In Discord, `!wordle`, `!wordle @snowMAMA`, and `!leaderboard` render. Played counts look plausible for ~430+ days.
  7. Spot-check one known day, e.g. #1936: Slicck X, OnlyTees 6, snowMAMA 4 👑.
