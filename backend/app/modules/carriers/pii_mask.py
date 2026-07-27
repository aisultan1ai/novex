from __future__ import annotations

import re

# ── Structured data (dict / list) — used for integration_log payloads ─────

_PII_FIELDS = frozenset({
    "full_name", "person", "phone", "address", "address_line1",
    "address_line2", "company", "company_name", "email",
    "sender_name", "receiver_name", "sender_phone", "receiver_phone",
    "sender_address", "receiver_address", "payer_name", "payer_phone",
    "payer_address", "contact_person", "contact_person_phone",
    "tax_id", "sender_tin", "payer_tin",
})


def _mask(value: str) -> str:
    if not value:
        return value
    if len(value) <= 3:
        return "*" * len(value)
    return value[0] + "*" * (len(value) - 2) + value[-1]


def mask_pii(data: object) -> object:
    """Recursively mask PII fields in dicts/lists before writing to logs.

    Field-name-based; only redacts known PII keys. Structured payloads only —
    for free-form XML/JSON bodies use ``mask_pii_text``.
    """
    if isinstance(data, dict):
        return {
            k: _mask(v) if k in _PII_FIELDS and isinstance(v, str) else mask_pii(v)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [mask_pii(item) for item in data]
    return data


# ── Free-form text (raw response body / request echo) ─────────────────────
#
# When a carrier returns HTTP >=400, we log a chunk of the response body so
# operators can see the failure reason. Those chunks routinely contain PII
# echoed back from OUR request (SOAP/XML/JSON with sender name, phone,
# address, tax id). We can't pre-parse untrusted response bodies safely, so
# instead we run a set of conservative regexes that catch the common PII
# shapes and leave the rest alone.
#
# Design principles:
#   * False negatives (missed PII) are worse than false positives (mangled
#     debugging info) — patterns lean broad.
#   * Cap total input length so this cannot become a CPU sink on huge bodies.

_MAX_TEXT_LEN = 4000  # trim before scanning to keep regex time bounded

# Common XML / JSON element pairs that carriers echo back with our PII.
# Case-insensitive, multi-carrier: covers Exline (<phone>, <person>,
# <address>), Azimuth JSON keys ("sender_phone", "sender_name", ...) and
# CSE SOAP (<m:Phone>, <m:Client>, <m:Info>).
_TAG_PATTERNS = re.compile(
    r"(<(?:[a-z0-9]+:)?"
    r"(phone|person|address|client|official|receiver|sender|company|"
    r"email|full_name|tax_id|iin|bin|payer_name|payer_phone|payer_address|"
    r"contact_person|contact_person_phone|"
    r"sender_name|sender_phone|sender_address|"
    r"receiver_name|receiver_phone|receiver_address)"
    r"[^>]*>)([^<]{1,255})(</)",
    re.IGNORECASE,
)

# JSON string values for the same PII field names. Handles both quoted keys
# in strict JSON and unquoted keys in log-friendly repr dumps.
_JSON_PATTERNS = re.compile(
    r"(\"?(?:sender_name|sender_phone|sender_address|receiver_name|"
    r"receiver_phone|receiver_address|payer_name|payer_phone|payer_address|"
    r"contact_person|contact_person_phone|full_name|person|phone|address|"
    r"company|company_name|email|tax_id|sender_tin|payer_tin)\"?\s*:\s*)"
    r"\"([^\"\\]{1,255})\"",
    re.IGNORECASE,
)

# Kazakhstan phone numbers in any format (fallback for anywhere the tag/key
# didn't match — e.g. plaintext error messages that quote the phone).
_PHONE_PATTERN = re.compile(r"(?:\+?7|8)[\s\-()]?\d{3}[\s\-()]?\d{3}[\s\-()]?\d{2}[\s\-()]?\d{2}")

# Email addresses (RFC-5322 lite — good enough for logs).
_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# ИИН / БИН = exactly 12 consecutive digits, not preceded / followed by a
# digit (so we don't mangle numeric ids like Azimuth invoice numbers).
_TAX_ID_PATTERN = re.compile(r"(?<!\d)\d{12}(?!\d)")


def _mask_middle(match_text: str) -> str:
    if not match_text:
        return match_text
    if len(match_text) <= 3:
        return "*" * len(match_text)
    return match_text[0] + "*" * (len(match_text) - 2) + match_text[-1]


def mask_pii_text(text: str, *, max_len: int = _MAX_TEXT_LEN) -> str:
    """Redact common PII shapes from a free-form XML/JSON/text blob.

    Trims to ``max_len`` first so regex work is bounded. Returns a string
    safe to send to logs / Sentry. Do NOT use as a security boundary —
    this is best-effort scrubbing for operational logs.
    """
    if not text:
        return text
    trimmed = text[:max_len]

    def _tag_repl(m: re.Match[str]) -> str:
        return f"{m.group(1)}{_mask_middle(m.group(3))}{m.group(4)}"

    def _json_repl(m: re.Match[str]) -> str:
        return f'{m.group(1)}"{_mask_middle(m.group(2))}"'

    scrubbed = _TAG_PATTERNS.sub(_tag_repl, trimmed)
    scrubbed = _JSON_PATTERNS.sub(_json_repl, scrubbed)
    scrubbed = _PHONE_PATTERN.sub(lambda m: _mask_middle(m.group(0)), scrubbed)
    scrubbed = _EMAIL_PATTERN.sub(lambda m: _mask_middle(m.group(0)), scrubbed)
    scrubbed = _TAX_ID_PATTERN.sub(lambda m: _mask_middle(m.group(0)), scrubbed)

    if len(text) > max_len:
        scrubbed += f"…[truncated, orig {len(text)} chars]"
    return scrubbed
