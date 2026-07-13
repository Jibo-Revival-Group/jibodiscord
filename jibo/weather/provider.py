from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import aiohttp

from jibo.config import (
    OPENWEATHER_API_KEY,
    OPENWEATHER_BASE_URL,
    OPENWEATHER_DEFAULT_LOCATION,
    OPENWEATHER_USE_CELSIUS,
)


@dataclass
class WeatherReportSnapshot:
    location_name: str
    summary: str
    temperature: int
    high_temperature: int | None
    low_temperature: int | None
    condition: str | None
    use_celsius: bool


@dataclass
class _LocationPoint:
    latitude: float
    longitude: float
    display_name: str | None


class OpenWeatherProvider:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = OPENWEATHER_BASE_URL,
        default_location: str = OPENWEATHER_DEFAULT_LOCATION,
        use_celsius: bool = OPENWEATHER_USE_CELSIUS,
    ) -> None:
        self.api_key = api_key or OPENWEATHER_API_KEY
        self.base_url = base_url.rstrip("/")
        self.default_location = default_location
        self.default_use_celsius = use_celsius

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def get_report(
        self,
        location_query: str | None = None,
        forecast_day_offset: int = 0,
        use_celsius: bool | None = None,
    ) -> WeatherReportSnapshot | None:
        if not self.is_configured:
            return None

        use_metric = self.default_use_celsius if use_celsius is None else use_celsius
        location = await self._resolve_location(location_query)
        if location is None:
            return None

        if forecast_day_offset <= 0:
            return await self._get_current_weather(location, use_metric)
        return await self._get_forecast_for_day(location, use_metric, forecast_day_offset)

    async def _resolve_location(self, location_query: str | None) -> _LocationPoint | None:
        query = (location_query or self.default_location).strip()
        if not query:
            return None

        payload = await self._get_json(
            "/geo/1.0/direct",
            {"q": query, "limit": "1", "appid": self.api_key},
        )
        if not isinstance(payload, list) or not payload:
            return None

        entry = payload[0]
        latitude = entry.get("lat")
        longitude = entry.get("lon")
        if latitude is None or longitude is None:
            return None

        name = entry.get("name")
        state = entry.get("state")
        country = entry.get("country")
        if name and state and country:
            display_name = f"{name}, {state}, {country}"
        elif name and country:
            display_name = f"{name}, {country}"
        else:
            display_name = name

        return _LocationPoint(float(latitude), float(longitude), display_name)

    async def _get_current_weather(
        self,
        location: _LocationPoint,
        use_celsius: bool,
    ) -> WeatherReportSnapshot | None:
        payload = await self._get_json(
            "/data/2.5/weather",
            {
                "lat": str(location.latitude),
                "lon": str(location.longitude),
                "units": "metric" if use_celsius else "imperial",
                "appid": self.api_key,
            },
        )
        if not isinstance(payload, dict):
            return None

        main = payload.get("main", {})
        temperature = _read_int(main.get("temp"))
        high = _read_int(main.get("temp_max"))
        low = _read_int(main.get("temp_min"))
        if temperature is None and high is None and low is None:
            return None

        forecast_high_low = await self._get_today_high_low_from_forecast(location, use_celsius)
        if forecast_high_low:
            high = forecast_high_low[0] if forecast_high_low[0] is not None else high
            low = forecast_high_low[1] if forecast_high_low[1] is not None else low

        location_name = payload.get("name") or location.display_name or self.default_location
        summary = _read_weather_summary(payload) or "partly cloudy"
        condition = _read_weather_condition(payload)
        resolved_temperature = temperature if temperature is not None else (high or low or 0)

        return WeatherReportSnapshot(
            location_name=location_name,
            summary=summary,
            temperature=resolved_temperature,
            high_temperature=high,
            low_temperature=low,
            condition=condition,
            use_celsius=use_celsius,
        )

    async def _get_forecast_for_day(
        self,
        location: _LocationPoint,
        use_celsius: bool,
        forecast_day_offset: int,
    ) -> WeatherReportSnapshot | None:
        if forecast_day_offset > 5:
            return None

        payload = await self._get_json(
            "/data/2.5/forecast",
            {
                "lat": str(location.latitude),
                "lon": str(location.longitude),
                "units": "metric" if use_celsius else "imperial",
                "appid": self.api_key,
            },
        )
        if not isinstance(payload, dict):
            return None

        entries = payload.get("list", [])
        if not isinstance(entries, list):
            return None

        offset_seconds = 0
        city = payload.get("city", {})
        if isinstance(city, dict) and city.get("timezone") is not None:
            offset_seconds = int(city["timezone"])

        target_date = datetime.now(timezone.utc).astimezone(timezone(timedelta(seconds=offset_seconds))).date()
        target_date += timedelta(days=forecast_day_offset)

        matched: list[dict[str, Any]] = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            timestamp = item.get("dt")
            if timestamp is None:
                continue
            local_time = datetime.fromtimestamp(int(timestamp), timezone.utc).astimezone(
                timezone(timedelta(seconds=offset_seconds))
            )
            if local_time.date() != target_date:
                continue
            matched.append(item)

        if not matched:
            return None

        selected = min(
            matched,
            key=lambda item: abs(
                (
                    datetime.fromtimestamp(int(item["dt"]), timezone.utc).astimezone(
                        timezone(timedelta(seconds=offset_seconds))
                    ).time().hour
                    - 12
                )
            ),
        )
        main = selected.get("main", {})
        highs = [_read_int(entry.get("main", {}).get("temp_max")) for entry in matched]
        lows = [_read_int(entry.get("main", {}).get("temp_min")) for entry in matched]
        highs = [value for value in highs if value is not None]
        lows = [value for value in lows if value is not None]

        temperature = _read_int(main.get("temp"))
        high = max(highs) if highs else _read_int(main.get("temp_max"))
        low = min(lows) if lows else _read_int(main.get("temp_min"))
        if temperature is None and high is None and low is None:
            return None

        location_name = None
        if isinstance(city, dict):
            city_name = city.get("name")
            country = city.get("country")
            if city_name and country:
                location_name = f"{city_name}, {country}"
            else:
                location_name = city_name

        return WeatherReportSnapshot(
            location_name=location_name or location.display_name or self.default_location,
            summary=_read_weather_summary(selected) or "partly cloudy",
            temperature=temperature if temperature is not None else (high or low or 0),
            high_temperature=high,
            low_temperature=low,
            condition=_read_weather_condition(selected),
            use_celsius=use_celsius,
        )

    async def _get_today_high_low_from_forecast(
        self,
        location: _LocationPoint,
        use_celsius: bool,
    ) -> tuple[int | None, int | None] | None:
        payload = await self._get_json(
            "/data/2.5/forecast",
            {
                "lat": str(location.latitude),
                "lon": str(location.longitude),
                "units": "metric" if use_celsius else "imperial",
                "appid": self.api_key,
            },
        )
        if not isinstance(payload, dict):
            return None

        entries = payload.get("list", [])
        if not isinstance(entries, list):
            return None

        offset_seconds = 0
        city = payload.get("city", {})
        if isinstance(city, dict) and city.get("timezone") is not None:
            offset_seconds = int(city["timezone"])

        target_date = datetime.now(timezone.utc).astimezone(timezone(timedelta(seconds=offset_seconds))).date()
        highs: list[int] = []
        lows: list[int] = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            timestamp = item.get("dt")
            main = item.get("main", {})
            if timestamp is None or not isinstance(main, dict):
                continue
            local_time = datetime.fromtimestamp(int(timestamp), timezone.utc).astimezone(
                timezone(timedelta(seconds=offset_seconds))
            )
            if local_time.date() != target_date:
                continue
            high = _read_int(main.get("temp_max"))
            low = _read_int(main.get("temp_min"))
            if high is not None:
                highs.append(high)
            if low is not None:
                lows.append(low)

        if not highs and not lows:
            return None
        return (max(highs) if highs else None, min(lows) if lows else None)

    async def _get_json(self, path: str, query: dict[str, str]) -> Any:
        url = f"{self.base_url}{path}?{urlencode(query)}"
        timeout = aiohttp.ClientTimeout(total=6)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return None
                return await response.json()


def _read_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _read_weather_summary(payload: dict[str, Any]) -> str | None:
    weather = payload.get("weather")
    if not isinstance(weather, list) or not weather:
        return None
    first = weather[0]
    if not isinstance(first, dict):
        return None
    description = first.get("description")
    return str(description).strip() if description else None


def _read_weather_condition(payload: dict[str, Any]) -> str | None:
    weather = payload.get("weather")
    if not isinstance(weather, list) or not weather:
        return None
    first = weather[0]
    if not isinstance(first, dict):
        return None
    main = first.get("main")
    if not main:
        return None
    normalized = str(main).strip().lower()
    mapping = {
        "rain": "rain",
        "drizzle": "rain",
        "thunderstorm": "rain",
        "snow": "snow",
        "clear": "sunny",
        "clouds": "cloudy",
        "mist": "fog",
        "smoke": "fog",
        "haze": "fog",
        "fog": "fog",
    }
    return mapping.get(normalized, normalized)
