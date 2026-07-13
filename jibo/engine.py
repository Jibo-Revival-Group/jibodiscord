from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime

from jibo.catalog import Catalog, load_catalog
from jibo.config import CLOUD_VERSION, PERSONA_BIRTHDAY, PERSONA_BIRTHDAY_WORDS, USE_FUN_FACT_API
from jibo.intent_router import resolve_semantic_intent
from jibo.news.formatter import build_news_reply
from jibo.normalize import normalize_transcript
from jibo.parsers.define import try_parse_define_word
from jibo.parsers.dice import (
    INVALID_SIDES_REPLY,
    format_dice_reply,
    roll_dice,
    try_parse_dice,
)
from jibo.parsers.math import evaluate_math, format_math_reply, try_parse_math
from jibo.providers.dictionary import DictionaryProvider
from jibo.providers.fun_facts import FunFactProvider
from jibo.providers.news_api import NewsProvider
from jibo.providers.search import KnowledgeSearchService, format_knowledge_search_reply
from jibo.weather.formatter import build_weather_spoken_reply, choose_weather_service_down_reply
from jibo.weather.parser import WeatherDateEntity, parse_weather_request
from jibo.weather.provider import OpenWeatherProvider


@dataclass
class JiboResponse:
    intent: str
    text: str


class JiboEngine:
    def __init__(
        self,
        catalog: Catalog | None = None,
        mim_prompt_count: int = 0,
        weather_provider: OpenWeatherProvider | None = None,
        fun_fact_provider: FunFactProvider | None = None,
        dictionary_provider: DictionaryProvider | None = None,
        news_provider: NewsProvider | None = None,
        knowledge_search: KnowledgeSearchService | None = None,
    ) -> None:
        self.catalog = catalog or Catalog()
        self.mim_prompt_count = mim_prompt_count
        self.weather_provider = weather_provider or OpenWeatherProvider()
        self.fun_fact_provider = fun_fact_provider or FunFactProvider()
        self.dictionary_provider = dictionary_provider or DictionaryProvider()
        self.news_provider = news_provider or NewsProvider()
        self.knowledge_search = knowledge_search or KnowledgeSearchService()

    @classmethod
    def create(cls, openjibo_path=None) -> "JiboEngine":
        catalog, mim_count = load_catalog(openjibo_path)
        return cls(catalog=catalog, mim_prompt_count=mim_count)

    def ask(self, transcript: str) -> JiboResponse:
        cleaned = transcript.strip()
        intent = resolve_semantic_intent(cleaned)
        text = self._build_reply(intent, cleaned)
        return JiboResponse(intent=intent, text=text)

    async def ask_async(self, transcript: str) -> JiboResponse:
        cleaned = transcript.strip()
        intent = resolve_semantic_intent(cleaned)
        text = await self._build_reply_async(intent, cleaned)
        return JiboResponse(intent=intent, text=text)

    def _choose(self, replies: list[str]) -> str:
        if not replies:
            return "Hmm. I am not sure what to say to that yet."
        return random.choice(replies)

    def _choose_with_snippets(self, replies: list[str], *snippets: str) -> str:
        for snippet in snippets:
            if not snippet:
                continue
            for reply in replies:
                if snippet.lower() in reply.lower():
                    return reply
        return self._choose(replies)

    def _describe_age(self, reference: date | None = None) -> str:
        today = reference or date.today()
        days = max(0, (today - PERSONA_BIRTHDAY).days)
        if days == 0:
            return "less than one day old"
        if days == 1:
            return "1 day old"
        return f"{days} days old"

    def _render_age_reply(self) -> str:
        age_description = self._describe_age()
        template = self._choose(self.catalog.age_replies)
        return (
            template.replace("{age_description}", age_description)
            .replace("{birthdate}", PERSONA_BIRTHDAY_WORDS)
            .replace("{age_days}", str(max(0, (date.today() - PERSONA_BIRTHDAY).days)))
        )

    def _generic_fallback(self, transcript: str) -> str:
        echo_templates = [r for r in self.catalog.generic_fallback_replies if "{transcript}" in r]
        template = self._choose(echo_templates or self.catalog.generic_fallback_replies)
        return template.replace("{transcript}", transcript)

    def _greeting_for_time(self, prefix: str) -> str:
        return f"{prefix}. It is nice to see you."

    def _resolve_countdown_holiday(self, transcript: str) -> tuple[str, date] | None:
        lowered = normalize_transcript(transcript)
        if "until " not in lowered:
            return None
        holiday_phrase = lowered.split("until ", 1)[1].strip()
        if not holiday_phrase:
            return None

        aliases = {
            "christmas": "Christmas Day",
            "xmas": "Christmas Day",
            "new year": "New Year's Day",
            "new years": "New Year's Day",
            "new years day": "New Year's Day",
            "halloween": "Halloween",
            "thanksgiving": "Thanksgiving Day",
        }
        name = aliases.get(holiday_phrase)
        if not name:
            return None

        today = date.today()
        month_day = {
            "Christmas Day": (12, 25),
            "New Year's Day": (1, 1),
            "Halloween": (10, 31),
            "Thanksgiving Day": (11, 25),
        }[name]
        target = date(today.year, month_day[0], month_day[1])
        if target < today:
            target = date(today.year + 1, month_day[0], month_day[1])
        return name, target

    def _render_countdown_reply(self, transcript: str) -> str:
        resolved = self._resolve_countdown_holiday(transcript)
        if not resolved:
            return self._generic_fallback(transcript)
        name, target = resolved
        days = (target - date.today()).days
        day_word = "day" if days == 1 else "days"
        return f"There are {days} {day_word} until {name}."

    async def _fetch_fun_fact(self) -> str | None:
        if not USE_FUN_FACT_API:
            return None
        return await self.fun_fact_provider.fetch_random_fact()

    async def _build_define_reply(self, transcript: str) -> str:
        word = try_parse_define_word(transcript)
        if not word:
            return (
                "I didn't catch what word you wanted me to define. "
                "Can you ask me again with a hey jibo?"
            )

        if not self.dictionary_provider.is_configured:
            return "I couldn't find a definition for that word."

        definition = await self.dictionary_provider.lookup_definition(word)
        if not definition:
            return "I couldn't find a definition for that word."
        return f"The definition is. {definition}"

    async def _build_news_reply(self, transcript: str) -> str:
        reply = await build_news_reply(transcript, self.catalog, self.news_provider)
        return reply.text

    async def _try_knowledge_search_reply(self, transcript: str) -> str | None:
        if not self.knowledge_search.is_configured:
            return None

        query = normalize_transcript(transcript).strip()
        if not query:
            return None

        result = await self.knowledge_search.search(query)
        if result is None or not result.answer_text.strip():
            return None
        return format_knowledge_search_reply(result.answer_text, result.backend_kind)

    async def _build_reply_async(self, intent: str, transcript: str) -> str:
        if intent == "fun_fact":
            fact = await self._fetch_fun_fact()
            if fact:
                return fact
        if intent == "weather":
            return await self._build_weather_reply(transcript)
        if intent == "news":
            return await self._build_news_reply(transcript)
        if intent == "define_word":
            return await self._build_define_reply(transcript)
        if intent == "chat":
            search_reply = await self._try_knowledge_search_reply(transcript)
            if search_reply:
                return search_reply
        return self._build_reply(intent, transcript)

    async def _build_weather_reply(self, transcript: str) -> str:
        catalog = self.catalog
        if not self.weather_provider.is_configured:
            return choose_weather_service_down_reply(catalog)

        request = parse_weather_request(transcript, use_celsius=self.weather_provider.default_use_celsius)
        snapshot = await self.weather_provider.get_report(
            location_query=request.location_query,
            forecast_day_offset=request.forecast_day_offset,
            use_celsius=request.use_celsius,
        )
        if snapshot is None:
            return choose_weather_service_down_reply(catalog)

        weather_date = WeatherDateEntity(
            date_entity="tomorrow" if request.forecast_day_offset == 1 else None,
            forecast_day_offset=request.forecast_day_offset,
            forecast_lead_in=request.forecast_lead_in,
        )
        return build_weather_spoken_reply(snapshot, weather_date, catalog)

    def _build_reply(self, intent: str, transcript: str) -> str:
        catalog = self.catalog

        if intent == "joke":
            return self._choose(catalog.jokes)
        if intent == "fun_fact":
            return self._choose(catalog.fun_fact_fallbacks)
        if intent == "math_query":
            query = try_parse_math(transcript)
            if query:
                return format_math_reply(query, evaluate_math(query))
            return "I couldn't figure that one out."
        if intent == "roll_dice":
            query = try_parse_dice(transcript)
            if not query:
                return INVALID_SIDES_REPLY
            result = roll_dice(query.sides)
            return format_dice_reply(query.sides, result)
        if intent == "dance":
            dance = self._choose(catalog.dance_replies)
            animation = self._choose(catalog.dance_animations)
            return f"{dance} *does the {animation.replace('rom-', '')} dance*"
        if intent == "dance_question":
            return self._choose(catalog.dance_question_replies)
        if intent == "twerk":
            return "Watch me twerk. *does a little robot twerk*"
        if intent == "hello":
            return self._choose(catalog.greeting_replies)
        if intent == "how_are_you":
            return self._choose(catalog.how_are_you_replies)
        if intent == "good_morning":
            return self._greeting_for_time("Good morning")
        if intent == "good_afternoon":
            return self._greeting_for_time("Good afternoon")
        if intent == "good_evening":
            return self._greeting_for_time("Good evening")
        if intent == "good_night":
            return self._greeting_for_time("Good night")
        if intent == "welcome_back":
            return self._choose_with_snippets(catalog.greeting_replies, "welcome back", "nice to be here")
        if intent == "robot_personality":
            return self._choose_with_snippets(
                catalog.personality_replies, "curious", "playful", "friendly", "personality"
            )
        if intent == "robot_favorite_color":
            return self._choose_with_snippets(
                catalog.personality_replies,
                "blue is my favorite",
                "colors of the rainbow",
                "big fan of blue",
            )
        if intent == "robot_favorite_food":
            return self._choose_with_snippets(
                catalog.personality_replies, "macaroni", "never eat", "favorite food"
            )
        if intent == "robot_favorite_joke":
            return self._choose_with_snippets(catalog.personality_replies, "all jokes", "especially funny")
        if intent == "robot_how_old_are_you":
            return self._render_age_reply()
        if intent == "robot_birthday":
            return f"My birthday is {PERSONA_BIRTHDAY_WORDS}."
        if intent == "robot_favorite_animal":
            return self._choose(catalog.favorite_animal_replies)
        if intent == "robot_identity":
            return self._choose_with_snippets(
                catalog.personality_replies,
                "i am a robot",
                "i m just jibo",
                "just jibo",
            )
        if intent == "robot_has_friends":
            return self._choose(catalog.friend_replies)
        if intent == "robot_best_friends":
            return self._choose(catalog.best_friend_replies)
        if intent == "robot_can_sing":
            return self._choose(catalog.sing_replies)
        if intent == "robot_can_dance":
            return self._choose(catalog.dance_question_replies)
        if intent == "robot_story":
            return self._choose(catalog.story_replies)
        if intent == "robot_recommend_movie":
            return self._choose(catalog.recommend_movie_replies)
        if intent == "robot_can_dream":
            return self._choose(catalog.can_dream_replies)
        if intent == "robot_can_fly":
            return self._choose(catalog.can_fly_replies)
        if intent == "robot_can_walk":
            return self._choose(catalog.can_walk_replies)
        if intent == "robot_can_read":
            return self._choose(catalog.can_read_replies)
        if intent == "robot_can_hear":
            return self._choose(catalog.can_hear_replies)
        if intent == "robot_can_talk":
            return self._choose(catalog.can_talk_replies)
        if intent == "robot_can_see":
            return self._choose(catalog.can_see_replies)
        if intent == "surprise":
            return self._choose(catalog.surprise_replies)
        if intent == "pizza":
            return self._choose(catalog.pizza_replies)
        if intent == "news":
            return self._choose(catalog.news_replies)
        if intent == "define_word":
            return "I couldn't find a definition for that word."
        if intent == "radio":
            return "Opening the radio."
        if intent == "radio_genre_pop":
            return "Opening pop radio."
        if intent == "radio_genre_rock":
            return "Opening rock radio."
        if intent == "radio_genre_jazz":
            return "Opening jazz radio."
        if intent == "countdown":
            return self._render_countdown_reply(transcript)
        if intent == "cloud_version":
            return f"Cloud version {CLOUD_VERSION}."
        if intent == "time":
            return f"Showing the time. It is {datetime.now().strftime('%-I:%M %p')}."
        if intent == "date":
            return f"Showing the date. Today is {datetime.now().strftime('%B %d, %Y')}."
        if intent == "day":
            return f"Showing the day. Today is {datetime.now().strftime('%A')}."
        if intent == "robot_what_does_jibo_mean":
            return self._choose_with_snippets(
                catalog.personality_replies, "meaning", "jibo means", "name jibo"
            ) or "Jibo is my name. I like it."

        if intent == "chat":
            normalized = normalize_transcript(transcript)
            if not normalized:
                return "Hi there. What would you like to talk about?"
            return self._generic_fallback(transcript)

        return self._generic_fallback(transcript)
