"""Load OpenJibo API settings from appsettings.json with environment overrides."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

OPENJIBO_APPSETTINGS_PATH: Path | None = None
_openjibo_config_cache: dict[str, Any] | None = None


def configure_appsettings_path(path: Path) -> None:
    global OPENJIBO_APPSETTINGS_PATH, _openjibo_config_cache
    OPENJIBO_APPSETTINGS_PATH = path
    _openjibo_config_cache = None


def load_openjibo_config() -> dict[str, Any]:
    global _openjibo_config_cache
    if _openjibo_config_cache is not None:
        return _openjibo_config_cache

    if OPENJIBO_APPSETTINGS_PATH is None or not OPENJIBO_APPSETTINGS_PATH.is_file():
        _openjibo_config_cache = {}
        return _openjibo_config_cache

    try:
        payload = json.loads(OPENJIBO_APPSETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _openjibo_config_cache = {}
        return _openjibo_config_cache

    section = payload.get("OpenJibo", {})
    _openjibo_config_cache = section if isinstance(section, dict) else {}
    return _openjibo_config_cache


def get_openjibo_section(*keys: str) -> dict[str, Any]:
    node: Any = load_openjibo_config()
    for key in keys:
        if not isinstance(node, dict):
            return {}
        node = node.get(key, {})
    return node if isinstance(node, dict) else {}


def _coerce_setting(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value).strip()
    return text or None


def resolve_setting(
    env_name: str,
    section_keys: tuple[str, ...],
    json_key: str,
    default: str | None = None,
    *,
    extra_env_names: tuple[str, ...] = (),
) -> str | None:
    for name in (env_name, *extra_env_names):
        env_value = os.environ.get(name)
        if env_value:
            return env_value

    openjibo_value = get_openjibo_section(*section_keys).get(json_key)
    coerced = _coerce_setting(openjibo_value)
    if coerced is not None:
        return coerced
    return default


def resolve_bool_setting(
    env_name: str,
    section_keys: tuple[str, ...],
    json_key: str,
    default: bool = False,
) -> bool:
    raw = resolve_setting(env_name, section_keys, json_key, "true" if default else "false")
    return (raw or "false").lower() in ("1", "true", "yes")


def resolve_int_setting(
    env_name: str,
    section_keys: tuple[str, ...],
    json_key: str,
    default: int,
) -> int:
    raw = resolve_setting(env_name, section_keys, json_key, str(default))
    try:
        return int(raw or default)
    except ValueError:
        return default


def resolve_list_setting(
    section_keys: tuple[str, ...],
    json_key: str,
    default: tuple[str, ...] = (),
) -> list[str]:
    value = get_openjibo_section(*section_keys).get(json_key)
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return list(default)
