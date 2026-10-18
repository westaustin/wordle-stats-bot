import logging

import discord
from discord.ext import commands

from wordle_bot import config
from wordle_bot.db import (backfill_complete, connect, guild_results, latest_message_id, latest_wordle_no,
                           mark_backfill_complete, user_results)
from wordle_bot.embeds import leaderboard_embed, stats_embed
from wordle_bot.ingest import ingest_message
from wordle_bot.stats import compute_stats, leaderboard

log = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # so display names resolve for everyone, not just cached members

bot = commands.Bot(command_prefix="!", intents=intents)
conn = None  # opened in main() so importing this module has no side effects


def display_name(guild, user_id: int) -> str:
    member = guild.get_member(user_id)
    return member.display_name if member else f"Former member ({user_id})"


def user_label(guild, user) -> str:
    member = guild.get_member(user.id)
    return member.display_name if member else user.name


def catch_up_point(conn, guild_id: int) -> int | None:
    """Message id to resume after, or None if a full history pass is still needed."""
    return latest_message_id(conn, guild_id) if backfill_complete(conn, guild_id) else None


def iter_history_channels(guild) -> list:
    """Text channels, voice channel chats, and active threads the bot can read."""
    channels = [*guild.text_channels, *guild.voice_channels, *guild.threads]
    return [c for c in channels if c.permissions_for(guild.me).read_message_history]


async def _channels_with_archived_threads(guild) -> list:
    channels = iter_history_channels(guild)
    for text_channel in guild.text_channels:
        if not text_channel.permissions_for(guild.me).read_message_history:
            continue
        try:
            async for thread in text_channel.archived_threads(limit=None):
                channels.append(thread)
        except discord.HTTPException as e:
            log.warning("Can't list archived threads in #%s: %s", text_channel.name, e)
    return channels


async def backfill(conn, guild, after: int | None = None) -> int:
    """Ingest Wordle summaries from channel history. Pass `after` (a message id) to catch up only.

    A full pass (no `after`) that reads every channel without error is recorded, so later
    starts can catch up instead of rescanning. Any channel error leaves the full pass pending.
    """
    since = discord.Object(id=after) if after else None
    ingested = 0
    clean = True
    for channel in await _channels_with_archived_threads(guild):
        try:
            async for message in channel.history(limit=None, after=since, oldest_first=True):
                if ingest_message(conn, message) is not None:
                    ingested += 1
        except discord.HTTPException as e:
            clean = False
            log.warning("Couldn't read history in #%s: %s", channel.name, e)
    if after is None and clean:
        mark_backfill_complete(conn, guild.id)
    log.info("Backfill for %s ingested %d summaries%s", guild.name, ingested,
             "" if clean else " (incomplete; will retry full scan on next start)")
    return ingested


@bot.event
async def on_ready():
    log.info("Logged in as %s", bot.user)
    for guild in bot.guilds:
        await backfill(conn, guild, after=catch_up_point(conn, guild.id))


@bot.event
async def on_message(message: discord.Message):
    ingest_message(conn, message)
    if not message.author.bot:
        await bot.process_commands(message)


@bot.command(name="wordle")
async def wordle_cmd(ctx: commands.Context, member: discord.User = None):
    # discord.User (not Optional[Member]) so a bad or departed @mention errors instead of
    # silently showing the caller's own stats; UserConverter can fetch users who left.
    target = member or ctx.author
    stats = compute_stats(user_results(conn, ctx.guild.id, target.id), latest_wordle_no(conn, ctx.guild.id))
    await ctx.send(embed=stats_embed(user_label(ctx.guild, target), stats))


@bot.command(name="leaderboard")
async def leaderboard_cmd(ctx: commands.Context):
    rows = leaderboard(guild_results(conn, ctx.guild.id), latest_wordle_no(conn, ctx.guild.id))
    named = [(display_name(ctx.guild, r.user_id), r.stats) for r in rows]
    await ctx.send(embed=leaderboard_embed(named))


@bot.command(name="rescan")
@commands.has_permissions(manage_guild=True)
async def rescan_cmd(ctx: commands.Context):
    await ctx.send("Rescanning Wordle history…")
    count = await backfill(conn, ctx.guild)
    await ctx.send(f"Done. Ingested {count} daily summaries.")


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.UserNotFound):
        await ctx.send(f"Couldn't find a user matching `{error.argument}`. Try an @mention.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You need Manage Server to do that.")
    elif not isinstance(error, commands.CommandNotFound):
        log.error("Command %s failed", ctx.command, exc_info=error)


def main():
    global conn
    logging.basicConfig(level=logging.INFO)
    conn = connect(config.DB_PATH)
    bot.run(config.DISCORD_TOKEN, log_handler=None)
