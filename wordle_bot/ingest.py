import logging
from dataclasses import replace

from wordle_bot import config
from wordle_bot.db import upsert_results
from wordle_bot.parser import ParsedLine, is_summary, parse_summary, wordle_number_for

log = logging.getLogger(__name__)


def member_id_for(guild, name: str) -> int | None:
    """Match a plain-text Wordle name to one member: server nickname, then global name, then username."""
    wanted = name.casefold()
    for name_of in (lambda m: m.nick, lambda m: m.global_name, lambda m: m.name):
        ids = {m.id for m in guild.members if (name_of(m) or "").casefold() == wanted}
        if len(ids) == 1:
            return ids.pop()
        if ids:
            log.warning("Wordle name %r matches %d members of %s; skipping it", name, len(ids), guild.name)
            return None
    log.warning("Wordle name %r doesn't match any member of %s; skipping it", name, guild.name)
    return None


def resolve_names(guild, lines: list[ParsedLine]) -> list[ParsedLine]:
    """Turn plain-text names into user ids, dropping lines left with nobody on them."""
    resolved = []
    for line in lines:
        ids = list(line.user_ids)
        for name in line.names:
            uid = member_id_for(guild, name)
            if uid is not None and uid not in ids:
                ids.append(uid)
        if ids:
            resolved.append(replace(line, user_ids=ids, names=[]))
    return resolved


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
    lines = resolve_names(message.guild, parsed.lines) if any(l.names for l in parsed.lines) else parsed.lines
    if not lines:
        return None
    wordle_no = wordle_number_for(message.created_at)
    upsert_results(conn, message.guild.id, wordle_no, lines,
                   channel_id=message.channel.id, message_id=message.id)
    return wordle_no
