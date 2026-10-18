# Wordle Bot — History, Answers & Day Lookup — Design

Date: 2026-10-18
Owner: Austin West
Builds on: `docs/superpowers/specs/2026-10-18-wordle-stats-bot-design.md` (existing bot: summary ingestion, `!wordle`, `!leaderboard`)

## Intent

Looking back at an old Wordle day, the group wants three things: **what was the word, what were my guesses, and what did I finish in?** Guesses (the actual letters typed) aren't available anywhere the bot can see, so they're out (Austin agreed). This feature covers the other two: the answer word next to each score, with a way to browse back through past days.

## Goals

- `!history` — your recent results, newest first, paginated with buttons.
- `!history @user` — same for someone else.
- `!day <number or date>` — one day, everyone's scores plus the word, with buttons to step to the previous/next day.
- Every row/day shows the answer word.

## Non-goals

- The actual guessed words. They're not in Discord. Also not the colored grids, since that needs image parsing (still deferred).
- Spoilers. Results only exist for yesterday and earlier, and the group doesn't replay old days (NYT archive needs a paid sub). So no word the bot shows is one someone could still be playing. Austin's call.

## Anti-goals

- Leaking today's word. Today's (or a future) answer is never shown, even though the NYT endpoint would return it.

## Answer words

- Source: `https://www.nytimes.com/svc/wordle/v2/YYYY-MM-DD.json`, which is public and needs no auth. Verified 2026-10-18: `2026-10-07` → `{"solution":"prove","print_date":"2026-10-07","days_since_launch":1936,...}`, and `2021-06-19` → `"cigar"` (#0). `days_since_launch` matches the bot's Wordle numbering, so date = `WORDLE_EPOCH + wordle_no` days.
- Cache each answer in SQLite the first time it's needed. A day's answer never changes, so fetch once per day, ever. Store uppercase.
- If a fetch fails (network, non-200, unexpected JSON), show `?????` for that word and don't cache the failure. It retries next time.
- **Safe-to-show rule (my call):** a word is shown only if its Wordle # ≤ `latest_wordle_no` for the guild, the newest day the server has a summary for. Once the summary is out, everyone in the group has finished that day. A clock-based cutoff could leak the word to a West Coast player between midnight and 3 a.m. ET. Words past that cutoff are never fetched or shown. The same check drives `!day`'s ▶ disabling and its `today` handling.
- **My call:** fetch lazily, only for the days on the page being shown. No bulk prefetch of 1,900+ days. A page has at most 10 fetches, and it's instant after that.

## Commands

### `!history [@user]`

- Lists the user's days newest first. This covers every day they have a result (played or X), plus "didn't play" rows for days between their first and last game. Austin approved the mockup with those rows. **My call:** a missed day only counts if the server has a summary for that Wordle # (anyone has a result). Days with no server data at all are skipped, not labelled "didn't play". The bot can't tell a missed day from missing data, and calling it "didn't play" would be false.
- Row: `#1946 · Oct 17 · CRANE · 4/6 👑`. Missed day: `#1943 · Oct 14 · TRAIN · didn't play`.
- 10 rows per page *(my call)*. Footer `Page N / M`.
- Buttons: ⏮ ◀ ▶ ⏭. Disable them at the ends.
- Same user-lookup behavior as `!wordle`: a bad or departed mention gives an error, not the caller's history. Embed title uses the same name logic.
- No results → `No Wordle results yet.`

### `!day <arg>`

- Accepted forms (Austin: number and date both work):
  - Wordle number: `1936` or `#1936`
  - Dates: `oct 7`, `october 7`, `10/7`, `2026-10-07`, `10/7/2026`
  - `yesterday`
  - `today`, or any day past the safe-to-show cutoff, returns "That day's results haven't posted yet." and never the word.
- A date without a year means the most recent past occurrence (`dec 25` asked in October = last December).
- Output: title `Wordle #1936 · Oct 7 · PROVE`, then one line per player sorted best to worst (fails last), 👑 on crown lines. Names use the leaderboard's name logic, including the "Former member" fallback.
- A day with no results in the DB shows the word plus `No results recorded for this day.`
- Buttons: `◀ #1935` and `#1937 ▶`. Disable ▶ when the next day is past the safe-to-show cutoff.
- Unparseable arg → short help reply listing the accepted forms. Missing arg defaults to `yesterday` *(my call)*.

### Pagination behavior (both commands)

- Discord message buttons (discord.py `ui.View`), not reactions. *(My call: Austin's "I've seen bots do this with emojis" was satisfied by the mockup's emoji-labeled buttons.)*
- **My call:** only the person who ran the command can press the buttons. Others get an ephemeral "Run the command yourself to browse."
- Buttons time out after 5 minutes of no presses, then get removed or disabled.
- Pressing edits the same message. It never posts a new one.

## Out of scope / unchanged

- Ingestion, stats, and the leaderboard are unchanged.
- Same stack: Python, discord.py, SQLite, and the same module layout. New HTTP calls use `aiohttp`, which discord.py already depends on, so the bot doesn't block.

## Left to the builder

- Schema for the answers cache.
- Date parsing approach. A small hand-rolled parser is fine. Don't add a heavy dependency.
- Exact embed formatting within the mockup's look (`.superpowers/brainstorm/84634-1792333394/content/history.html`).
- How the history page query is structured.
