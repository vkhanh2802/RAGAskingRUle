import re
import unicodedata

_HORIZONTAL_WHITESPACE = re.compile(r"[^\S\r\n]+")
_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text_block(text: str) -> str:
    """Normalize extraction noise without changing document wording or numbers."""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("\u00ad", "").replace("\u200b", "")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = _CONTROL_CHARACTERS.sub("", normalized)

    lines = [_HORIZONTAL_WHITESPACE.sub(" ", line).strip() for line in normalized.split("\n")]
    cleaned = "\n".join(lines).strip()
    return _EXCESS_BLANK_LINES.sub("\n\n", cleaned)
