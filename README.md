# Wordle Stats Bot

Tracks each member's daily Wordle result from the Wordle Activity's daily summary
("Here are yesterday's results: …") and answers:

- `!wordle` — your stats
- `!wordle @someone` — their stats
- `!history` / `!history @someone` — recent days with the answer word, paged with buttons
- `!day 1936` / `!day oct 7` / `!day yesterday` — everyone's scores and the word for one day
- `!leaderboard` — server ranking by average guesses (min 20 games)
- `!rescan` — re-read all channel history (needs Manage Server)

Design: `docs/superpowers/specs/2026-10-18-wordle-stats-bot-design.md`

## 1. Create the bot

1. https://discord.com/developers/applications → New Application → Bot → copy the token.
2. Under **Privileged Gateway Intents**, enable **Message Content Intent** and **Server Members Intent**.
3. OAuth2 → URL Generator: scope `bot`, permissions **View Channels**, **Read Message History**,
   **Send Messages**, **Embed Links**. Open the URL and add the bot to your server.
   Make sure it can see every channel (including voice-channel chats) where Wordle gets played.

## 2. Install

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # then paste DISCORD_TOKEN
```

## 3. Probe (one-time check)

```bash
.venv/bin/python -m scripts.probe
```

This prints recent summaries with the author id and a computed Wordle #. Put the author id
in `.env` as `WORDLE_AUTHOR_ID` (until it's set, only bot/app-authored summaries are trusted), and open one image link to confirm "Wordle No." matches the
computed number.

## 4. Run

```bash
.venv/bin/python -m wordle_bot
```

On first start it reads all channel history (can take a few minutes). Once a full pass finishes
cleanly, later restarts only catch up from where it left off; if any channel errored, the next
start does a full pass again. `!rescan` forces a full pass anytime. For an always-on server, see `deploy/wordle-bot.service`
(copy to `/etc/systemd/system/`, adjust paths, then `systemctl enable --now wordle-bot`).

## Tests

```bash
.venv/bin/pytest
```
