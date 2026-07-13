import random
import re
from dataclasses import dataclass

from jibo.normalize import normalize_transcript

MIN_SIDES = 2
MAX_SIDES = 100
DEFAULT_SIDES = 6

_DEFAULT = re.compile(r"^roll (?:a |the )?(?:dice|die)$", re.I)
_SIDED = re.compile(
    r"^roll (?:a |the )?(?P<sides>\d+|[a-z\-]+(?:\s+[a-z\-]+)?)[\s-]?sided (?:dice|die)$",
    re.I,
)
_D_NOTATION = re.compile(
    r"^roll (?:a |the )?d(?P<sides>\d+|[a-z\-]+(?:\s+[a-z\-]+)?)$",
    re.I,
)


@dataclass
class DiceQuery:
    sides: int


def _spoken_to_int(token: str) -> int | None:
    token = token.strip().lower()
    if token.isdigit():
        return int(token)

    mapping = {
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19,
        "twenty": 20,
        "thirty": 30,
        "forty": 40,
        "fifty": 50,
        "sixty": 60,
        "seventy": 70,
        "eighty": 80,
        "ninety": 90,
        "hundred": 100,
        "one hundred": 100,
    }
    if " " not in token:
        return mapping.get(token)

    parts = token.split()
    if len(parts) == 2 and parts[0] == "one" and parts[1] == "hundred":
        return 100
    if len(parts) != 2:
        return None
    first = mapping.get(parts[0])
    second = mapping.get(parts[1])
    if first is not None and first >= 20 and second is not None and second < 10:
        return first + second
    return None


def _parse_sides(token: str) -> int | None:
    spoken = _spoken_to_int(token)
    if spoken is None:
        return None
    if MIN_SIDES <= spoken <= MAX_SIDES:
        return spoken
    return None


def try_parse_dice(transcript: str) -> DiceQuery | None:
    normalized = normalize_transcript(transcript)
    if not normalized:
        return None

    if _DEFAULT.match(normalized):
        return DiceQuery(DEFAULT_SIDES)

    for pattern in (_SIDED, _D_NOTATION):
        match = pattern.match(normalized)
        if match:
            sides = _parse_sides(match.group("sides"))
            if sides is not None:
                return DiceQuery(sides)
    return None


def roll_dice(sides: int) -> int:
    return random.randint(1, sides)


def format_dice_reply(sides: int, result: int) -> str:
    if sides == 20 and result == 1:
        return "It landed on a 1. Critical failure!"
    return f"It landed on {result}."


INVALID_SIDES_REPLY = (
    "I can roll dice with 2 to 100 sides. Try asking me to roll a dice or roll a 20 sided die."
)
