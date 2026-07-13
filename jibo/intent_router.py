"""Semantic intent routing ported from OpenJibo JiboInteractionService.IntentRouting."""

from __future__ import annotations

import re
from collections.abc import Callable

from jibo.normalize import matches_any, normalize_transcript
from jibo.parsers.define import is_define_request
from jibo.parsers.dice import try_parse_dice
from jibo.parsers.math import try_parse_math
from jibo.weather.parser import is_weather_request

IntentMatcher = Callable[[str, str], str | None]


def _phrase_intent(phrases: tuple[str, ...], intent: str) -> IntentMatcher:
    def matcher(_raw: str, lowered: str) -> str | None:
        if matches_any(lowered, *phrases):
            return intent
        return None

    return matcher


def _regex_intent(pattern: str, intent: str) -> IntentMatcher:
    compiled = re.compile(pattern, re.I)

    def matcher(_raw: str, lowered: str) -> str | None:
        if compiled.search(lowered):
            return intent
        return None

    return matcher


def _define_word_intent(raw: str, lowered: str) -> str | None:
    if is_define_request(raw):
        return "define_word"
    return None


def _is_time_request(_raw: str, lowered: str) -> str | None:
    normalized = normalize_transcript(lowered)
    if not normalized:
        return None
    if normalized in ("time", "the time", "current time", "what time is it", "what s the time", "what is the time"):
        return "time"
    if normalized.startswith(("what time", "tell me the time", "show me the time")):
        return "time"
    return None


def _is_date_request(_raw: str, lowered: str) -> str | None:
    normalized = normalize_transcript(lowered)
    if normalized in (
        "what is the date",
        "what s the date",
        "what's the date",
        "what date is it",
        "today s date",
        "today date",
        "what's today's date",
        "what is today s date",
        "what s today s date",
        "what's today s date",
        "what's todays date",
        "what is todays date",
        "what s todays date",
    ):
        return "date"
    return None


def _is_dance_command(_raw: str, lowered: str) -> str | None:
    normalized = normalize_transcript(lowered)
    if normalized in (
        "dance",
        "boogie",
        "do a dance",
        "do your dance",
        "show me a dance",
        "show us a dance",
        "show me your dance",
        "show us your dance",
        "dance for me",
        "dance for us",
        "dance with me",
        "dance with us",
        "bust a move",
        "bust some moves",
        "do some dancing",
        "start dancing",
        "lets dance",
        "let s dance",
    ) or normalized.startswith(("dance ", "boogie ")):
        return "dance"
    return None


def _is_dance_question(_raw: str, lowered: str) -> str | None:
    if matches_any(
        lowered,
        "do you like to dance",
        "do you like dancing",
        "do you enjoy dancing",
        "do you enjoy dance",
        "are you into dancing",
    ):
        return "dance_question"
    return None


def _countdown_intent(_raw: str, lowered: str) -> str | None:
    if lowered.startswith("how many days until "):
        return "countdown"
    if lowered.startswith("days until "):
        return "countdown"
    return None


def _radio_intent(_raw: str, lowered: str) -> str | None:
    if "play pop music" in lowered or "play some pop music" in lowered:
        return "radio_genre_pop"
    if "play rock music" in lowered or "play some rock music" in lowered:
        return "radio_genre_rock"
    if "play jazz music" in lowered or "play some jazz music" in lowered:
        return "radio_genre_jazz"
    if "play music" in lowered or lowered == "music":
        return "radio"
    return None


def _weather_intent(raw: str, lowered: str) -> str | None:
    if is_weather_request(raw):
        return "weather"
    return None


def _math_intent(_raw: str, lowered: str) -> str | None:
    if try_parse_math(lowered):
        return "math_query"
    return None


def _dice_intent(_raw: str, lowered: str) -> str | None:
    if try_parse_dice(lowered):
        return "roll_dice"
    return None


def _greeting_intent(_raw: str, lowered: str) -> str | None:
    if matches_any(lowered, "good morning", "morning jibo"):
        return "good_morning"
    if matches_any(lowered, "good afternoon"):
        return "good_afternoon"
    if matches_any(lowered, "good evening"):
        return "good_evening"
    if matches_any(lowered, "good night", "goodnight"):
        return "good_night"
    if matches_any(
        lowered,
        "welcome back",
        "i'm home",
        "im home",
        "i am home",
        "i'm back",
        "im back",
        "i am back",
    ):
        return "welcome_back"
    if matches_any(
        lowered,
        "how are you",
        "what's up",
        "what s up",
        "what up",
        "how is it going",
        "how's it going",
        "how are things",
        "how's things",
        "how is things",
        "how are you feeling",
        "how is your mood",
        "how is your day",
        "how's your day",
        "how's life",
        "how is life",
        "how's everything",
        "how is everything",
    ):
        return "how_are_you"
    if matches_any(lowered, "hello", "hi", "hey"):
        return "hello"
    return None


# Order matters — mirrors OpenJibo priority (specialized before generic).
INTENT_MATCHERS: list[IntentMatcher] = [
    _math_intent,
    _dice_intent,
    _phrase_intent(
        (
            "what does jibo mean",
            "what does the name jibo mean",
            "what is the meaning of jibo",
        ),
        "robot_what_does_jibo_mean",
    ),
    _phrase_intent(("are you funny", "do you think you are funny", "are you a funny robot"), "robot_is_funny"),
    _phrase_intent(
        (
            "what is your favorite joke",
            "what's your favorite joke",
            "what s your favorite joke",
            "do you have a favorite joke",
            "what joke do you like best",
        ),
        "robot_favorite_joke",
    ),
    _phrase_intent(
        ("fun fact", "tell me a fun fact", "give me a fun fact", "share a fun fact", "random fact", "useless fact"),
        "fun_fact",
    ),
    _phrase_intent(("joke", "funny", "make me laugh", "tell me a joke"), "joke"),
    _countdown_intent,
    _phrase_intent(
        (
            "how old are you",
            "what is your age",
            "what s your age",
            "how old r you",
        ),
        "robot_how_old_are_you",
    ),
    _phrase_intent(
        (
            "do you have a personality",
            "what is your personality",
            "what's your personality",
            "what s your personality",
            "describe your personality",
        ),
        "robot_personality",
    ),
    _phrase_intent(
        (
            "when is your birthday",
            "when's your birthday",
            "what is your birthday",
            "what's your birthday",
            "what s your birthday",
            "what's your bday",
            "when's your bday",
        ),
        "robot_birthday",
    ),
    _phrase_intent(
        (
            "what is your favorite color",
            "what's your favorite color",
            "what s your favorite color",
            "what is your favourite color",
            "what's your favourite color",
            "what s your favourite color",
            "do you have a favorite color",
            "do you have a favourite color",
            "what color do you like",
            "what colour do you like",
            "do you like blue",
            "do you like the color blue",
            "do you like the colour blue",
        ),
        "robot_favorite_color",
    ),
    _phrase_intent(
        (
            "what is your favorite food",
            "what's your favorite food",
            "what s your favorite food",
            "do you have a favorite food",
            "what food do you like",
        ),
        "robot_favorite_food",
    ),
    _phrase_intent(
        (
            "who am i",
            "what am i",
            "what are you",
            "who are you",
        ),
        "robot_identity",
    ),
    _phrase_intent(
        (
            "do you have friends",
            "are you my friend",
            "are we friends",
            "are you friends with me",
        ),
        "robot_has_friends",
    ),
    _phrase_intent(("are you my best friend", "are we best friends", "who is your best friend"), "robot_best_friends"),
    _phrase_intent(
        (
            "what is your favorite animal",
            "what's your favorite animal",
            "do you like penguins",
            "do you like animals",
        ),
        "robot_favorite_animal",
    ),
    _is_dance_question,
    _phrase_intent(("can you twerk", "twerk"), "twerk"),
    _is_dance_command,
    _phrase_intent(
        (
            "can you dream",
            "do you dream",
            "do you have dreams",
        ),
        "robot_can_dream",
    ),
    _phrase_intent(("can you fly", "do you fly"), "robot_can_fly"),
    _phrase_intent(("can you walk", "are you able to walk"), "robot_can_walk"),
    _phrase_intent(("can you read", "do you read"), "robot_can_read"),
    _phrase_intent(("can you hear", "do you hear me"), "robot_can_hear"),
    _phrase_intent(("can you talk", "do you talk"), "robot_can_talk"),
    _phrase_intent(("can you see", "do you see me"), "robot_can_see"),
    _phrase_intent(("can you sing", "will you sing", "sing a song", "sing me a song"), "robot_can_sing"),
    _phrase_intent(("can you dance", "do you know how to dance"), "robot_can_dance"),
    _phrase_intent(("tell me a story", "do you know any stories"), "robot_story"),
    _phrase_intent(("recommend a movie", "favorite movie", "what movie do you like"), "robot_recommend_movie"),
    _phrase_intent(("surprise", "surprise me", "tell me something fun"), "surprise"),
    _phrase_intent(("make pizza", "bake pizza", "can you make pizza"), "pizza"),
    _weather_intent,
    _define_word_intent,
    _phrase_intent(("news", "headlines", "tell me the news"), "news"),
    _radio_intent,
    _phrase_intent(("cloud version", "what version is the cloud", "openjibo cloud version"), "cloud_version"),
    _is_time_request,
    _phrase_intent(("what day is it", "what day is today"), "day"),
    _is_date_request,
    _greeting_intent,
]


def resolve_semantic_intent(transcript: str) -> str:
    lowered = normalize_transcript(transcript)
    if not lowered:
        return "chat"

    for matcher in INTENT_MATCHERS:
        intent = matcher(transcript, lowered)
        if intent:
            return intent

    return "chat"
