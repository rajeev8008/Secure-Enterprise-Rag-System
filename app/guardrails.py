import re

INJECTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bignore\s+(all\s+)?(previous|prior)\s+instructions?\b",
        r"\b(reveal|show|print)\s+(the\s+)?(system|developer)\s+prompt\b",
        r"\b(jailbreak|bypass\s+(security|permissions?|access controls?))\b",
        r"\bact\s+as\s+(the\s+)?(system|developer)\b",
    )
)

PII_PATTERNS = (
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE), "[REDACTED EMAIL]"),
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED SSN]"),
    (re.compile(r"(?<!\d)(?:\+?\d[\d .()-]{7,}\d)(?!\d)"), "[REDACTED PHONE]"),
)


def prompt_injection_reason(text: str) -> str | None:
    return "prompt_injection" if any(pattern.search(text) for pattern in INJECTION_PATTERNS) else None


def redact_pii(text: str) -> str:
    for pattern, replacement in PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text
