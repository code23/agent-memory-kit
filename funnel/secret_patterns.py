"""Shared deterministic secret kinds for capture and the promotion funnel."""
import re

SECRET_PATTERNS = {
    "api_key": r"\bsk-[A-Za-z0-9]{8,}",
    "ipv4": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    "repo_url": r"(github|gitlab)\.com/",
    "env_export": r"export [A-Z_]{4,}",
    "port": r":\d{4,5}\b",
    "uk_bank_account": r"(?i)(?<![\w+])(?:sort[ -]?code\s*[:=]?\s*)?(?:\d{2}[- ]\d{2}[- ]\d{2}|\d{6})(?:\s*[,;/]\s*|\s+(?:and\s+)?)(?:account(?:\s+(?:number|no\.?))?\s*[:=]?\s*)?\d{8}(?!\w)(?![ -]?\d)",
    "card_number": r"(?<![\w+])(?<!\d[ -])\d(?:[ -]?\d){12,18}(?!\w)(?![ -]?\d)",
}


def policy_patterns(policy):
    """Reject positional legacy policies rather than silently mislabelling secrets."""
    patterns = policy.get("forbidden_patterns")
    if not isinstance(patterns, dict):
        raise ValueError("forbidden_patterns must be a mapping keyed by kind; upgrade policy.yaml from policy.example.yaml (remove email, money and phone patterns)")
    for kind, pattern in patterns.items():
        if not isinstance(kind, str) or not kind or not isinstance(pattern, str) or not pattern:
            raise ValueError("forbidden_patterns requires non-empty kind and regex strings")
        re.compile(pattern)  # invalid policies fail closed before extraction or judging
    return patterns
