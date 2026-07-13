from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from jibo.normalize import matches_any, normalize_transcript

_WEATHER_LOCATION_PATTERN = re.compile(
    r"\b(?:in|for|at)\s+(?P<location>[a-z][a-z\s'\-]+)$",
    re.I,
)
_WEATHER_LOCATION_SUFFIX_PATTERN = re.compile(
    r"\b(?:today|tonight|tomorrow|day after tomorrow|outside|right now|please|thanks|"
    r"this weekend|next weekend|the weekend|weekend|this week|next week|"
    r"on monday|on tuesday|on wednesday|on thursday|on friday|on saturday|on sunday|"
    r"this monday|this tuesday|this wednesday|this thursday|this friday|this saturday|this sunday|"
    r"next monday|next tuesday|next wednesday|next thursday|next friday|next saturday|next sunday|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.I,
)
_WEATHER_TOPIC_LOCATION_PATTERN = re.compile(
    r"\b(?:weather|forecast|temperature|humidity)\b.*\b(?:in|for|at)\s+[a-z]",
    re.I,
)
_WEATHER_CONDITION_FORECAST_PATTERN = re.compile(
    r"\bwill it be\s+(sunny|cloudy|windy|foggy|stormy|rainy|snowy|hail|hailing)\b",
    re.I,
)
_WEATHER_DAY_OF_WEEK_PATTERN = re.compile(
    r"\b(?P<next>next\s+)?(?P<this>this\s+)?(?:on\s+)?(?P<day>monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.I,
)

_GENERIC_WEATHER_LOCATION_TERMS = {
    "my area",
    "our area",
    "this area",
    "the area",
    "the city",
    "this city",
    "our city",
    "my city",
    "the town",
    "this town",
    "our town",
    "my town",
    "our street",
    "this street",
    "my street",
    "the neighborhood",
    "the neighbourhood",
    "this neighborhood",
    "this neighbourhood",
    "our neighborhood",
    "our neighbourhood",
}

_WEEKDAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


@dataclass
class WeatherDateEntity:
    date_entity: str | None
    forecast_day_offset: int
    forecast_lead_in: str | None

    @classmethod
    def none(cls) -> WeatherDateEntity:
        return cls(None, 0, None)


@dataclass
class WeatherRequest:
    location_query: str | None
    forecast_day_offset: int
    forecast_lead_in: str | None
    use_celsius: bool


def is_weather_request(transcript: str) -> bool:
    normalized = normalize_transcript(transcript)
    if not normalized:
        return False

    if _is_weather_topic_question(normalized):
        return True

    if matches_any(
        normalized,
        "weather",
        "forecast",
        "how is the weather",
        "how s the weather",
        "check the weather",
        "weather report",
        "what s today s weather",
        "what is the weather",
        "what will the weather",
        "what will tomorrow s weather",
        "look up the forecast",
        "launch the weather skill",
        "what is today s humidity",
        "what s the humidity",
        "what is the humidity",
        "what s today s forecast",
        "what is today s forecast",
        "what s today s weather look like",
        "what is today s weather look like",
        "whats the weather",
        "what s the weather",
        "whats the weather today",
        "what s the weather today",
    ):
        return True

    return matches_any(
        normalized,
        "will it rain",
        "will it snow",
        "is it raining",
        "is it snowing",
        "is there going to be hail",
        "does it look like rain",
        "does it seem like snow",
        "is it going to rain",
        "is it going to snow",
        "do you think it will rain",
        "do you think it will snow",
    ) or bool(_WEATHER_CONDITION_FORECAST_PATTERN.search(normalized))


def parse_weather_request(transcript: str, use_celsius: bool = False) -> WeatherRequest:
    normalized = normalize_transcript(transcript)
    location_query = resolve_weather_location_query(normalized)
    weather_date = resolve_weather_date_entity(normalized)
    return WeatherRequest(
        location_query=location_query,
        forecast_day_offset=weather_date.forecast_day_offset,
        forecast_lead_in=weather_date.forecast_lead_in,
        use_celsius=use_celsius,
    )


def resolve_weather_location_query(normalized_transcript: str) -> str | None:
    match = _WEATHER_LOCATION_PATTERN.search(normalized_transcript)
    if not match:
        return None

    candidate = match.group("location").strip()
    candidate = _WEATHER_LOCATION_SUFFIX_PATTERN.sub("", candidate).strip()
    if not candidate or candidate.lower() in _GENERIC_WEATHER_LOCATION_TERMS:
        return None

    return candidate.title()


def resolve_weather_date_entity(normalized_transcript: str, reference: date | None = None) -> WeatherDateEntity:
    if not normalized_transcript:
        return WeatherDateEntity.none()

    if "day after tomorrow" in normalized_transcript:
        return WeatherDateEntity("day_after_tomorrow", 2, "The day after tomorrow")

    if matches_any(normalized_transcript, "tomorrow", "tomorrow s"):
        return WeatherDateEntity("tomorrow", 1, "Tomorrow")

    reference_date = reference or date.today()
    day_match = _WEATHER_DAY_OF_WEEK_PATTERN.search(normalized_transcript)
    if day_match:
        day_name = day_match.group("day").lower()
        if day_name in _WEEKDAYS:
            target_weekday = _WEEKDAYS.index(day_name)
            current_weekday = reference_date.weekday()
            offset = (target_weekday - current_weekday) % 7
            if offset == 0 or day_match.group("next"):
                offset = 7 if offset == 0 else offset
            if day_match.group("this") and offset > 0:
                pass
            return WeatherDateEntity("weekday", offset, f"On {day_name.title()}")

    return WeatherDateEntity.none()


def _is_weather_topic_question(normalized_transcript: str) -> bool:
    mentions_weather_topic = any(
        token in normalized_transcript
        for token in ("weather", "forecast", "temperature", "humidity")
    )
    if not mentions_weather_topic:
        return False

    if normalized_transcript.startswith(
        (
            "what ",
            "how ",
            "check ",
            "show ",
            "tell ",
            "look up ",
            "launch ",
            "give me ",
            "temperature ",
            "forecast ",
            "weather ",
        )
    ):
        return True

    return bool(_WEATHER_TOPIC_LOCATION_PATTERN.search(normalized_transcript))
