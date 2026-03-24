"""
PII and sensitive data redaction middleware.
Runs on all incoming ticket text before it reaches the LLM.
"""
import re

PII_PATTERNS = [
    (r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b", "[CARD_REDACTED]"),   # Credit card
    (r"\b\d{3}[- ]?\d{2}[- ]?\d{4}\b", "[SSN_REDACTED]"),               # SSN
    (r"\b[A-Z]\d{8}\b|\b\d{9}\b", "[SIN_REDACTED]"),                    # SIN (Canada)
    (r"(?i)password\s*[:=]\s*\S+", "[PASSWORD_REDACTED]"),               # Passwords
    (r"(?i)api[_\s-]?key\s*[:=]\s*\S+", "[APIKEY_REDACTED]"),           # API keys
    (r"(?i)secret\s*[:=]\s*\S+", "[SECRET_REDACTED]"),                  # Secrets
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL_REDACTED]"),  # Email
]


def redact_text(text: str) -> tuple[str, list[str]]:
    """
    Returns (redacted_text, list_of_redaction_labels).
    """
    redacted = text
    labels = []
    for pattern, replacement in PII_PATTERNS:
        new_text, n = re.subn(pattern, replacement, redacted)
        if n > 0:
            labels.append(replacement)
            redacted = new_text
    return redacted, labels
