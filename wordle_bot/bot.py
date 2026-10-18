import logging
from logging.handlers import RotatingFileHandler

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
from wordle_bot.views import HANDLERS, PagerButton, day_view, history_view

log = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # so display names resolve for everyone, not just cached members



class WordleBot(commands.Bot):
    """Owns the HTTP session used to look up answer words."""

    http_session: aiohttp.ClientSession | None = None

    async def setup_hook(self):
        self.http_session = aiohttp.ClientSession()
        self.add_dynamic_items(PagerButton)  # paging buttons on any message, even from before a restart

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


PROGRESS_EVERY = 5000  # log a progress line this often while reading one long channel


async def name_for(guild, user_id: int) -> str:
    """Like user_label, but from an id alone (a button press), fetching users who left."""
    member = guild.get_member(user_id)
    if member:
        return member.display_name
    try:
        return (bot.get_user(user_id) or await bot.fetch_user(user_id)).name
    except discord.HTTPException:
        return f"Former member ({user_id})"


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
    channels = await _channels_with_archived_threads(guild)
    log.info("Backfill for %s started (%s, %d channels)", guild.name,
             "full scan" if after is None else f"catching up after message {after}", len(channels))
    for i, channel in enumerate(channels, 1):
        read = found = 0
        try:
            async for message in channel.history(limit=None, after=since, oldest_first=True):
                read += 1
                if ingest_message(conn, message) is not None:
                    found += 1
                if read % PROGRESS_EVERY == 0:
                    log.info("  #%s: %d messages read so far, %d summaries", channel.name, read, found)
        except discord.HTTPException as e:
            clean = False
            log.warning("Couldn't read history in #%s: %s", channel.name, e)
        ingested += found
        log.info("  [%d/%d] #%s: %d messages, %d summaries", i, len(channels), channel.name, read, found)
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


async def history_page(guild, owner_id: int, user_id: int, page: int):
    latest = latest_wordle_no(conn, guild.id)
    rows = history_rows(user_results(conn, guild.id, user_id), summary_days(conn, guild.id))
    pages = page_count(len(rows), config.HISTORY_PAGE_SIZE)
    page = max(0, min(page, pages - 1))
    shown = paginate(rows, page, config.HISTORY_PAGE_SIZE)
    words = await get_answers(conn, [r.wordle_no for r in shown], latest, bot.fetch_answer)
    embed = history_embed(await name_for(guild, user_id), shown, words, page, pages)
    return embed, history_view(owner_id, user_id, page, pages) if pages > 1 else None


async def day_page(guild, owner_id: int, wordle_no: int):
    latest = latest_wordle_no(conn, guild.id)
    wordle_no = max(0, min(wordle_no, latest))
    word = (await get_answers(conn, [wordle_no], latest, bot.fetch_answer))[wordle_no]
    entries = [(display_name(guild, uid), r) for uid, r in day_results(conn, guild.id, wordle_no)]
    return day_embed(wordle_no, word, entries), day_view(owner_id, wordle_no, latest)


HANDLERS["h"] = lambda interaction, owner, user_id, page: history_page(interaction.guild, owner, user_id, page)
HANDLERS["d"] = lambda interaction, owner, _, wordle_no: day_page(interaction.guild, owner, wordle_no)


@bot.command(name="history")
async def history_cmd(ctx: commands.Context, member: discord.User = None):
    target = member or ctx.author
    async with ctx.typing():
        embed, view = await history_page(ctx.guild, ctx.author.id, target.id, 0)
    await ctx.send(embed=embed, view=view)


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
    async with ctx.typing():
        embed, view = await day_page(ctx.guild, ctx.author.id, wordle_no)
    await ctx.send(embed=embed, view=view)


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


def setup_logging(log_file: str | None) -> None:
    """Log to the console, and also to a rotating UTF-8 file when `log_file` is set."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        handlers.append(RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"))
    logging.basicConfig(level=logging.INFO, handlers=handlers, force=True,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main():
    global conn
    setup_logging(config.LOG_FILE)
    conn = connect(config.DB_PATH)
    bot.run(config.DISCORD_TOKEN, log_handler=None)
