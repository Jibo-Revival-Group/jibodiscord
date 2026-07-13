from __future__ import annotations

from dataclasses import dataclass

import aiohttp

from jibo.config import (
    NEWSAPI_BASE_URL,
    NEWSAPI_COUNTRY,
    NEWSAPI_FALLBACK_QUERY,
    NEWSAPI_KEY,
    NEWSAPI_LANGUAGE,
)

_USER_AGENT = "OpenJiboNewsBot/1.0"


@dataclass
class NewsHeadline:
    title: str
    summary: str
    category: str | None = None
    source_name: str | None = None
    url: str | None = None


@dataclass
class NewsBriefingSnapshot:
    headlines: list[NewsHeadline]
    source_name: str | None = None
    provider_status: str | None = None


class NewsProvider:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        country: str | None = None,
        language: str | None = None,
        fallback_query: str | None = None,
    ) -> None:
        self.api_key = (api_key or NEWSAPI_KEY or "").strip()
        self.base_url = (base_url or NEWSAPI_BASE_URL or "https://newsapi.org").rstrip("/")
        self.country = (country or NEWSAPI_COUNTRY or "us").strip().lower()
        self.language = (language or NEWSAPI_LANGUAGE or "en").strip().lower()
        self.fallback_query = (fallback_query or NEWSAPI_FALLBACK_QUERY or "").strip()

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def fetch_briefing(self, categories: list[str] | None = None) -> NewsBriefingSnapshot | None:
        if not self.is_configured:
            return None

        category = (categories or [None])[0]
        params: dict[str, str] = {
            "pageSize": "10",
            "language": self.language,
        }
        if category:
            params["category"] = category.lower()
        else:
            params["country"] = self.country

        snapshot = await self._fetch_top_headlines(params)
        if snapshot and snapshot.headlines:
            return snapshot

        if self.fallback_query:
            return await self._fetch_everything(self.fallback_query)
        return snapshot

    async def _fetch_top_headlines(self, params: dict[str, str]) -> NewsBriefingSnapshot | None:
        url = f"{self.base_url}/v2/top-headlines"
        return await self._request(url, params)

    async def _fetch_everything(self, query: str) -> NewsBriefingSnapshot | None:
        url = f"{self.base_url}/v2/everything"
        params = {
            "q": query,
            "pageSize": "10",
            "language": self.language,
            "sortBy": "publishedAt",
        }
        return await self._request(url, params)

    async def _request(self, url: str, params: dict[str, str]) -> NewsBriefingSnapshot | None:
        headers = {
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
            "X-Api-Key": self.api_key,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=6),
                ) as response:
                    if response.status != 200:
                        return NewsBriefingSnapshot(headlines=[], provider_status="http_error")
                    payload = await response.json()
                    return self._parse_payload(payload)
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return NewsBriefingSnapshot(headlines=[], provider_status="exception")

    def _parse_payload(self, payload: object) -> NewsBriefingSnapshot | None:
        if not isinstance(payload, dict):
            return NewsBriefingSnapshot(headlines=[], provider_status="schema_error")

        status = str(payload.get("status", "")).lower()
        if status != "ok":
            return NewsBriefingSnapshot(headlines=[], provider_status="api_error")

        articles = payload.get("articles")
        if not isinstance(articles, list):
            return NewsBriefingSnapshot(headlines=[], provider_status="schema_error")

        headlines: list[NewsHeadline] = []
        source_name: str | None = None
        for article in articles:
            if not isinstance(article, dict):
                continue
            title = article.get("title")
            description = article.get("description") or article.get("content")
            if not isinstance(title, str) or not isinstance(description, str):
                continue
            article_source = article.get("source")
            article_source_name = None
            if isinstance(article_source, dict):
                raw_name = article_source.get("name")
                if isinstance(raw_name, str):
                    article_source_name = raw_name
                    source_name = source_name or raw_name
            headlines.append(
                NewsHeadline(
                    title=title.strip(),
                    summary=description.strip(),
                    source_name=article_source_name,
                    url=article.get("url") if isinstance(article.get("url"), str) else None,
                )
            )

        return NewsBriefingSnapshot(
            headlines=headlines,
            source_name=source_name,
            provider_status="success" if headlines else "empty",
        )
