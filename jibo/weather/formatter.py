from __future__ import annotations

import random
import re

from jibo.catalog import Catalog
from jibo.weather.parser import WeatherDateEntity
from jibo.weather.provider import WeatherReportSnapshot

_SPOKEN_ABBREVIATIONS = {
    "US",
    "USA",
    "UK",
    "UAE",
    "EU",
    "DC",
}


def build_weather_spoken_reply(
    snapshot: WeatherReportSnapshot,
    weather_date: WeatherDateEntity,
    catalog: Catalog,
) -> str:
    unit = "Celsius" if snapshot.use_celsius else "Fahrenheit"
    summary = (snapshot.summary or "partly cloudy").strip().rstrip(".")
    location = _normalize_location_for_speech(snapshot.location_name or "your area")

    if weather_date.forecast_day_offset > 0:
        if weather_date.forecast_day_offset != 1:
            high_text = (
                None
                if snapshot.high_temperature is None
                else f"a high near {snapshot.high_temperature} degrees {unit}"
            )
            low_text = (
                None
                if snapshot.low_temperature is None
                else f"a low around {snapshot.low_temperature} degrees {unit}"
            )
            if high_text and low_text:
                temp_range = f" with {high_text} and {low_text}"
            elif high_text or low_text:
                temp_range = f" with {high_text or low_text}"
            else:
                temp_range = ""
            lead_in = weather_date.forecast_lead_in or "Tomorrow"
            return f"Let's look at the weather. {lead_in} in {location}, it looks {summary}{temp_range}."

        high_value = snapshot.high_temperature or snapshot.temperature
        low_value = snapshot.low_temperature or snapshot.temperature
        intro = _render_weather_template(
            _choose_template(catalog.weather_tomorrow_intro_replies, "Let's look at the weather."),
            location,
            summary,
            high_value,
            low_value,
            unit,
            weather_date.forecast_lead_in or "",
        )
        high_low = _render_weather_template(
            _choose_template(
                catalog.weather_tomorrow_high_low_replies,
                "Tomorrow's high will be {high} and the low will be {low}.",
            ),
            location,
            summary,
            high_value,
            low_value,
            unit,
            weather_date.forecast_lead_in or "",
        )
        lead_in = weather_date.forecast_lead_in or "Tomorrow"
        return f"{intro} {lead_in} in {location}, it looks {summary}. {high_low}"

    intro = _render_weather_template(
        _choose_template(catalog.weather_intro_replies, "For your weather."),
        location,
        summary,
        snapshot.temperature,
        snapshot.temperature,
        unit,
        "",
    )
    high_low = _render_weather_template(
        _choose_template(
            catalog.weather_today_high_low_replies,
            "Today's high is {high}, and the low is {low}.",
        ),
        location,
        summary,
        snapshot.high_temperature or snapshot.temperature,
        snapshot.low_temperature or snapshot.temperature,
        unit,
        "",
    )
    return (
        f"{intro} In {location}, it's {summary} and {snapshot.temperature} degrees {unit}. {high_low}"
    )


def choose_weather_service_down_reply(catalog: Catalog) -> str:
    return _choose_template(
        catalog.weather_service_down_replies,
        "Looks like I can't access weather info right now, sorry.",
    )


def _choose_template(templates: list[str], fallback: str) -> str:
    if not templates:
        return fallback
    return random.choice(templates)


def _render_weather_template(
    template: str,
    location: str,
    summary: str,
    high_temperature: int | None,
    low_temperature: int | None,
    unit: str,
    forecast_lead_in: str,
) -> str:
    high = "" if high_temperature is None else str(high_temperature)
    low = "" if low_temperature is None else str(low_temperature)
    return (
        template.replace("${skill.weather.today.highTemp}", high)
        .replace("${skill.weather.today.lowTemp}", low)
        .replace("${skill.weather.tomorrow.highTemp}", high)
        .replace("${skill.weather.tomorrow.lowTemp}", low)
        .replace("${skill.weather.summary}", summary)
        .replace("${skill.weather.location}", location)
        .replace("${skill.weather.prefix}", forecast_lead_in)
        .replace("{high}", high)
        .replace("{low}", low)
        .replace("{unit}", unit)
        .strip()
    )


def _normalize_location_for_speech(text: str) -> str:
    def replacer(match: re.Match[str]) -> str:
        token = match.group("token")
        if token not in _SPOKEN_ABBREVIATIONS:
            return token
        return ".".join(token) + "."

    return re.sub(r"\b(?P<token>[A-Z]{2,3})\b", replacer, text)
