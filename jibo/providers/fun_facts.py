from __future__ import annotations

import aiohttp

from jibo.config import USELESS_FACTS_BASE_URL


class FunFactProvider:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or USELESS_FACTS_BASE_URL or "https://uselessfacts.jsph.pl").rstrip("/")

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url)

    async def fetch_random_fact(self) -> str | None:
        if not self.is_configured:
            return None

        url = f"{self.base_url}/api/v2/facts/random"
        headers = {
            "Accept": "application/json",
            "User-Agent": "OpenJiboFunFactBot/1.0",
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=4),
                ) as response:
                    if response.status != 200:
                        return None
                    payload = await response.json()
                    text = payload.get("text")
                    return text.strip() if isinstance(text, str) and text.strip() else None
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return None
