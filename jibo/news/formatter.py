from __future__ import annotations

import random
import re
from dataclasses import dataclass

from jibo.catalog import Catalog
from jibo.config import NEWSAPI_DEFAULT_CATEGORIES
from jibo.normalize import normalize_transcript
from jibo.providers.news_api import NewsHeadline, NewsProvider

_MAX_HEADLINES = 3
_MAX_PREFERRED_CATEGORIES = 2

_NEWS_CATEGORY_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("sports", "sports"),
    ("sport", "sports"),
    ("football", "sports"),
    ("baseball", "sports"),
    ("basketball", "sports"),
    ("hockey", "sports"),
    ("technology", "technology"),
    ("tech", "technology"),
    ("ai", "technology"),
    ("a i", "technology"),
    ("artificial intelligence", "technology"),
    ("science", "science"),
    ("business", "business"),
    ("finance", "business"),
    ("market", "business"),
    ("stock", "business"),
    ("politics", "general"),
    ("political", "general"),
    ("world", "general"),
    ("entertainment", "entertainment"),
    ("movie", "entertainment"),
    ("music", "entertainment"),
)

_CORRECTION_PREFIX = re.compile(r"^\s*(?:correction|corrected|update|updated)\s*:", re.I)
_UNSAFE_TERM = re.compile(
    r"\b(?:murder|homicide|suicide|porn|pornography|sex\s+crime|sexual\s+assault|"
    r"graphic\s+violence|beheading|massacre)\b",
    re.I,
)
_AI_PATTERN = re.compile(r"\bA\.?\s*I\.?\b", re.I)


def resolve_preferred_news_categories(transcript: str) -> list[str]:
    normalized = normalize_transcript(transcript)
    categories: list[str] = []
    for keyword, category in _NEWS_CATEGORY_KEYWORDS:
        if keyword in normalized:
            _add_category(categories, category)
    return categories[:_MAX_PREFERRED_CATEGORIES]


def _add_category(categories: list[str], category: str) -> None:
    if category.lower() not in {item.lower() for item in categories}:
        categories.append(category)


def _normalize_headline_field(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    return re.sub(r"\s+", " ", value).strip()


def _is_safe_headline(title: str, summary: str) -> bool:
    if _CORRECTION_PREFIX.match(title):
        return False
    return not _UNSAFE_TERM.search(title) and not _UNSAFE_TERM.search(summary)


def _filter_headlines(headlines: list[NewsHeadline]) -> list[NewsHeadline]:
    accepted: list[NewsHeadline] = []
    seen_titles: set[str] = set()
    for headline in headlines:
        title = _normalize_headline_field(headline.title)
        summary = _normalize_headline_field(headline.summary)
        if not title or not summary:
            continue
        if not _is_safe_headline(title, summary):
            continue
        duplicate_key = re.sub(r"\s+", " ", title).strip().lower()
        if duplicate_key in seen_titles:
            continue
        seen_titles.add(duplicate_key)
        accepted.append(NewsHeadline(title=title, summary=summary, category=headline.category))
    return accepted


def _build_lead_in(source_name: str | None, preferred_categories: list[str]) -> str:
    if not preferred_categories:
        lead_in = "Here are a few headlines."
    elif len(preferred_categories) == 1:
        lead_in = f"Here are your {preferred_categories[0]} headlines."
    else:
        lead_in = f"Here are your {preferred_categories[0]} and {preferred_categories[1]} headlines."

    if source_name:
        return f"{lead_in} Source: {source_name}."
    return lead_in


def _normalize_speech_text(text: str) -> str:
    return _AI_PATTERN.sub("artificial intelligence", text)


def _choose_shortest(replies: list[str]) -> str | None:
    if not replies:
        return None
    return min(replies, key=len)


@dataclass
class NewsReply:
    text: str
    used_provider: bool


async def build_news_reply(
    transcript: str,
    catalog: Catalog,
    provider: NewsProvider | None = None,
) -> NewsReply:
    news_provider = provider or NewsProvider()
    preferred_categories = resolve_preferred_news_categories(transcript)
    if not preferred_categories:
        preferred_categories = list(NEWSAPI_DEFAULT_CATEGORIES)

    if news_provider.is_configured:
        snapshot = await news_provider.fetch_briefing(preferred_categories)
        if snapshot and snapshot.headlines:
            filtered = _filter_headlines(snapshot.headlines)[:_MAX_HEADLINES]
            if filtered:
                lead_in = _build_lead_in(snapshot.source_name, preferred_categories[:_MAX_PREFERRED_CATEGORIES])
                joined = " ".join(f"{headline.title}." for headline in filtered)
                outro = _choose_shortest(catalog.news_outro_replies) or "And that's the news."
                spoken = _normalize_speech_text(f"{lead_in} {joined} {outro}".strip())
                return NewsReply(text=spoken, used_provider=True)

    if catalog.news_briefings:
        return NewsReply(text=random.choice(catalog.news_briefings), used_provider=False)
    return NewsReply(text=random.choice(catalog.news_replies), used_provider=False)
