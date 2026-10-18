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

## Running on Windows

Needs Python 3.11+ from python.org (tick "Add python.exe to PATH"). Put the project somewhere
permanent, e.g. `C:\wordle-bot`, then in that folder:

```powershell
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

Edit `.env`: set `DISCORD_TOKEN`, and set `WORDLE_LOG_FILE=bot.log` so you can see what the bot
is doing while it runs in the background. Then check it works in the foreground first:

```powershell
.venv\Scripts\python -m scripts.probe
.venv\Scripts\python -m wordle_bot
```

Stop it with Ctrl+C once `!wordle` answers in Discord.

**Run it in the background, starting at boot (no login needed).** In PowerShell opened with
*Run as administrator*:

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\install-task.ps1
```

It asks for your Windows password. That's your account password, not your PIN; Task Scheduler
needs it to run the bot while nobody is logged in. The task waits a minute after boot for the
network, then runs `deploy\windows\run-bot.cmd`, which restarts the bot 30 seconds after it
ever exits.

- **Is it running?** Look at `bot.log`, or Task Scheduler → *Wordle Bot* → Status "Running".
- **Stop / remove:** `powershell -ExecutionPolicy Bypass -File deploy\windows\stop-bot.ps1`
  (add `-Uninstall` to stop it starting at boot).
- **After changing `.env` or updating the code:** stop it, then `Start-ScheduledTask -TaskName "Wordle Bot"`.
- **Keep the PC awake:** Settings → System → Power → Sleep → *Never* while plugged in.

## Tests

```bash
.venv/bin/pytest
```
