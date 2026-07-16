from __future__ import annotations

import math
from collections import Counter
from collections import defaultdict
from typing import Any
from typing import Iterable

from dwg_audit.domain.models import LineEntity
from dwg_audit.domain.models import TextItem
from dwg_audit.audit.token_parser import parse_text_tokens


ALGORITHM_VERSION = "semantic-attachment-v1"
ATTACHABLE_KINDS = frozenset(
    {
        "WIRE_N_NUMBER",
        "TERMINAL_LOCAL",
        "EXTERNAL_ENDPOINT",
        "COMPONENT_BODY",
        "DEVICE_TAG",
        "SCOPED_PREFIX",
    }
)
LOW_MARGIN_THRESHOLD = 0.02


def build_semantic_attachment_candidates(
    texts: list[TextItem],
    lines: list[LineEntity],
    tokens: list[dict[str, Any]] | None = None,
    *,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """Geometry-only shadow semantic attachment candidates (no Pair/Issue creation)."""
    if top_k < 1:
        return []

    token_rows = tokens if tokens is not None else parse_text_tokens(texts)
    texts_by_id = {text.text_id: text for text in texts}
    lines_by_sheet: dict[str, list[LineEntity]] = defaultdict(list)
    for line in lines:
        lines_by_sheet[line.sheet_id].append(line)

    rows: list[dict[str, Any]] = []
    attachment_counter = 0

    for token in token_rows:
        kind = str(token.get("token_kind") or "")
        if kind not in ATTACHABLE_KINDS:
            continue

        sheet_id = str(token.get("sheet_id") or "")
        sheet_lines = lines_by_sheet.get(sheet_id, [])
        if not sheet_lines:
            continue

        text_id = str(token.get("text_id") or "")
        text = texts_by_id.get(text_id)
        insert_x = float(token.get("insert_x", text.insert_x if text is not None else 0.0))
        insert_y = float(token.get("insert_y", text.insert_y if text is not None else 0.0))
        token_id = str(token.get("token_id") or f"TK1-{text_id}")
        token_text = str(token.get("normalized_text") or token.get("raw_text") or "")

        candidates: list[tuple[float, str, str, float, float]] = []
        for line in sheet_lines:
            for endpoint, x, y in (
                ("start", line.start_x, line.start_y),
                ("end", line.end_x, line.end_y),
            ):
                distance = math.hypot(insert_x - x, insert_y - y)
                candidates.append((distance, line.line_id, endpoint, x, y))

        if not candidates:
            continue

        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        top = candidates[:top_k]
        scores = [1.0 / (1.0 + distance) for distance, *_ in top]
        score_1 = scores[0]
        score_2 = scores[1] if len(scores) > 1 else None
        margin = (score_1 - score_2) if score_2 is not None else 0.0

        for rank, ((distance, line_id, endpoint, target_x, target_y), score) in enumerate(
            zip(top, scores),
            start=1,
        ):
            attachment_counter += 1
            selected = rank == 1
            reason_codes = ["NEAREST_LINE_ENDPOINT"] if selected else ["NOT_NEAREST_LINE_ENDPOINT"]
            if selected and score_2 is not None and margin < LOW_MARGIN_THRESHOLD:
                reason_codes.append("LOW_MARGIN")

            rows.append(
                {
                    "attachment_id": f"SA{attachment_counter:04d}",
                    "sheet_id": sheet_id,
                    "token_id": token_id,
                    "text_id": text_id,
                    "token_kind": kind,
                    "token_text": token_text,
                    "target_kind": "LINE_ENDPOINT",
                    "target_line_id": line_id,
                    "target_endpoint": endpoint,
                    "target_x": target_x,
                    "target_y": target_y,
                    "rank": rank,
                    "distance": distance,
                    "score": score,
                    "selected": selected,
                    "state": "SELECTED" if selected else "REJECTED",
                    "margin": margin if selected else 0.0,
                    "reason_codes": reason_codes,
                    "algorithm_version": ALGORITHM_VERSION,
                }
            )

    return rows


def summarize_semantic_attachments(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Summarize shadow attachment candidate rows."""
    material = list(rows)
    selected = 0
    rejected = 0
    low_margin_count = 0
    by_kind: Counter[str] = Counter()

    for row in material:
        state = str(row.get("state") or "")
        if state == "SELECTED" or row.get("selected") is True:
            selected += 1
            kind = str(row.get("token_kind") or "UNKNOWN")
            by_kind[kind] += 1
            reasons = row.get("reason_codes") or []
            if "LOW_MARGIN" in reasons or float(row.get("margin") or 0.0) < LOW_MARGIN_THRESHOLD:
                # Count low-margin only when there was a real competitor (margin computed
                # against a second score). margin==0 with single candidate is not low.
                if "LOW_MARGIN" in reasons:
                    low_margin_count += 1
        else:
            rejected += 1

    return {
        "selected_count": selected,
        "rejected_count": rejected,
        "total_count": len(material),
        "by_token_kind": dict(sorted(by_kind.items())),
        "low_margin_count": low_margin_count,
        "algorithm_version": ALGORITHM_VERSION,
    }
