from wordle_bot import config
from wordle_bot.db import upsert_results
from wordle_bot.parser import is_summary, parse_summary, wordle_number_for


def ingest_message(conn, message) -> int | None:
    """Store a Wordle daily summary message. Returns its Wordle #, or None if ignored."""
    if message.guild is None:
        return None
    if config.WORDLE_AUTHOR_ID is not None:
        if message.author.id != config.WORDLE_AUTHOR_ID:
            return None
    elif not message.author.bot:
        return None  # without a configured author id, at least never trust a human-typed summary
    if not is_summary(message.content):
        return None
    parsed = parse_summary(message.content)
    if not parsed.lines:
        return None
    wordle_no = wordle_number_for(message.created_at)
    upsert_results(conn, message.guild.id, wordle_no, parsed.lines,
                   channel_id=message.channel.id, message_id=message.id)
    return wordle_no
