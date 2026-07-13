import random
import re
from dataclasses import dataclass
from enum import Enum, auto

from jibo.normalize import normalize_transcript

_QUESTION_PREFIXES = (
    "what's",
    "whats",
    "what is",
    "what s",
    "calculate",
    "compute",
)

_SPOKEN_ONES = (
    "a",
    "an",
    "zero",
    "oh",
    "one",
    "won",
    "two",
    "three",
    "four",
    "for",
    "five",
    "six",
    "seven",
    "eight",
    "ate",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
)
_SPOKEN_TENS = ("twenty", "thirty", "forty", "fifty")
_NUMBER = rf"(?:\d+(?:\.\d+)?|{'|'.join(_SPOKEN_ONES)}|{'|'.join(_SPOKEN_TENS)}|(?:{'|'.join(_SPOKEN_TENS)})[\s-]+(?:one|two|three|four|five|six|seven|eight|nine))"

_SQRT = re.compile(rf"^(?:the\s+)?square\s+root\s+of\s+(?P<num>{_NUMBER})\s*$", re.I)
_POWER = re.compile(rf"^(?P<left>{_NUMBER})\s+to\s+the\s+power\s+of\s+(?P<right>{_NUMBER})\s*$", re.I)
_SQUARED = re.compile(rf"^(?P<num>{_NUMBER})\s+squared\s*$", re.I)
_CUBED = re.compile(rf"^(?P<num>{_NUMBER})\s+cubed\s*$", re.I)
_BINARY = re.compile(
    rf"^(?P<left>{_NUMBER})\s+(?P<op>plus|add|added\s+to|\+|minus|subtract|subtracted\s+by|-|\*|x|times|multiplied\s+by|divided\s+by|over|/)\s+(?P<right>{_NUMBER})\s*$",
    re.I,
)


class MathOperation(Enum):
    ADD = auto()
    SUBTRACT = auto()
    MULTIPLY = auto()
    DIVIDE = auto()
    SQRT = auto()
    POWER = auto()


@dataclass
class MathQuery:
    operation: MathOperation
    left: float
    right: float | None
    left_spoken: str
    right_spoken: str | None
    operator_spoken: str


@dataclass
class MathResult:
    success: bool
    value: float = 0.0
    error: str | None = None


def _expand_symbols(value: str) -> str:
    return (
        value.replace("÷", " divided by ")
        .replace("×", " times ")
        .replace("+", " plus ")
        .replace("*", " times ")
        .replace("/", " divided by ")
        .replace(" - ", " minus ")
        .replace(" x ", " times ")
    )


def _strip_question_prefix(text: str) -> str:
    for prefix in _QUESTION_PREFIXES:
        if text == prefix:
            return ""
        if text.startswith(f"{prefix} "):
            return text[len(prefix) + 1 :].strip()
    return text


def _spoken_to_int(token: str) -> int | None:
    token = token.strip().lower().replace("-", " ")
    if token.isdigit():
        return int(token)

    mapping = {
        "a": 1,
        "an": 1,
        "zero": 0,
        "oh": 0,
        "one": 1,
        "won": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "for": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "ate": 8,
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
    }
    if " " not in token:
        return mapping.get(token)

    parts = token.split()
    if len(parts) != 2:
        return None
    first = mapping.get(parts[0])
    second = mapping.get(parts[1])
    if first is not None and first >= 20 and second is not None and second < 10:
        return first + second
    return None


def _parse_number(token: str) -> float | None:
    token = token.strip().lower().replace("-", " ")
    try:
        return float(token)
    except ValueError:
        spoken = _spoken_to_int(token)
        return float(spoken) if spoken is not None else None


def _nums_from_match(match: re.Match) -> tuple[str, str | None]:
  groups = [g for g in match.groups() if g is not None]
  if len(groups) == 1:
      return groups[0], None
  return groups[0], groups[1]


def try_parse_math(transcript: str) -> MathQuery | None:
    normalized = _strip_question_prefix(normalize_transcript(_expand_symbols(transcript)))
    if not normalized:
        return None

    tokens = normalized.split()
    homophones = {"for": "four", "won": "one", "ate": "eight", "oh": "zero"}
    normalized = " ".join(homophones.get(t, t) for t in tokens)

    match = _SQRT.match(normalized)
    if match:
        spoken = match.group("num").strip()
        value = _parse_number(spoken)
        if value is not None:
            return MathQuery(MathOperation.SQRT, value, None, spoken, None, "square root of")

    match = _POWER.match(normalized)
    if match:
        left_spoken = match.group("left").strip()
        right_spoken = match.group("right").strip()
        left = _parse_number(left_spoken)
        right = _parse_number(right_spoken)
        if left is not None and right is not None:
            return MathQuery(MathOperation.POWER, left, right, left_spoken, right_spoken, "to the power of")

    match = _SQUARED.match(normalized)
    if match:
        spoken = match.group("num").strip()
        value = _parse_number(spoken)
        if value is not None:
            return MathQuery(MathOperation.POWER, value, 2, spoken, "2", "squared")

    match = _CUBED.match(normalized)
    if match:
        spoken = match.group("num").strip()
        value = _parse_number(spoken)
        if value is not None:
            return MathQuery(MathOperation.POWER, value, 3, spoken, "3", "cubed")

    match = _BINARY.match(normalized)
    if match:
        left_spoken = match.group("left").strip()
        right_spoken = match.group("right").strip()
        left = _parse_number(left_spoken)
        right = _parse_number(right_spoken)
        if left is None or right is None:
            return None
        op_token = match.group("op").lower()
        mapping = {
            "plus": (MathOperation.ADD, "plus"),
            "add": (MathOperation.ADD, "plus"),
            "added to": (MathOperation.ADD, "plus"),
            "+": (MathOperation.ADD, "plus"),
            "minus": (MathOperation.SUBTRACT, "minus"),
            "subtract": (MathOperation.SUBTRACT, "minus"),
            "subtracted by": (MathOperation.SUBTRACT, "minus"),
            "-": (MathOperation.SUBTRACT, "minus"),
            "*": (MathOperation.MULTIPLY, "times"),
            "x": (MathOperation.MULTIPLY, "times"),
            "times": (MathOperation.MULTIPLY, "times"),
            "multiplied by": (MathOperation.MULTIPLY, "times"),
            "divided by": (MathOperation.DIVIDE, "divided by"),
            "over": (MathOperation.DIVIDE, "divided by"),
            "/": (MathOperation.DIVIDE, "divided by"),
        }
        operation, operator_spoken = mapping.get(op_token, (None, ""))
        if operation is None:
            return None
        return MathQuery(operation, left, right, left_spoken, right_spoken, operator_spoken)

    return None


def evaluate_math(query: MathQuery) -> MathResult:
    if query.operation == MathOperation.ADD:
        return MathResult(True, query.left + query.right)
    if query.operation == MathOperation.SUBTRACT:
        return MathResult(True, query.left - query.right)
    if query.operation == MathOperation.MULTIPLY:
        return MathResult(True, query.left * query.right)
    if query.operation == MathOperation.DIVIDE:
        if query.right == 0:
            return MathResult(False, error="I can't divide by zero.")
        return MathResult(True, query.left / query.right)
    if query.operation == MathOperation.SQRT:
        if query.left < 0:
            return MathResult(False, error="I can't take the square root of a negative number.")
        return MathResult(True, query.left**0.5)
    if query.operation == MathOperation.POWER:
        return MathResult(True, query.left**query.right)
    return MathResult(False, error="I couldn't figure that one out.")


def format_math_answer(value: float) -> str:
    if abs(value - round(value)) < 0.0000001:
        return str(int(round(value)))
    return f"{value:.10g}"


def format_math_reply(query: MathQuery, result: MathResult) -> str:
    if not result.success:
        return result.error or "I couldn't figure that one out."

    connector = random.choice(["equals", "is", "comes to", "is equal to"])
    answer = format_math_answer(result.value)

    if query.operation == MathOperation.SQRT:
        reply = f"the square root of {query.left_spoken} {connector} {answer}"
    elif query.operation == MathOperation.POWER and query.operator_spoken == "squared":
        reply = f"{query.left_spoken} squared {connector} {answer}"
    elif query.operation == MathOperation.POWER and query.operator_spoken == "cubed":
        reply = f"{query.left_spoken} cubed {connector} {answer}"
    elif query.operation == MathOperation.POWER:
        reply = f"{query.left_spoken} to the power of {query.right_spoken} {connector} {answer}"
    else:
        reply = f"{query.left_spoken} {query.operator_spoken} {query.right_spoken} {connector} {answer}"

    if query.operation == MathOperation.ADD and (
        (abs(query.left - 9) < 0.001 and abs(query.right - 10) < 0.001)
        or (abs(query.left - 10) < 0.001 and abs(query.right - 9) < 0.001)
    ):
        reply += ", but some might say it's 21"

    return reply
