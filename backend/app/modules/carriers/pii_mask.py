from __future__ import annotations

_PII_FIELDS = frozenset({
    "full_name", "person", "phone", "address", "address_line1",
    "address_line2", "company", "company_name",
})


def _mask(value: str) -> str:
    if not value:
        return value
    if len(value) <= 3:
        return "*" * len(value)
    return value[0] + "*" * (len(value) - 2) + value[-1]


def mask_pii(data: object) -> object:
    """Recursively mask PII fields in dicts/lists before writing to logs."""
    if isinstance(data, dict):
        return {
            k: _mask(v) if k in _PII_FIELDS and isinstance(v, str) else mask_pii(v)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [mask_pii(item) for item in data]
    return data
