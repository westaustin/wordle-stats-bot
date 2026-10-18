import logging

import discord
from discord.ext import commands

from wordle_bot import config
from wordle_bot.db import connect, guild_results, has_any, latest_message_id, latest_wordle_no, user_results
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
        except discord.Forbidden:
            log.info("No access to archived threads in #%s", text_channel.name)
    return channels


async def backfill(conn, guild, after: int | None = None) -> int:
    """Ingest Wordle summaries from channel history. Pass `after` (a message id) to catch up only."""
    since = discord.Object(id=after) if after else None
    ingested = 0
    for channel in await _channels_with_archived_threads(guild):
        try:
            async for message in channel.history(limit=None, after=since, oldest_first=True):
                if ingest_message(conn, message) is not None:
                    ingested += 1
        except discord.Forbidden:
            log.info("No history access in #%s", channel.name)
    log.info("Backfill for %s ingested %d summaries", guild.name, ingested)
    return ingested


@bot.event
async def on_ready():
    log.info("Logged in as %s", bot.user)
    for guild in bot.guilds:
        after = latest_message_id(conn, guild.id) if has_any(conn, guild.id) else None
        await backfill(conn, guild, after=after)


@bot.event
async def on_message(message: discord.Message):
    ingest_message(conn, message)
    if not message.author.bot:
        await bot.process_commands(message)


@bot.command(name="wordle")
async def wordle_cmd(ctx: commands.Context, member: discord.Member | None = None):
    target = member or ctx.author
    stats = compute_stats(user_results(conn, ctx.guild.id, target.id), latest_wordle_no(conn, ctx.guild.id))
    await ctx.send(embed=stats_embed(target.display_name, stats))


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


def main():
    global conn
    logging.basicConfig(level=logging.INFO)
    conn = connect(config.DB_PATH)
    bot.run(config.DISCORD_TOKEN, log_handler=None)
