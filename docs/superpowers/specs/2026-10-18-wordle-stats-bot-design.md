# Wordle Stats Bot — Design

Date: 2026-10-18
Owner: Austin West

## Intent

Austin's friend group plays Wordle daily through the NYT Wordle Discord Activity. The Activity only tracks a server-wide group streak (442 days and counting) — there are no individual stats. The group likes looking at clean numbers. This bot fills that gap: it records each person's daily result and shows personal stats and a server leaderboard on request.

It's for fun. Success = friends type `!wordle`, get a nice-looking card with accurate numbers, and the history goes back as far as the server's Wordle messages do.

## Goals

- Track each member's Wordle result per day: solved in 1–6 guesses, or failed.
- Backfill from existing channel history on first run so stats start with 400+ days of data.
- Commands:
  - `!wordle` — the caller's own stats.
  - `!wordle @user` — that user's stats.
  - `!leaderboard` — server leaderboard.
- Output as Discord embeds (style "A" chosen in mockups: native embed, text fields, monospace emoji/block-character bar chart).

## Non-goals

- Web dashboard or any UI outside Discord.
- Tracking anything the Wordle Activity doesn't already post (no letters, no hard-mode).
- Supporting other games or multiple unrelated servers (though data keyed by guild ID costs nothing — see Data).

## Anti-goals

- Wrong attribution: a score credited to the wrong person is worse than a missing score. When in doubt, skip and log.
- Double-counting: the same result appears in several messages; each (Wordle #, user) counts once.

## Source data (observed)

The Wordle Activity posts in whichever channel the game was launched from. The bot only needs one kind of post.

**Daily summary (text + image), posted the following day.** Real examples:

```
Wordle: Your group is on a 442 day streak! 🔥🔥🔥 Here are yesterday's results:
👑 4/6: @OnlyTees @snowMAMA
5/6: @Slicck
```

```
Wordle: Your group is on a 432 day streak! 🔥🔥🔥 Here are yesterday's results:
👑 4/6: @snowMAMA
6/6: @OnlyTees
X/6: @Slicck
```

- One line per score. The format is `N/6:` or `X/6:` (fail), followed by one or more mentions.
- Mentions are real Discord user mentions, with user IDs in the raw content. That makes them a reliable identity.
- 👑 marks the day's best score. Everyone on that line gets a crown.
- The text has no Wordle number. The attached image has "Wordle No. NNNN" printed at the top.

**Ignored: individual result posts.** These are "Slicck was playing" text plus an image with one card per player. Each card shows a profile photo and the colored grid. Several players are grouped on one image when they played around the same time. They are only useful if the summary is missing, and multi-player images could only be attributed by matching profile pictures. Out of scope for v1. See Future.

## How results are determined

**Source:** the daily summary text only. It covers solves (`1/6`–`6/6`) and fails (`X/6`). No image parsing and no avatar matching.

**Wordle number:** derived from the summary's post date. Wordle #0 = 2021-06-19, so #N = (post date − 1 day) − 2021-06-19. Sanity check: #1946 = 2026-10-17. Use America/New_York for the date. **Builder must verify the offset against real data.** Take a few summaries whose attached image shows "Wordle No." and confirm the computed number matches. One manual spot-check is enough; no OCR needed in the bot.

**Dedup:** one record per (guild, Wordle #, user). If two summaries ever cover the same Wordle #, re-ingesting must not double-count.

**Unparseable lines:** log them and skip. Never guess.

## Stats

Per user:

- Played (solves + fails)
- Win %
- Average guesses — **my call:** a fail counts as 7, so failing doesn't improve your average.
- 👑 Crowns — days with 👑 in the summary.
- Current streak and best streak — **my call:** consecutive Wordle numbers solved (NYT-style; a fail or missed day breaks it).
- Best score (lowest guesses, with count)
- Guess distribution 1–6 plus X, drawn as a monospace bar chart.
- Footer: first and last Wordle # covered.

Leaderboard (**my calls**): ranked by average guesses; minimum 20 games to appear; columns rank, player, avg, played, crowns, current streak. Top 3 get 🥇🥈🥉.

Mockup of both is in `.superpowers/brainstorm/81760-1792331778/content/stats-card.html` (option A).

## How it gets built

- **My calls:** Python, discord.py, SQLite (single file). No other services.
- Runs on Austin's own always-on server.
- Bot needs: Message Content intent, read messages / read message history in all channels where Wordle runs. It watches every channel it can see, since the Activity posts wherever it was launched.
- Live: handle new Wordle Activity messages as they arrive.
- Backfill: on first run (and via a re-scan path), walk channel history and ingest all Wordle Activity messages. Must be idempotent — re-running produces the same data.
- Identify Wordle Activity messages by author (the Activity's app/bot user), not by text alone.
- Store raw message IDs per record so re-parsing and debugging are possible.
- Austin's working style: TDD, real (not mocked) DB tests where practical, constants at top.

## Other calls (mine)

- Summary only, with images ignored. Austin confirmed that `X/6` appears in summaries, so the text gives complete data. The 400+ day group streak suggests summaries post reliably.
- Activity posts may live in voice channels' text chat and in threads. Backfill must cover those too. Before parsing work begins, verify the bot can read the full history there.
- Current streak before today's summary posts: computed through the latest Wordle # that has a summary.
- 👑 ties: everyone on the 👑 line gets a crown.

## Left to the builder

- Schema details, command framework (prefix commands via discord.py), embed layout specifics within style A.
- How unresolved/skipped records are surfaced (a log is enough).
- Deployment mechanics on Austin's server (systemd, Docker, etc.), and token/config handling via env file.

## Future (not v1)

- Parse individual result images to recover days with no summary. This means reading the grid for the score and the header for the Wordle number. Identity comes from the "X was playing" text for single-player images and from profile-picture matching for grouped ones.
