from __future__ import annotations

import re
from typing import Any

from dwg_audit.domain.models import TextItem


# Specialized kinds first; ANNOTATION is the fallback.
TOKEN_KINDS = (
    "SCOPED_PREFIX",
    "WIRE_N_NUMBER",
    "COMPONENT_BODY",
    "COMPONENT_PORT",
    "EXTERNAL_ENDPOINT",
    "TERMINAL_LOCAL",
    "DEVICE_TAG",
    "PAGE_REFERENCE",
    "ANNOTATION",
)

_SCOPED_PREFIX = re.compile(r"^(?P<prefix>\d+(?:-\d+)?)n$", re.IGNORECASE)
_WIRE_N_NUMBER = re.compile(r"^n(?P<local_number>\d+)$", re.IGNORECASE)
_COMPONENT_BODY = re.compile(
    r"^(?P<prefix>\d+(?:-\d+)?)(?P<family>KLP|ZKK)(?P<ordinal>\d*)$",
    re.IGNORECASE,
)
_COMPONENT_PORT = re.compile(r"^(?P<ordinal>[1-6])$")
_EXTERNAL_ENDPOINT = re.compile(
    r"^(?P<prefix>\d+(?:-\d+)?)(?P<family>QD|FD|YD|DK)(?P<ordinal>\d+)$",
    re.IGNORECASE,
)
_TERMINAL_LOCAL = re.compile(r"^(?P<local_number>\d{1,3})$")
_DEVICE_TAG = re.compile(
    r"^(?P<prefix>\d+(?:-\d+)?)(?P<family>[A-Za-z]{1,4})(?P<ordinal>\d+)$",
    re.IGNORECASE,
)
_PAGE_REFERENCE = re.compile(
    r"(详见|另页|see\s+page|see\s+sheet|refer\s+to\s+page)",
    re.IGNORECASE,
)

_COMPONENT_BODY_FAMILIES = frozenset({"KLP", "ZKK"})
_EXTERNAL_FAMILIES = frozenset({"QD", "FD", "YD", "DK"})


def parse_text_tokens(texts: list[TextItem]) -> list[dict[str, Any]]:
    """Parse TextItems into deterministic token rows (usually one primary per text)."""
    rows: list[dict[str, Any]] = []
    for text in texts:
        parsed = _parse_one(text)
        if not parsed:
            continue
        if len(parsed) == 1:
            token = parsed[0]
            token["token_id"] = f"TK1-{text.text_id}"
            rows.append(token)
        else:
            for index, token in enumerate(parsed, start=1):
                token["token_id"] = f"TK1-{text.text_id}-{index}"
                rows.append(token)
    return rows


def _parse_one(text: TextItem) -> list[dict[str, Any]]:
    raw_text = text.text if text.text is not None else ""
    normalized = (text.normalized_text if text.normalized_text is not None else raw_text).strip()
    if not normalized:
        return []

    base = {
        "text_id": text.text_id,
        "sheet_id": text.sheet_id,
        "file_id": text.file_id,
        "raw_text": raw_text,
        "normalized_text": normalized,
        "prefix": None,
        "family": None,
        "local_number": None,
        "ordinal": None,
        "layer": text.layer,
        "insert_x": text.insert_x,
        "insert_y": text.insert_y,
        "bbox": [text.bbox_min_x, text.bbox_min_y, text.bbox_max_x, text.bbox_max_y],
    }

    match = _SCOPED_PREFIX.fullmatch(normalized)
    if match:
        return [
            {
                **base,
                "token_kind": "SCOPED_PREFIX",
                "prefix": match.group("prefix"),
                "confidence": 0.98,
                "reason_codes": ["MATCH_SCOPED_PREFIX"],
            }
        ]

    match = _WIRE_N_NUMBER.fullmatch(normalized)
    if match:
        return [
            {
                **base,
                "token_kind": "WIRE_N_NUMBER",
                "local_number": match.group("local_number"),
                "confidence": 0.97,
                "reason_codes": ["MATCH_WIRE_N_NUMBER"],
            }
        ]

    match = _COMPONENT_BODY.fullmatch(normalized)
    if match:
        family = match.group("family").upper()
        ordinal = match.group("ordinal") or None
        return [
            {
                **base,
                "token_kind": "COMPONENT_BODY",
                "prefix": match.group("prefix"),
                "family": family,
                "ordinal": ordinal,
                "confidence": 0.96,
                "reason_codes": ["MATCH_COMPONENT_BODY", f"FAMILY_{family}"],
            }
        ]

    match = _COMPONENT_PORT.fullmatch(normalized)
    if match:
        return [
            {
                **base,
                "token_kind": "COMPONENT_PORT",
                "ordinal": match.group("ordinal"),
                "confidence": 0.9,
                "reason_codes": ["MATCH_COMPONENT_PORT"],
            }
        ]

    match = _EXTERNAL_ENDPOINT.fullmatch(normalized)
    if match:
        family = match.group("family").upper()
        return [
            {
                **base,
                "token_kind": "EXTERNAL_ENDPOINT",
                "prefix": match.group("prefix"),
                "family": family,
                "ordinal": match.group("ordinal"),
                "confidence": 0.95,
                "reason_codes": ["MATCH_EXTERNAL_ENDPOINT", f"FAMILY_{family}"],
            }
        ]

    match = _TERMINAL_LOCAL.fullmatch(normalized)
    if match and (text.is_numeric_candidate or normalized.isdigit()):
        return [
            {
                **base,
                "token_kind": "TERMINAL_LOCAL",
                "local_number": match.group("local_number"),
                "confidence": 0.92 if text.is_numeric_candidate else 0.85,
                "reason_codes": ["MATCH_TERMINAL_LOCAL"],
            }
        ]

    match = _DEVICE_TAG.fullmatch(normalized)
    if match:
        family = match.group("family").upper()
        # COMPONENT_BODY / EXTERNAL_ENDPOINT already claimed their families.
        if family not in _COMPONENT_BODY_FAMILIES and family not in _EXTERNAL_FAMILIES:
            return [
                {
                    **base,
                    "token_kind": "DEVICE_TAG",
                    "prefix": match.group("prefix"),
                    "family": family,
                    "ordinal": match.group("ordinal"),
                    "confidence": 0.88,
                    "reason_codes": ["MATCH_DEVICE_TAG", f"FAMILY_{family}"],
                }
            ]

    if _PAGE_REFERENCE.search(normalized):
        return [
            {
                **base,
                "token_kind": "PAGE_REFERENCE",
                "confidence": 0.8,
                "reason_codes": ["MATCH_PAGE_REFERENCE"],
            }
        ]

    return [
        {
            **base,
            "token_kind": "ANNOTATION",
            "confidence": 0.4,
            "reason_codes": ["FALLBACK_ANNOTATION"],
        }
    ]
