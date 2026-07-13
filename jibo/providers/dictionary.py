from __future__ import annotations

from urllib.parse import quote

import aiohttp

from jibo.config import FREE_DICTIONARY_BASE_URL

_USER_AGENT = "OpenJiboDictionaryBot/1.0"


class DictionaryProvider:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or FREE_DICTIONARY_BASE_URL or "https://freedictionaryapi.com").rstrip("/")

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url)

    async def lookup_definition(self, word: str) -> str | None:
        if not self.is_configured or not word.strip():
            return None

        encoded_word = quote(word.strip().lower())
        url = f"{self.base_url}/api/v1/entries/en/{encoded_word}"
        headers = {
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=4),
                ) as response:
                    if response.status == 404:
                        return None
                    if response.status != 200:
                        return None
                    payload = await response.json()
                    return self._extract_definition(payload)
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return None

    @staticmethod
    def _extract_definition(payload: object) -> str | None:
        if not isinstance(payload, dict):
            return None

        entries = payload.get("entries")
        if not isinstance(entries, list):
            return None

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            senses = entry.get("senses")
            if not isinstance(senses, list):
                continue
            for sense in DictionaryProvider._flatten_senses(senses):
                if not isinstance(sense, dict):
                    continue
                if DictionaryProvider._is_vulgar_sense(sense):
                    continue
                definition = sense.get("definition")
                if isinstance(definition, str) and definition.strip():
                    return definition.strip()
        return None

    @staticmethod
    def _flatten_senses(senses: list[object]) -> list[object]:
        flattened: list[object] = []
        for sense in senses:
            flattened.append(sense)
            if isinstance(sense, dict):
                subsenses = sense.get("subsenses")
                if isinstance(subsenses, list):
                    flattened.extend(DictionaryProvider._flatten_senses(subsenses))
        return flattened

    @staticmethod
    def _is_vulgar_sense(sense: dict[str, object]) -> bool:
        tags = sense.get("tags")
        if not isinstance(tags, list):
            return False
        return any(isinstance(tag, str) and tag.lower() == "vulgar" for tag in tags)
