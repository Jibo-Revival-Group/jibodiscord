#!/usr/bin/env python3
"""JiboDisc: posts in the social-media channel when a followed YouTube channel releases a video."""

import json
import logging
import os
from pathlib import Path

import aiohttp
import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

import youtube

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("jibodisc")

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise SystemExit("DISCORD_TOKEN is not set. Copy .env.example to .env and add your bot token.")
if not os.environ.get("DISCORD_GUILD_ID", "").isdigit():
    raise SystemExit("DISCORD_GUILD_ID is not set. Copy .env.example to .env and set your Discord server ID.")
DISCORD_GUILD_ID = int(os.environ["DISCORD_GUILD_ID"])

SOCIAL_MEDIA_CHANNEL_ID = 1570894281538019368
YOUTUBE_PING_ROLE_ID = 1570893128448213032
SEEN_FILE = Path(__file__).with_name("youtube-seen.json")  # video IDs already handled, per channel

client = discord.Client(intents=discord.Intents.default())
tree = app_commands.CommandTree(client)  # holds no commands; syncing it removes the old /ask and /ai


def load_seen() -> dict[str, list[str]]:
    try:
        return json.loads(SEEN_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_seen(seen: dict[str, list[str]]) -> None:
    tmp = SEEN_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(seen))
    tmp.replace(SEEN_FILE)


@tasks.loop(minutes=1)  # YouTube feeds already lag minutes behind; checking often keeps that from adding up
async def check_youtube() -> None:
    channel = client.get_channel(SOCIAL_MEDIA_CHANNEL_ID)
    if channel is None:
        log.error("Channel %s not found (is the bot in the server, and can it see the channel?)", SOCIAL_MEDIA_CHANNEL_ID)
        return
    seen = load_seen()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as http:
        for handle, channel_id in youtube.CHANNELS.items():
            try:
                async with http.get(youtube.FEED_URL.format(channel_id)) as response:
                    response.raise_for_status()
                    name, videos = youtube.parse_feed(await response.text())
            except Exception as exc:  # one channel's feed failing must not stop the others
                log.warning("Feed check failed for %s: %s", handle, exc)
                continue
            name = name or handle
            titles = {v["id"]: v["title"] for v in videos}
            for video_id in youtube.new_videos(seen, handle, list(titles)):
                url = f"https://www.youtube.com/watch?v={video_id}"
                embed = discord.Embed(title=titles[video_id] or "New video", url=url, color=0xFF0000)
                embed.set_author(name=name, url=f"https://www.youtube.com/channel/{channel_id}")
                embed.set_image(url=f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg")
                try:
                    # <link> keeps the link in the message without a second preview; it still works if embeds are not allowed
                    await channel.send(
                        f"<@&{YOUTUBE_PING_ROLE_ID}> **{name}** just released a new video! <{url}>",
                        embed=embed,
                        allowed_mentions=discord.AllowedMentions(roles=True),
                    )
                    log.info("Posted %s from %s", video_id, handle)
                except discord.HTTPException as exc:  # e.g. no permission: forget it again so the next check retries
                    seen[handle].remove(video_id)
                    log.error("Could not post %s from %s: %s", video_id, handle, exc)
            save_seen(seen)  # after each channel, so a crash never re-posts what was already sent


@client.event
async def on_ready() -> None:
    for guild in client.guilds:
        if guild.id != DISCORD_GUILD_ID:
            log.warning("Leaving unauthorized guild %s (%s)", guild.name, guild.id)
            await guild.leave()
    await tree.sync(guild=discord.Object(id=DISCORD_GUILD_ID))
    await tree.sync()
    if not check_youtube.is_running():
        check_youtube.start()
    log.info("Logged in as %s, following %d YouTube channels", client.user, len(youtube.CHANNELS))


@client.event
async def on_guild_join(guild: discord.Guild) -> None:
    if guild.id != DISCORD_GUILD_ID:
        log.warning("Auto-leaving unauthorized guild %s (%s)", guild.name, guild.id)
        await guild.leave()


if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
