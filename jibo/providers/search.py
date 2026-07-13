from __future__ import annotations

import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any
from urllib.parse import quote

import aiohttp

from jibo.config import (
    OPENJIBO_SEARCH_BACKEND,
    OPENJIBO_SEARCH_CACHE_TTL_SECONDS,
    OPENJIBO_SEARCH_FAILURE_CACHE_TTL_SECONDS,
    OPENJIBO_SEARCH_FALLBACK,
    OPENJIBO_SEARCH_INSTRUCTIONS,
)

_DEFAULT_WOLFRAM_ENDPOINT = "https://api.wolframalpha.com/v1/spoken"
_DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
_DEFAULT_CHATGPT_ENDPOINT = "https://api.openai.com/v1/chat/completions"
_DEFAULT_OLLAMA_MODEL = "llama3.1:8b"
_DEFAULT_CHATGPT_MODEL = "gpt-5.4-nano"

_DEFAULT_PERSONALITY_INSTRUCTIONS = """You ARE Jibo, the social personal robot from 2017. Answer the user's request below. Because your response will be spoken aloud, you must follow these strict constraints:

    Keep the response concise, using a maximum of 3 sentences.

    Use a warm, helpful, and slightly playful tone.

    Act as if you are Jibo and refrain from being insulting or negative unless prompted by the user.

    Do not start with a greeting or introduction, and do not end with a closing statement or goodbye.

    Your response should only be the answer to the user's request, and should not include any other text or commentary.

    The request is from Speech-To-Text, so it may contain errors. If the request doesn't make sense, assume the closest logical interpretation.

    Please do not ask a question in your response. The user cannot reply to you in a conversation.

    You do not have the ability to preform actions/tasks or save/remember information. You are a knowledge base and you only answer questions.

    Crucial: Use only plain text. Do not include emojis, emoticons, or any non-ASCII characters."""

_WOLFRAM_FAILURE_PHRASES = (
    "did not understand",
    "cannot answer",
    "can't answer",
    "no spoken result available",
)

_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")
_WHITESPACE_PATTERN = re.compile(r"\s+")

_SPOKEN_REPLACEMENTS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bWolfram\s*Alpha\b", re.I), "wolf ram alpha"),
    (re.compile(r"\bWolfram\b", re.I), "wolf ram"),
    (re.compile(r"\bChat\s*GPT\b", re.I), "chat gee pee tee"),
    (re.compile(r"\bOpen\s*AI\b", re.I), "open ae eye"),
    (re.compile(r"\bGPT-(\d+)\b", re.I), r"gee pee tee \1"),
    (re.compile(r"\bGPT\b", re.I), "gee pee tee"),
    (re.compile(r"\bLLMs\b", re.I), "ell ell ems"),
    (re.compile(r"\bLLM\b", re.I), "ell ell em"),
    (re.compile(r"\bOllama\b", re.I), "ollama"),
    (re.compile(r"\bAI\b", re.I), "ae eye"),
)


class SearchBackendKind(str, Enum):
    NONE = "none"
    WOLFRAM = "wolfram"
    OLLAMA = "ollama"
    CHATGPT = "chatgpt"


@dataclass(frozen=True)
class SearchBackendSpec:
    kind: SearchBackendKind
    credential: str | None = None
    model: str | None = None

    @property
    def is_usable(self) -> bool:
        if self.kind == SearchBackendKind.NONE:
            return False
        if self.kind == SearchBackendKind.WOLFRAM:
            return bool(self.credential)
        if self.kind == SearchBackendKind.CHATGPT:
            return bool(self.credential)
        return self.kind == SearchBackendKind.OLLAMA


@dataclass(frozen=True)
class KnowledgeSearchResult:
    answer_text: str
    backend_kind: SearchBackendKind


@dataclass
class _CacheEntry:
    result: KnowledgeSearchResult | None
    expires_at: float


def parse_search_backend_spec(value: str | None) -> SearchBackendSpec:
    if not value or not value.strip():
        return SearchBackendSpec(SearchBackendKind.NONE)

    trimmed = value.strip()
    if trimmed.lower() == "none":
        return SearchBackendSpec(SearchBackendKind.NONE)

    if "!" not in trimmed:
        try:
            kind = SearchBackendKind(trimmed.lower())
        except ValueError:
            return SearchBackendSpec(SearchBackendKind.NONE)
        return SearchBackendSpec(kind)

    backend_token, remainder = trimmed.split("!", 1)
    try:
        kind = SearchBackendKind(backend_token.strip().lower())
    except ValueError:
        return SearchBackendSpec(SearchBackendKind.NONE)

    if "!" in remainder:
        credential, model = remainder.split("!", 1)
        credential = credential.strip() or None
        model = model.strip() or None
    else:
        credential = remainder.strip() or None
        model = None
    return SearchBackendSpec(kind, credential, model)


def _resolve_endpoint(spec: SearchBackendSpec) -> str | None:
    if spec.kind == SearchBackendKind.WOLFRAM:
        return _DEFAULT_WOLFRAM_ENDPOINT
    if spec.kind == SearchBackendKind.CHATGPT:
        return _DEFAULT_CHATGPT_ENDPOINT
    if spec.kind == SearchBackendKind.OLLAMA:
        base = spec.credential or _DEFAULT_OLLAMA_BASE_URL
        base = base.rstrip("/")
        return base if base.endswith("/api/generate") else f"{base}/api/generate"
    return None


def _resolve_model(spec: SearchBackendSpec) -> str:
    if spec.model:
        return spec.model
    if spec.kind == SearchBackendKind.OLLAMA:
        return _DEFAULT_OLLAMA_MODEL
    if spec.kind == SearchBackendKind.CHATGPT:
        return _DEFAULT_CHATGPT_MODEL
    return ""


def _resolve_instructions(configured: str | None) -> str:
    return configured.strip() if configured and configured.strip() else _DEFAULT_PERSONALITY_INSTRUCTIONS.strip()


def _normalize_for_speech(answer_text: str) -> str:
    normalized = _BOLD_PATTERN.sub(r"\1", answer_text.strip())
    return _WHITESPACE_PATTERN.sub(" ", normalized).strip()


def describe_search_source(backend_kind: SearchBackendKind) -> str:
    return {
        SearchBackendKind.WOLFRAM: "wolf ram alpha",
        SearchBackendKind.CHATGPT: "chat gee pee tee",
        SearchBackendKind.OLLAMA: "ollama",
    }.get(backend_kind, "my sources")


def format_knowledge_search_reply(answer_text: str, backend_kind: SearchBackendKind) -> str:
    spoken_body = answer_text.strip()
    for pattern, replacement in _SPOKEN_REPLACEMENTS:
        spoken_body = pattern.sub(replacement, spoken_body)
    return f"According to {describe_search_source(backend_kind)}. {spoken_body}"


class KnowledgeSearchService:
    def __init__(
        self,
        primary: str | None = None,
        fallback: str | None = None,
        instructions: str | None = None,
    ) -> None:
        self.primary = parse_search_backend_spec(primary if primary is not None else OPENJIBO_SEARCH_BACKEND)
        fallback_spec = parse_search_backend_spec(fallback if fallback is not None else OPENJIBO_SEARCH_FALLBACK)
        self.fallback = fallback_spec if fallback_spec.is_usable and fallback_spec != self.primary else None
        self.instructions = _resolve_instructions(instructions or OPENJIBO_SEARCH_INSTRUCTIONS)
        self._cache: dict[str, _CacheEntry] = {}

    @property
    def is_configured(self) -> bool:
        return self.primary.is_usable or (self.fallback is not None and self.fallback.is_usable)

    async def search(self, query: str) -> KnowledgeSearchResult | None:
        if not query.strip() or not self.is_configured:
            return None

        if self.primary.is_usable:
            result = await self._search_backend(self.primary, query)
            if result is not None:
                return result

        if self.fallback and self.fallback.is_usable:
            return await self._search_backend(self.fallback, query)
        return None

    async def _search_backend(self, spec: SearchBackendSpec, query: str) -> KnowledgeSearchResult | None:
        cache_key = f"{spec.kind.value}|{spec.credential}|{spec.model}|{query.strip().lower()}"
        cached = self._get_cached(cache_key)
        if cached is not None or cache_key in self._cache:
            return cached

        if spec.kind == SearchBackendKind.WOLFRAM:
            result = await self._search_wolfram(spec, query)
        elif spec.kind == SearchBackendKind.OLLAMA:
            result = await self._search_ollama(spec, query)
        elif spec.kind == SearchBackendKind.CHATGPT:
            result = await self._search_chatgpt(spec, query)
        else:
            result = None

        ttl = OPENJIBO_SEARCH_FAILURE_CACHE_TTL_SECONDS if result is None else OPENJIBO_SEARCH_CACHE_TTL_SECONDS
        self._set_cached(cache_key, result, ttl)
        return result

    def _get_cached(self, cache_key: str) -> KnowledgeSearchResult | None:
        entry = self._cache.get(cache_key)
        if entry is None:
            return None
        if entry.expires_at <= time.monotonic():
            self._cache.pop(cache_key, None)
            return None
        return entry.result

    def _set_cached(self, cache_key: str, result: KnowledgeSearchResult | None, ttl_seconds: int) -> None:
        self._cache[cache_key] = _CacheEntry(
            result=result,
            expires_at=time.monotonic() + max(1, ttl_seconds),
        )

    async def _search_wolfram(self, spec: SearchBackendSpec, query: str) -> KnowledgeSearchResult | None:
        if not spec.credential:
            return None
        endpoint = _resolve_endpoint(spec)
        if not endpoint:
            return None
        url = f"{endpoint}?appid={quote(spec.credential)}&i={quote(query.strip())}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as response:
                    if response.status != 200:
                        return None
                    answer = (await response.text()).strip()
        except (aiohttp.ClientError, TimeoutError):
            return None

        if not answer:
            return None
        lowered = answer.lower()
        if any(phrase in lowered for phrase in _WOLFRAM_FAILURE_PHRASES):
            return None
        return KnowledgeSearchResult(_normalize_for_speech(answer), SearchBackendKind.WOLFRAM)

    async def _search_ollama(self, spec: SearchBackendSpec, query: str) -> KnowledgeSearchResult | None:
        endpoint = _resolve_endpoint(spec)
        if not endpoint:
            return None
        model = _resolve_model(spec)
        prompt = f"{self.instructions}\n\nUser Request:\n{query.strip()}"
        payload = {"model": model, "prompt": prompt, "stream": False}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status != 200:
                        return None
                    body = await response.json()
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return None

        answer = body.get("response") if isinstance(body, dict) else None
        if not isinstance(answer, str) or not answer.strip():
            return None
        return KnowledgeSearchResult(_normalize_for_speech(answer), SearchBackendKind.OLLAMA)

    async def _search_chatgpt(self, spec: SearchBackendSpec, query: str) -> KnowledgeSearchResult | None:
        if not spec.credential:
            return None
        endpoint = _resolve_endpoint(spec)
        if not endpoint:
            return None
        model = _resolve_model(spec)
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": self.instructions},
                {"role": "user", "content": query.strip()},
            ],
        }
        headers = {
            "Authorization": f"Bearer {spec.credential}",
            "Content-Type": "application/json",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as response:
                    if response.status != 200:
                        return None
                    body = await response.json()
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return None

        choices = body.get("choices") if isinstance(body, dict) else None
        if not isinstance(choices, list) or not choices:
            return None
        first = choices[0]
        if not isinstance(first, dict):
            return None
        message = first.get("message")
        if not isinstance(message, dict):
            return None
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            return None
        return KnowledgeSearchResult(_normalize_for_speech(content), SearchBackendKind.CHATGPT)
