"""Print recent Wordle summary messages so you can find the Wordle app's author id
and check the computed Wordle # against the number printed in the attached image.

Run from the project root:  .venv/bin/python -m scripts.probe
"""
import discord

from wordle_bot import config
from wordle_bot.bot import iter_history_channels
from wordle_bot.parser import is_summary, wordle_number_for

PER_CHANNEL = 5
SCAN_LIMIT = 2000  # messages to look back through per channel

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    for guild in client.guilds:
        print(f"=== {guild.name} ({guild.id})")
        for channel in iter_history_channels(guild):
            found = 0
            try:
                async for m in channel.history(limit=SCAN_LIMIT):
                    if not is_summary(m.content):
                        continue
                    print(f"\n#{channel.name} | author {m.author} ({m.author.id}) | {m.created_at:%Y-%m-%d %H:%M} UTC"
                          f" | computed Wordle #{wordle_number_for(m.created_at)}")
                    print(m.content)
                    for a in m.attachments:
                        print("  image:", a.url)
                    found += 1
                    if found >= PER_CHANNEL:
                        break
            except discord.Forbidden:
                print(f"(no access to #{channel.name})")
    await client.close()


client.run(config.DISCORD_TOKEN)
