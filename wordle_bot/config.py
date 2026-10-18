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
ANSWER_URL = "https://www.nytimes.com/svc/wordle/v2/{date}.json"
HISTORY_PAGE_SIZE = 10
VIEW_TIMEOUT = 300  # seconds before paging buttons stop working

DB_PATH = os.getenv("WORDLE_DB_PATH", "wordle.db")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
LOG_FILE = os.getenv("WORDLE_LOG_FILE") or None
WORDLE_AUTHOR_ID = int(os.environ["WORDLE_AUTHOR_ID"]) if os.getenv("WORDLE_AUTHOR_ID") else None
