#!/usr/bin/env python3
"""Discord bot that emulates Jibo using OpenJibo response data and intent routing."""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

import discord
from discord import app_commands
from discord.ext import commands

from jibo.config import DISCORD_GUILD_ID
from jibo.engine import JiboEngine
from jibo.providers.discord_rag import DiscordRagService

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("jibo-discord-bot")

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise SystemExit("DISCORD_TOKEN is not set. Copy .env.example to .env and add your bot token.")
if DISCORD_GUILD_ID is None:
    raise SystemExit(
        "DISCORD_GUILD_ID is not set. Copy .env.example to .env and set your Discord server ID."
    )

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
jibo = JiboEngine.create()
discord_rag = DiscordRagService()


def _truncate(text: str, limit: int = 1900) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _guild_allowed(guild_id: int | None) -> bool:
    return guild_id is not None and guild_id == DISCORD_GUILD_ID


async def _leave_unauthorized_guilds() -> None:
    for guild in list(bot.guilds):
        if guild.id == DISCORD_GUILD_ID:
            continue
        log.warning("Leaving unauthorized guild %s (%s)", guild.name, guild.id)
        try:
            await guild.leave()
        except discord.HTTPException as exc:
            log.error("Failed to leave guild %s (%s): %s", guild.name, guild.id, exc)


async def _reply_jibo(target: discord.Interaction | discord.Message, question: str) -> None:
    question = question.strip()
    if not question:
        empty = "What would you like to ask me?"
        if isinstance(target, discord.Interaction):
            await target.response.send_message(empty)
        else:
            await target.reply(empty)
        return

    response = await jibo.ask_async(question)
    content = _truncate(response.text)
    log.info("intent=%s question=%r reply=%r", response.intent, question, response.text)

    if isinstance(target, discord.Interaction):
        await target.response.send_message(content)
    else:
        await target.reply(content)


async def _reply_ai(target: discord.Interaction | commands.Context, question: str) -> None:
    question = question.strip()
    is_interaction = isinstance(target, discord.Interaction)

    if not question:
        empty = "What would you like to ask? Try `/ai <question>` or `!ai <question>`."
        if is_interaction:
            await target.response.send_message(empty)
        else:
            await target.reply(empty)
        return

    if not discord_rag.is_configured:
        missing = (
            "AI is not configured. Set `OPENAI_API_KEY` in `.env` "
            "(or a `chatgpt!KEY` search backend in OpenJibo settings)."
        )
        if is_interaction:
            await target.response.send_message(missing)
        else:
            await target.reply(missing)
        return

    if is_interaction:
        await target.response.defer()
        answer = await discord_rag.ask(question)
        content = _truncate(answer) if answer else "Sorry, I couldn't get an answer right now."
        log.info("ai question=%r reply=%r", question, content)
        await target.followup.send(content)
        return

    async with target.typing():
        answer = await discord_rag.ask(question)
    content = _truncate(answer) if answer else "Sorry, I couldn't get an answer right now."
    log.info("ai question=%r reply=%r", question, content)
    await target.reply(content)


@bot.check
async def only_allowed_guild(ctx: commands.Context) -> bool:
    return _guild_allowed(ctx.guild.id if ctx.guild else None)


@bot.tree.interaction_check
async def only_allowed_guild_slash(interaction: discord.Interaction) -> bool:
    return _guild_allowed(interaction.guild_id)


@bot.event
async def on_ready() -> None:
    await _leave_unauthorized_guilds()
    guild = discord.Object(id=DISCORD_GUILD_ID)
    bot.tree.copy_global_to(guild=guild)
    await bot.tree.sync(guild=guild)
    log.info(
        "Logged in as %s (guild=%s, OpenJibo .mim prompts loaded: %s, AI RAG configured: %s)",
        bot.user,
        DISCORD_GUILD_ID,
        jibo.mim_prompt_count,
        discord_rag.is_configured,
    )


@bot.event
async def on_guild_join(guild: discord.Guild) -> None:
    if guild.id == DISCORD_GUILD_ID:
        log.info("Joined allowed guild %s (%s)", guild.name, guild.id)
        return
    log.warning("Auto-leaving unauthorized guild %s (%s)", guild.name, guild.id)
    try:
        await guild.leave()
    except discord.HTTPException as exc:
        log.error("Failed to leave guild %s (%s): %s", guild.name, guild.id, exc)


@bot.tree.command(name="ask", description="Ask Jibo a question")
@app_commands.describe(question="What would you like to ask Jibo?")
async def slash_ask(interaction: discord.Interaction, question: str) -> None:
    await _reply_jibo(interaction, question)


@bot.command(name="ask")
async def prefix_ask(ctx: commands.Context, *, question: str = "") -> None:
    await _reply_jibo(ctx.message, question)


@bot.tree.command(name="ai", description="Ask an AI using Jibo Discord history")
@app_commands.describe(question="Your question about Jibo / the community")
async def slash_ai(interaction: discord.Interaction, question: str) -> None:
    await _reply_ai(interaction, question)


@bot.command(name="ai")
async def prefix_ai(ctx: commands.Context, *, question: str = "") -> None:
    await _reply_ai(ctx, question)


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    if isinstance(error, commands.CheckFailure):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply("Try `!ask <question>` or `!ai <question>` — for example: `!ask tell me a joke`")
        return
    log.exception("Command error: %s", error)


def main() -> None:
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
