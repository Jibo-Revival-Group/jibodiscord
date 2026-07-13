import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from jibo.config import LEGACY_MIMS_DIRS, OPENJIBO_PATH
from jibo.seed_catalog import SEED_CATALOG

_LEGACY_MARKUP = re.compile(r"<[^>]+>")
_PLACEHOLDER = re.compile(r"\$\{[^}]+\}")
_WHITESPACE = re.compile(r"\s+")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.;:!?])")


@dataclass
class Catalog:
    jokes: list[str] = field(default_factory=list)
    fun_fact_fallbacks: list[str] = field(default_factory=list)
    favorite_animal_replies: list[str] = field(default_factory=list)
    friend_replies: list[str] = field(default_factory=list)
    best_friend_replies: list[str] = field(default_factory=list)
    sing_replies: list[str] = field(default_factory=list)
    holiday_sing_replies: list[str] = field(default_factory=list)
    dance_animations: list[str] = field(default_factory=list)
    dance_replies: list[str] = field(default_factory=list)
    dance_question_replies: list[str] = field(default_factory=list)
    greeting_replies: list[str] = field(default_factory=list)
    story_replies: list[str] = field(default_factory=list)
    how_are_you_replies: list[str] = field(default_factory=list)
    age_replies: list[str] = field(default_factory=list)
    personality_replies: list[str] = field(default_factory=list)
    pizza_replies: list[str] = field(default_factory=list)
    surprise_replies: list[str] = field(default_factory=list)
    recommend_movie_replies: list[str] = field(default_factory=list)
    search_web_replies: list[str] = field(default_factory=list)
    can_walk_replies: list[str] = field(default_factory=list)
    can_walk_dog_replies: list[str] = field(default_factory=list)
    can_watch_movies_replies: list[str] = field(default_factory=list)
    can_watch_tv_replies: list[str] = field(default_factory=list)
    can_dream_replies: list[str] = field(default_factory=list)
    can_exercise_replies: list[str] = field(default_factory=list)
    can_fly_replies: list[str] = field(default_factory=list)
    can_learn_replies: list[str] = field(default_factory=list)
    can_laugh_replies: list[str] = field(default_factory=list)
    can_read_replies: list[str] = field(default_factory=list)
    can_hear_replies: list[str] = field(default_factory=list)
    can_talk_replies: list[str] = field(default_factory=list)
    can_see_replies: list[str] = field(default_factory=list)
    can_wink_replies: list[str] = field(default_factory=list)
    can_move_replies: list[str] = field(default_factory=list)
    can_work_replies: list[str] = field(default_factory=list)
    can_breathe_replies: list[str] = field(default_factory=list)
    can_get_tired_replies: list[str] = field(default_factory=list)
    can_have_emotions_replies: list[str] = field(default_factory=list)
    can_whistle_replies: list[str] = field(default_factory=list)
    can_cook_replies: list[str] = field(default_factory=list)
    can_make_coffee_replies: list[str] = field(default_factory=list)
    can_make_breakfast_replies: list[str] = field(default_factory=list)
    can_jump_replies: list[str] = field(default_factory=list)
    generic_fallback_replies: list[str] = field(default_factory=list)
    weather_replies: list[str] = field(default_factory=list)
    weather_intro_replies: list[str] = field(default_factory=list)
    weather_tomorrow_intro_replies: list[str] = field(default_factory=list)
    weather_today_high_low_replies: list[str] = field(default_factory=list)
    weather_tomorrow_high_low_replies: list[str] = field(default_factory=list)
    weather_service_down_replies: list[str] = field(default_factory=list)
    news_replies: list[str] = field(default_factory=list)
    news_outro_replies: list[str] = field(default_factory=list)
    news_briefings: list[str] = field(default_factory=list)

    def get_list(self, key: str) -> list[str]:
        return getattr(self, key, [])

    def add_unique(self, key: str, text: str) -> None:
        items = self.get_list(key)
        if text and text.lower() not in {item.lower() for item in items}:
            items.append(text)


def _normalize_prompt(prompt: str, is_template: bool = False) -> str:
    text = _LEGACY_MARKUP.sub(" ", prompt)
    if not is_template:
        text = _PLACEHOLDER.sub(" ", text)
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", text)
    return _WHITESPACE.sub(" ", text).strip()


def _resolve_bucket(file_path: Path) -> str | None:
    normalized = str(file_path).replace("\\", "/")
    name = file_path.stem

    if "/core-responses/" in normalized and "error" in name.lower():
        return "generic_fallback_replies"
    if "/core-responses/deflector/" in normalized or "deflector" in name.lower():
        return "personality_replies"
    if name.startswith("RA_JBO_TellAJoke"):
        return "jokes"
    if name.startswith("RA_JBO_SingChristmasSongUnknown"):
        return "holiday_sing_replies"
    if name.startswith("RA_JBO_Sing"):
        return "sing_replies"
    if name.startswith("RA_JBO_Story"):
        return "story_replies"
    if name.startswith("RA_JBO_RecommendMovie"):
        return "recommend_movie_replies"
    if name.startswith("RA_JBO_SearchWeb"):
        return "search_web_replies"
    if name.startswith("NewsOutro"):
        return "news_outro_replies"
    if "/emotion-responses/" in normalized or "/gqa-responses/" in normalized:
        return "personality_replies"
    if name.startswith("RI_JBO_HasFavoriteAnimal") or name.startswith("RI_JBO_LikesPenguins"):
        return "favorite_animal_replies"
    if name.startswith("RI_JBO_HasFriends") or name.startswith("RI_JBO_IsFriendsWith"):
        return "friend_replies"
    if name.startswith("RI_JBO_IsBestFriendsWithUser"):
        return "best_friend_replies"
    if "/scripted-responses/" in normalized:
        return "personality_replies"
    return None


def _load_mim_file(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    prompts = data.get("prompts", [])
    texts: list[str] = []
    bucket = _resolve_bucket(path)
    is_template = bucket == "age_replies"
    for entry in prompts:
        prompt = entry.get("prompt", "")
        text = _normalize_prompt(prompt, is_template=is_template)
        if text:
            texts.append(text)
    return texts


def _merge_seed(catalog: Catalog) -> None:
    for key, values in SEED_CATALOG.items():
        for value in values:
            catalog.add_unique(key, value)


def _merge_mims(catalog: Catalog, root: Path) -> int:
    count = 0
    if not root.is_dir():
        return count

    for mim_path in sorted(root.rglob("*.mim")):
        bucket = _resolve_bucket(mim_path)
        if not bucket:
            continue
        for text in _load_mim_file(mim_path):
            catalog.add_unique(bucket, text)
            count += 1
    return count


def load_catalog(openjibo_path: Path | None = None) -> tuple[Catalog, int]:
    catalog = Catalog()
    _merge_seed(catalog)

    base = openjibo_path or OPENJIBO_PATH
    mim_count = 0
    for relative in LEGACY_MIMS_DIRS:
        mim_count += _merge_mims(catalog, base / relative)

    return catalog, mim_count
