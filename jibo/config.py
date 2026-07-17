import os
from datetime import date
from pathlib import Path

from jibo.openjibo_settings import (
    configure_appsettings_path,
    resolve_bool_setting,
    resolve_int_setting,
    resolve_list_setting,
    resolve_setting,
)

PERSONA_BIRTHDAY = date(2026, 3, 22)
PERSONA_BIRTHDAY_WORDS = PERSONA_BIRTHDAY.strftime("%B %d, %Y")
CLOUD_VERSION = "1.0.20"

DEFAULT_OPENJIBO_PATH = Path.home() / "JiboExperiments" / "OpenJibo"
OPENJIBO_PATH = Path(os.environ.get("OPENJIBO_PATH", DEFAULT_OPENJIBO_PATH))

LEGACY_MIMS_DIRS = (
    "src/Jibo.Cloud/dotnet/src/Jibo.Cloud.Infrastructure/Content/LegacyMims/BuildA",
    "src/Jibo.Cloud/dotnet/src/Jibo.Cloud.Infrastructure/Content/LegacyMims/BuildB",
    "src/Jibo.Cloud/dotnet/src/Jibo.Cloud.Infrastructure/Content/LegacyMims/ReportSkill",
)

OPENJIBO_APPSETTINGS_PATH = (
    OPENJIBO_PATH / "src/Jibo.Cloud/dotnet/src/Jibo.Cloud.Api/appsettings.json"
)
configure_appsettings_path(OPENJIBO_APPSETTINGS_PATH)

USE_FUN_FACT_API = os.environ.get("USE_FUN_FACT_API", "true").lower() in ("1", "true", "yes")

# Weather (OpenWeather)
OPENWEATHER_API_KEY = resolve_setting(
    "OPENWEATHER_API_KEY",
    ("Weather", "OpenWeather"),
    "ApiKey",
)
OPENWEATHER_BASE_URL = resolve_setting(
    "OPENWEATHER_BASE_URL",
    ("Weather", "OpenWeather"),
    "BaseUrl",
    "https://api.openweathermap.org",
)
OPENWEATHER_DEFAULT_LOCATION = resolve_setting(
    "OPENWEATHER_DEFAULT_LOCATION",
    ("Weather", "OpenWeather"),
    "DefaultLocation",
    "Boston,US",
)
OPENWEATHER_USE_CELSIUS = resolve_bool_setting(
    "OPENWEATHER_USE_CELSIUS",
    ("Weather", "OpenWeather"),
    "UseCelsius",
    default=False,
)

# Fun facts (UselessFacts)
USELESS_FACTS_BASE_URL = resolve_setting(
    "USELESS_FACTS_BASE_URL",
    ("FunFacts", "UselessFacts"),
    "BaseUrl",
    "https://uselessfacts.jsph.pl",
)

# Dictionary (FreeDictionaryApi)
FREE_DICTIONARY_BASE_URL = resolve_setting(
    "FREE_DICTIONARY_BASE_URL",
    ("Dictionary", "FreeDictionaryApi"),
    "BaseUrl",
    "https://freedictionaryapi.com",
)

# News (NewsAPI)
NEWSAPI_KEY = resolve_setting(
    "NEWSAPI_KEY",
    ("News", "NewsApi"),
    "ApiKey",
)
NEWSAPI_BASE_URL = resolve_setting(
    "NEWSAPI_BASE_URL",
    ("News", "NewsApi"),
    "BaseUrl",
    "https://newsapi.org",
)
NEWSAPI_COUNTRY = resolve_setting(
    "NEWSAPI_COUNTRY",
    ("News", "NewsApi"),
    "Country",
    "us",
)
NEWSAPI_LANGUAGE = resolve_setting(
    "NEWSAPI_LANGUAGE",
    ("News", "NewsApi"),
    "Language",
    "en",
)
NEWSAPI_FALLBACK_QUERY = resolve_setting(
    "NEWSAPI_FALLBACK_QUERY",
    ("News", "NewsApi"),
    "FallbackQuery",
    "robotics OR technology OR science",
)
NEWSAPI_DEFAULT_CATEGORIES = resolve_list_setting(
    ("News", "NewsApi"),
    "DefaultCategories",
    ("general", "technology", "sports", "business"),
)

# Knowledge search (Wolfram / Ollama / ChatGPT)
OPENJIBO_SEARCH_BACKEND = resolve_setting(
    "OPENJIBO_SEARCH_BACKEND",
    ("Search",),
    "Primary",
    extra_env_names=("OPENJIBO_SEARCH_PRIMARY",),
)
OPENJIBO_SEARCH_FALLBACK = resolve_setting(
    "OPENJIBO_SEARCH_FALLBACK",
    ("Search",),
    "Fallback",
)
OPENJIBO_SEARCH_INSTRUCTIONS = resolve_setting(
    "OPENJIBO_SEARCH_INSTRUCTIONS",
    ("Search",),
    "Instructions",
)
OPENJIBO_SEARCH_CACHE_TTL_SECONDS = resolve_int_setting(
    "OPENJIBO_SEARCH_CACHE_TTL_SECONDS",
    ("Search",),
    "CacheTtlSeconds",
    300,
)
OPENJIBO_SEARCH_FAILURE_CACHE_TTL_SECONDS = resolve_int_setting(
    "OPENJIBO_SEARCH_FAILURE_CACHE_TTL_SECONDS",
    ("Search",),
    "FailureCacheTtlSeconds",
    45,
)


def _chatgpt_api_key_from_search_backend() -> str | None:
    """Extract an OpenAI key from OpenJibo chatgpt!KEY[!MODEL] search specs."""
    for value in (OPENJIBO_SEARCH_BACKEND, OPENJIBO_SEARCH_FALLBACK):
        if not value:
            continue
        parts = value.split("!")
        if len(parts) >= 2 and parts[0].strip().lower() == "chatgpt":
            key = parts[1].strip()
            if key:
                return key
    return None


# Discord RAG (/ai, !ai) — Responses API + file_search
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or _chatgpt_api_key_from_search_backend()
OPENAI_AI_MODEL = os.environ.get("OPENAI_AI_MODEL", "gpt-4.1-mini")
OPENAI_VECTOR_STORE_ID = os.environ.get(
    "OPENAI_VECTOR_STORE_ID",
    "vs_6a5a46ef89408191bb8ce3cf2a6f132d",
)

# Only stay in / respond in this guild; leave all others
_raw_guild_id = os.environ.get("DISCORD_GUILD_ID", "").strip()
DISCORD_GUILD_ID: int | None = int(_raw_guild_id) if _raw_guild_id.isdigit() else None
