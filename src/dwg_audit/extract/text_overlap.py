"""Resolution of contradictory texts stacked at one position.

Rule (general drawing convention, not tied to any project, sheet, handle or value):

- When two or more texts with different values sit at the same position on a drawing and the
  order in which they were drawn can be read, the latest batch is the one that takes part in
  recognition and checks. Earlier texts are dropped silently; they leave evidence only.
- When that order cannot be read, the conflict stays for review. The issue must then say that
  overlapping text was detected and list the overlapping values.

DXF entities carry no timestamps. Within one DXF file, entity handles (hex) increase with
creation order, so the handle is the time basis. The order is readable only when all of these hold:

- every text has a parseable hexadecimal handle;
- all texts come from the same DXF file (same file_id);
- every text is an independent model-space entity: no source_block_name and not an ATTRIB;
  a block-internal text or ATTRIB has a handle from a different source and is not comparable;
- the handles are pairwise distinct.

Texts with the same value are not contradictory. They never make a position conflicting, and
an earlier text with the same value as the latest one is not listed as superseded.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from dwg_audit.domain.models import TextItem

OVERLAP_RESOLUTION_LATEST_HANDLE = "latest_handle"
OVERLAP_UNRESOLVED = "unresolved"

_HEX_HANDLE_PATTERN = re.compile(r"[0-9A-Fa-f]+")


@dataclass(frozen=True, slots=True)
class TextOverlapResolution:
    """Outcome of resolving one group of stacked texts.

    ``winner`` is the latest text when the order is readable, else None. ``superseded`` holds the
    earlier texts whose value differs from the winner. ``reason`` is ``latest_handle`` when resolved,
    otherwise a code naming why the order is not readable. ``values`` lists the distinct overlapping
    values (sorted), used in the review message.
    """

    winner: TextItem | None
    superseded: tuple[TextItem, ...]
    reason: str
    values: tuple[str, ...]

    @property
    def resolved(self) -> bool:
        return self.winner is not None

    def superseded_evidence(self) -> list[dict[str, str | None]]:
        return [
            {"text_id": text.text_id, "value": text.normalized_text, "handle": text.handle}
            for text in self.superseded
        ]


def handle_order_key(text: TextItem) -> int | None:
    """Creation-order key of a text, or None when its handle cannot be compared.

    Only plain hexadecimal handles of model-space, non-ATTRIB entities qualify. Expanded
    block content (``<insert>:VIRTUAL:n``) and ATTRIB texts carry synthetic handles.
    """
    if text.source_block_name or str(text.entity_type or "").upper() == "ATTRIB":
        return None
    handle = str(text.handle or "").strip()
    if not _HEX_HANDLE_PATTERN.fullmatch(handle):
        return None
    return int(handle, 16)


def resolve_overlapping_texts(texts: list[TextItem]) -> TextOverlapResolution:
    """Resolve a group of texts stacked at one position.

    The caller passes the texts found at the position, including the one it selected. The result
    is resolved only when every text is comparable and their values disagree; otherwise the
    winner is None and ``reason`` says why.
    """
    ordered = sorted(texts, key=lambda text: (text.text_id or "", text.handle or ""))
    values = tuple(sorted({text.normalized_text for text in ordered if text.normalized_text}))
    if len(values) < 2:
        return TextOverlapResolution(None, (), "no_conflicting_values", values)
    if len(ordered) < 2:
        return TextOverlapResolution(None, (), "single_text", values)
    if len({text.file_id for text in ordered}) > 1:
        return TextOverlapResolution(None, (), "different_files", values)

    keys: dict[str, int] = {}
    for text in ordered:
        key = handle_order_key(text)
        if key is None:
            return TextOverlapResolution(None, (), "handle_not_comparable", values)
        keys[text.text_id] = key
    if len(set(keys.values())) < len(keys):
        return TextOverlapResolution(None, (), "duplicate_handle", values)

    winner = max(ordered, key=lambda text: keys[text.text_id])
    superseded = tuple(
        text
        for text in ordered
        if text is not winner and text.normalized_text != winner.normalized_text
    )
    return TextOverlapResolution(winner, superseded, OVERLAP_RESOLUTION_LATEST_HANDLE, values)


def overlap_detected_text(values: tuple[str, ...] | list[str]) -> str:
    """Review wording for an unresolved overlap, e.g. ``检测到文字重叠：8n401 / 8nB01``."""
    return "检测到文字重叠：" + " / ".join(values)
