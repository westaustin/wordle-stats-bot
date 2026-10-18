import logging

import aiohttp
import discord
from discord.ext import commands

from wordle_bot import config
from wordle_bot.answers import get_answers, make_fetcher
from wordle_bot.dateparse import DAY_HELP, parse_day, today_et
from wordle_bot.db import (backfill_complete, connect, day_results, guild_results, latest_message_id,
                           latest_wordle_no, mark_backfill_complete, summary_days, user_results)
from wordle_bot.embeds import day_embed, history_embed, leaderboard_embed, stats_embed
from wordle_bot.history import history_rows, page_count, paginate
from wordle_bot.ingest import ingest_message
from wordle_bot.stats import compute_stats, leaderboard
from wordle_bot.views import DayView, HistoryView

log = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # so display names resolve for everyone, not just cached members



class WordleBot(commands.Bot):
    """Owns the HTTP session used to look up answer words."""

    http_session: aiohttp.ClientSession | None = None

    async def setup_hook(self):
        self.http_session = aiohttp.ClientSession()

    async def close(self):
        if self.http_session:
            await self.http_session.close()
        await super().close()

    async def fetch_answer(self, d):
        return await make_fetcher(self.http_session)(d)


bot = WordleBot(command_prefix="!", intents=intents)
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


@bot.command(name="history")
async def history_cmd(ctx: commands.Context, member: discord.User = None):
    target = member or ctx.author
    name = user_label(ctx.guild, target)
    latest = latest_wordle_no(conn, ctx.guild.id)
    rows = history_rows(user_results(conn, ctx.guild.id, target.id), summary_days(conn, ctx.guild.id))
    pages = page_count(len(rows), config.HISTORY_PAGE_SIZE)

    async def render(page: int) -> discord.Embed:
        shown = paginate(rows, page, config.HISTORY_PAGE_SIZE)
        words = await get_answers(conn, [r.wordle_no for r in shown], latest, bot.fetch_answer)
        return history_embed(name, shown, words, page, pages)

    async with ctx.typing():
        embed = await render(0)
    if pages == 1:
        await ctx.send(embed=embed)
        return
    view = HistoryView(ctx.author.id, pages, render)
    view.message = await ctx.send(embed=embed, view=view)


@bot.command(name="day")
async def day_cmd(ctx: commands.Context, *, arg: str = None):
    wordle_no = parse_day(arg, today_et())
    if wordle_no is None:
        await ctx.send(DAY_HELP)
        return
    latest = latest_wordle_no(conn, ctx.guild.id)
    if latest is None or wordle_no > latest:
        await ctx.send("That day's results haven't posted yet.")
        return

    async def render(n: int) -> discord.Embed:
        word = (await get_answers(conn, [n], latest, bot.fetch_answer))[n]
        entries = [(display_name(ctx.guild, uid), r) for uid, r in day_results(conn, ctx.guild.id, n)]
        return day_embed(n, word, entries)

    async with ctx.typing():
        embed = await render(wordle_no)
    view = DayView(ctx.author.id, wordle_no, latest, render)
    view.message = await ctx.send(embed=embed, view=view)


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
