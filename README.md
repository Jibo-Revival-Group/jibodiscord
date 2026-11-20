# JiboDisc

The Jibo Revival Group's Discord bot. When one of the YouTube channels it follows releases a video, it posts the link in the
social-media channel and pings the YouTube ping role.

## How it works

Every minute it reads each channel's public YouTube feed (no API key needed). A video it has not seen before gets one post.
The videos it has seen are kept in `youtube-seen.json` next to `bot.py`. The first check of a channel only records what is
already there, so nothing old is posted when the bot is first started or a channel is added.

- Followed channels: the `CHANNELS` list in `youtube.py` (handle and channel ID).
- Where it posts and which role it pings: `SOCIAL_MEDIA_CHANNEL_ID` and `YOUTUBE_PING_ROLE_ID` in `bot.py`.

## Setup

1. In the [Discord Developer Portal](https://discord.com/developers/applications), create an application with a bot and copy its
   token. No privileged intents are needed.
2. Invite it to the server with the `bot` scope. In the social-media channel it needs View Channel, Send Messages and
   Embed Links and Mention Everyone (or make the ping role mentionable).
3. Install and configure:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set DISCORD_TOKEN and DISCORD_GUILD_ID
python bot.py
```

The bot only stays in the server named by `DISCORD_GUILD_ID` and leaves any other.

## Tests

```bash
python -m unittest tests.test_youtube
```
