#!/usr/bin/env python3
"""Discord bot that emulates Jibo using OpenJibo response data and intent routing."""

import logging
import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from jibo.engine import JiboEngine

load_dotenv()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("jibo-discord-bot")

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise SystemExit("DISCORD_TOKEN is not set. Copy .env.example to .env and add your bot token.")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
jibo = JiboEngine.create()


def _truncate(text: str, limit: int = 1900) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


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


@bot.event
async def on_ready() -> None:
    await bot.tree.sync()
    log.info(
        "Logged in as %s (OpenJibo .mim prompts loaded: %s)",
        bot.user,
        jibo.mim_prompt_count,
    )


@bot.tree.command(name="ask", description="Ask Jibo a question")
@app_commands.describe(question="What would you like to ask Jibo?")
async def slash_ask(interaction: discord.Interaction, question: str) -> None:
    await _reply_jibo(interaction, question)


@bot.command(name="ask")
async def prefix_ask(ctx: commands.Context, *, question: str = "") -> None:
    await _reply_jibo(ctx.message, question)


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.reply("Try `!ask <your question>` — for example: `!ask tell me a joke`")
        return
    log.exception("Command error: %s", error)


def main() -> None:
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
