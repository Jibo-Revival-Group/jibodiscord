import re
import unicodedata

COMMAND_LEAD_PHRASES = (
    "hey jibo",
    "hello jibo",
    "hi jibo",
    "jibo",
    "o",
    "oh",
    "so",
    "well",
    "um",
    "uh",
    "hmm",
    "erm",
    "ah",
    "please",
    "ok jibo",
    "okay jibo",
)

# Glued contractions often produced by ASR or casual typing without apostrophes.
GLUED_CONTRACTIONS: dict[str, str] = {
    "whats": "what s",
    "wheres": "where s",
    "whens": "when s",
    "hows": "how s",
    "whos": "who s",
    "thats": "that s",
    "theres": "there s",
    "heres": "here s",
    "youre": "you re",
    "theyre": "they re",
    "weve": "we ve",
    "youve": "you ve",
    "ive": "i ve",
    "im": "i m",
    "dont": "don t",
    "doesnt": "doesn t",
    "didnt": "didn t",
    "wont": "won t",
    "cant": "can t",
    "isnt": "isn t",
    "arent": "aren t",
    "wasnt": "wasn t",
    "werent": "weren t",
    "couldnt": "couldn t",
    "wouldnt": "wouldn t",
    "shouldnt": "shouldn t",
    "lets": "let s",
    "its": "it s",
    "todays": "today s",
}

# British -> American spellings used throughout OpenJibo phrase lists.
SPELLING_ALIASES: dict[str, str] = {
    "favourite": "favorite",
    "favourites": "favorites",
    "colour": "color",
    "colours": "colors",
    "behaviour": "behavior",
    "humour": "humor",
    "honour": "honor",
    "neighbour": "neighbor",
    "neighbours": "neighbors",
    "metre": "meter",
    "metres": "meters",
    "centre": "center",
    "theatre": "theater",
}

_WHITESPACE = re.compile(r"\s+")
_PUNCTUATION = re.compile(r"[^\w\s']")


def normalize_loose_text(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", value).lower().strip()
    text = _PUNCTUATION.sub(" ", text)
    text = text.replace("'", " ")
    text = _WHITESPACE.sub(" ", text).strip()
    return _canonicalize_tokens(text)


def _canonicalize_tokens(text: str) -> str:
    if not text:
        return ""

    tokens: list[str] = []
    for token in text.split():
        token = GLUED_CONTRACTIONS.get(token, token)
        token = SPELLING_ALIASES.get(token, token)
        tokens.append(token)
    return " ".join(tokens)


def strip_leading_phrases(text: str, phrases: tuple[str, ...] = COMMAND_LEAD_PHRASES) -> str:
    normalized = text
    changed = True
    while changed:
        changed = False
        for phrase in phrases:
            if normalized == phrase:
                return ""
            prefix = f"{phrase} "
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix) :].strip()
                changed = True
    return normalized


def normalize_transcript(value: str | None) -> str:
    return strip_leading_phrases(normalize_loose_text(value))


def matches_any(text: str, *phrases: str) -> bool:
    for phrase in phrases:
        normalized_phrase = normalize_loose_text(phrase)
        if text == normalized_phrase or normalized_phrase in text:
            return True
    return False


def contains_any(text: str, *phrases: str) -> bool:
    return matches_any(text, *phrases)
