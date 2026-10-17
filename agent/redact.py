import re

PATTERNS = [
    (re.compile(r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key)\b\s*[=:]\s*\S+"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]+"), "Bearer [REDACTED]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_AWS_KEY]"),
]

def redact(text: str) -> str:
    """Remove passwords, tokens and keys from text before the LLM or database sees it."""
    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)
    return text

if __name__ == "__main__":
    cases = [
        ("db connect failed password=hunter2 host=db", "hunter2", False),
        ("Authorization: Bearer abc123.def456", "abc123", False),
        ("key AKIAABCDEFGHIJKLMNOP leaked", "AKIAABCDEFGHIJKLMNOP", False),
        ("work completed in 0.004 seconds", "work completed", True),
    ]
    for text, probe, should_remain in cases:
        remains = probe in redact(text)
        print("OK  " if remains == should_remain else "FAIL", text)