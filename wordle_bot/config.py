import os
from datetime import date
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

WORDLE_EPOCH = date(2021, 6, 19)  # Wordle #0
TZ = ZoneInfo("America/New_York")
MIN_GAMES = 20
FAIL_SCORE = 7
SUMMARY_MARKER = "Here are yesterday's results"

DB_PATH = os.getenv("WORDLE_DB_PATH", "wordle.db")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
WORDLE_AUTHOR_ID = int(os.environ["WORDLE_AUTHOR_ID"]) if os.getenv("WORDLE_AUTHOR_ID") else None
