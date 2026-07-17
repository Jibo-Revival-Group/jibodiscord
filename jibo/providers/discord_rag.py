from __future__ import annotations

import logging
from typing import Any

import aiohttp

from jibo.config import OPENAI_AI_MODEL, OPENAI_API_KEY, OPENAI_VECTOR_STORE_ID

log = logging.getLogger("jibo-discord-bot.discord_rag")

_RESPONSES_ENDPOINT = "https://api.openai.com/v1/responses"
_REQUEST_TIMEOUT_SECONDS = 45

_INSTRUCTIONS = """You are a helpful assistant for the Jibo Discord community.

Answer using information retrieved from the attached vector store, which contains
every message sent to the Jibo Discord. Prefer concrete troubleshooting steps,
workarounds, and answers that community members have shared.

Rules:
- Keep answers under 15 sentences.
- Prefer newer and more stable fixes or methods when sources disagree or several approaches exist.
- Be clear and concise. Use plain Discord-friendly text (no markdown tables).
- When the store has relevant discussion, synthesize the useful parts.
- If the store has nothing relevant, say so briefly and avoid inventing details.
- Do not claim to be Jibo the robot; you are answering from community history.
"""


def _extract_output_text(body: dict[str, Any]) -> str | None:
    direct = body.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    output = body.get("output")
    if not isinstance(output, list):
        return None

    parts: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") in ("output_text", "text"):
                text = block.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
    if not parts:
        return None
    return "\n".join(parts).strip() or None


class DiscordRagService:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        vector_store_id: str | None = None,
    ) -> None:
        self.api_key = (api_key if api_key is not None else OPENAI_API_KEY) or None
        self.model = model if model is not None else OPENAI_AI_MODEL
        self.vector_store_id = vector_store_id if vector_store_id is not None else OPENAI_VECTOR_STORE_ID

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.vector_store_id and self.model)

    async def ask(self, question: str) -> str | None:
        if not question.strip() or not self.is_configured:
            return None

        payload: dict[str, Any] = {
            "model": self.model,
            "instructions": _INSTRUCTIONS,
            "input": question.strip(),
            "tools": [
                {
                    "type": "file_search",
                    "vector_store_ids": [self.vector_store_id],
                }
            ],
            "tool_choice": {"type": "file_search"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    _RESPONSES_ENDPOINT,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT_SECONDS),
                ) as response:
                    body = await response.json(content_type=None)
                    if response.status != 200:
                        log.warning(
                            "OpenAI Responses API error status=%s body=%r",
                            response.status,
                            body,
                        )
                        return None
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            log.warning("OpenAI Responses API request failed: %s", exc)
            return None

        if not isinstance(body, dict):
            return None
        answer = _extract_output_text(body)
        if not answer:
            log.warning("OpenAI Responses API returned no output text: %r", body)
            return None
        return answer
