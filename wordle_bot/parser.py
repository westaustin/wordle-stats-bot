import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from wordle_bot import config

log = logging.getLogger(__name__)

LINE_RE = re.compile(r"^(👑\s*)?([1-6X])/6:\s*(.+)$")
MENTION_RE = re.compile(r"<@!?(\d+)>")
# Plain-text "@Name" the Wordle app sometimes posts instead of a real mention. Names may contain
# spaces ("@That Good Kwat"), so each one runs until the next " @" or the end of the line.
NAME_RE = re.compile(r"(?:^|\s)@(.+?)(?=\s+@|$)")


@dataclass(frozen=True)
class ParsedLine:
    guesses: int | None  # None = fail
    crown: bool
    user_ids: list[int]
    names: list[str] = field(default_factory=list)  # plain-text names, resolved to ids at ingest


@dataclass(frozen=True)
class ParsedSummary:
    lines: list[ParsedLine] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def is_summary(text: str) -> bool:
    return config.SUMMARY_MARKER in text


def parse_summary(text: str) -> ParsedSummary:
    lines, skipped = [], []
    for raw in text.splitlines():
        line = raw.strip()
        if "/6:" not in line:
            continue
        m = LINE_RE.match(line)
        ids = [int(i) for i in MENTION_RE.findall(m.group(3))] if m else []
        names = [n.strip() for n in NAME_RE.findall(MENTION_RE.sub(" ", m.group(3)).strip())] if m else []
        if not m or not (ids or names):
            log.warning("Skipping unparseable summary line: %r", line)
            skipped.append(line)
            continue
        score = m.group(2)
        lines.append(ParsedLine(None if score == "X" else int(score), bool(m.group(1)), ids, names))
    return ParsedSummary(lines, skipped)


def wordle_number_for(posted_at: datetime) -> int:
    played_on = posted_at.astimezone(config.TZ).date() - timedelta(days=1)
    return (played_on - config.WORDLE_EPOCH).days
