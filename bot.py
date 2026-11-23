#!/usr/bin/env python3
"""JiboDisc: posts in the social-media channel when a followed YouTube channel releases a video."""

import io
import json
import logging
import os
from pathlib import Path

import aiohttp
import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

import reddit
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
# SOCS=CAI skips the EU cookie page, which has none of the live-stream details
WATCH_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36", "Cookie": "SOCS=CAI"}
SEEN_FILE = Path(__file__).with_name("youtube-seen.json")  # video IDs already handled, per channel
REDDIT_PING_ROLE_ID = YOUTUBE_PING_ROLE_ID
UPCOMING_SEEN_KEY = "upcoming"  # streams whose "will go live" notice was already sent
REDDIT_SEEN_KEY = "reddit"  # Reddit post IDs share the state file with the YouTube channels

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
                url = youtube.WATCH_URL.format(video_id)
                try:
                    async with http.get(url, headers=WATCH_HEADERS) as response:
                        response.raise_for_status()
                        page = await response.text()
                        state = youtube.stream_state(page)
                except Exception as exc:  # unknown yet: forget it again so the next check looks once more
                    seen[handle].remove(video_id)
                    log.warning("Watch page check failed for %s: %s", video_id, exc)
                    continue
                embed = discord.Embed(title=titles[video_id] or "New video", url=url, color=0xFF0000)
                embed.set_author(name=name, url=f"https://www.youtube.com/channel/{channel_id}")
                embed.set_image(url=f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg")
                if state == "upcoming":  # announced, not started: check again every minute until it goes live
                    seen[handle].remove(video_id)
                    start = youtube.scheduled_start(page)
                    if start and video_id not in seen.setdefault(UPCOMING_SEEN_KEY, []):
                        try:  # once, no ping; <t:...:R> is Discord's live countdown ("in 50 minutes")
                            await channel.send(f"**{name}** will go live <t:{start}:R>! <{url}>", embed=embed,
                                               allowed_mentions=discord.AllowedMentions.none())
                            seen[UPCOMING_SEEN_KEY].append(video_id)
                            log.info("Posted upcoming %s from %s", video_id, handle)
                        except discord.HTTPException as exc:
                            log.error("Could not post upcoming %s from %s: %s", video_id, handle, exc)
                    continue
                try:
                    # <link> keeps the link in the message without a second preview; it still works if embeds are not allowed
                    await channel.send(
                        f"<@&{YOUTUBE_PING_ROLE_ID}> **{name}** "
                        + ("is live now!" if state == "live" else "just released a new video!") + f" <{url}>",
                        embed=embed,
                        allowed_mentions=discord.AllowedMentions(roles=True),
                    )
                    log.info("Posted %s from %s", video_id, handle)
                except discord.HTTPException as exc:  # e.g. no permission: forget it again so the next check retries
                    seen[handle].remove(video_id)
                    log.error("Could not post %s from %s: %s", video_id, handle, exc)
            save_seen(seen)  # after each channel, so a crash never re-posts what was already sent


@tasks.loop(minutes=5)  # each check starts a headless browser; Reddit throttles frequent visitors
async def check_reddit() -> None:
    channel = client.get_channel(SOCIAL_MEDIA_CHANNEL_ID)
    if channel is None:
        return
    seen = load_seen()
    try:
        posts = await reddit.fetch_new()
    except Exception as exc:  # a Reddit outage or block must not stop the loop
        log.warning("Reddit check failed: %s", exc)
        return
    by_id = {p["id"]: p for p in posts}
    for post_id in youtube.new_videos(seen, REDDIT_SEEN_KEY, list(by_id)):
        post = by_id[post_id]
        if not reddit.is_recent(post):
            log.info("Skipped old Reddit post %s from r/%s", post_id, post["subreddit"])
            continue
        embed = discord.Embed(title=post["title"][:256] or "New post", url=post["url"], description=post["summary"] or None, color=0xFF4500)
        embed.set_author(name=f"u/{post['author']} in r/{post['subreddit']}", url=f"https://www.reddit.com/r/{post['subreddit']}")
        files = []
        frame = await reddit.video_frame(post["video"]) if post["video"] else None
        if frame:
            files.append(discord.File(io.BytesIO(frame), "preview.jpg"))
            embed.set_image(url="attachment://preview.jpg")
        elif post["image"]:
            embed.set_image(url=post["image"])
        try:
            await channel.send(
                f"<@&{REDDIT_PING_ROLE_ID}> **u/{post['author']}** just posted in **r/{post['subreddit']}**! <{post['url']}>",
                embed=embed,
                files=files,
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
            log.info("Posted Reddit %s from r/%s", post_id, post["subreddit"])
        except discord.HTTPException as exc:
            seen[REDDIT_SEEN_KEY].remove(post_id)
            log.error("Could not post Reddit %s: %s", post_id, exc)
    save_seen(seen)


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
    if not check_reddit.is_running():
        check_reddit.start()
    log.info("Logged in as %s, following %d YouTube channels and r/%s", client.user, len(youtube.CHANNELS), ", r/".join(reddit.SUBREDDITS))


@client.event
async def on_guild_join(guild: discord.Guild) -> None:
    if guild.id != DISCORD_GUILD_ID:
        log.warning("Auto-leaving unauthorized guild %s (%s)", guild.name, guild.id)
        await guild.leave()


if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
