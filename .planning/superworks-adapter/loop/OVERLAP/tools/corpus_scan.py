"""Read-only corpus scan: stacked contradictory texts (叠放矛盾文字) in round12 texts.parquet.

A location is a cluster of model-space, non-MARK texts on one sheet whose insert points lie within
min(height) * 0.25 of each other and whose normalized values differ. Each location is classified with
the same helper the audit uses (resolve_overlapping_texts). Also records whether the location holds a
text that is a strip endpoint candidate (valid external endpoint value).
Outputs JSON to .tmp/loop_overlap_corpus_scan.json. Inputs are only read.
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

sys.path.insert(0, "F:/workspace/XJToolkit/src")
from dwg_audit.domain.models import TextItem  # noqa: E402
from dwg_audit.extract.text_overlap import resolve_overlapping_texts  # noqa: E402
from dwg_audit.audit.component_diagrams import _strip_external_endpoint_values  # noqa: E402

ROOT = Path("F:/workspace/XJToolkit")
RUN = ROOT / ".tmp/superworks_round12_full"
OUT = ROOT / ".tmp/loop_overlap_corpus_scan.json"


def to_item(row) -> TextItem:
    src = row.source_block_name
    return TextItem(
        text_id=str(row.text_id), sheet_id=str(row.sheet_id), file_id=str(row.file_id), handle=str(row.handle),
        entity_type=str(row.entity_type), text=str(row.text), normalized_text=str(row.normalized_text),
        is_numeric_candidate=bool(row.is_numeric_candidate), layer=str(row.layer), rotation_deg=float(row.rotation_deg),
        height=float(row.height), insert_x=float(row.insert_x), insert_y=float(row.insert_y),
        bbox_min_x=float(row.bbox_min_x), bbox_min_y=float(row.bbox_min_y),
        bbox_max_x=float(row.bbox_max_x), bbox_max_y=float(row.bbox_max_y),
        source_block_name=None if (src is None or (isinstance(src, float) and pd.isna(src))) else str(src),
    )


def clusters(items):
    """Greedy position clusters using the endpoint tolerance; returns lists with >= 2 distinct values."""
    out = []
    used = set()
    for anchor in items:
        if anchor.text_id in used:
            continue
        group = [anchor]
        for other in items:
            if other is anchor or other.text_id in used:
                continue
            tol = min(anchor.height, other.height) * 0.25
            if abs(other.insert_x - anchor.insert_x) <= tol and abs(other.insert_y - anchor.insert_y) <= tol:
                group.append(other)
        if len({t.normalized_text for t in group}) >= 2:
            for t in group:
                used.add(t.text_id)
            out.append(group)
    return out


def main() -> None:
    projects = sorted(p.name for p in RUN.iterdir() if p.is_dir() and (p / "complete.json").exists())
    totals = Counter()
    examples = defaultdict(list)
    per_project = {}
    for pid in projects:
        base = Path(json.loads((RUN / pid / "complete.json").read_text(encoding="utf-8"))["project_dir"])
        texts = pd.read_parquet(base / "findings/texts.parquet")
        pages = pd.read_parquet(base / "findings/pages.parquet") if (base / "findings/pages.parquet").exists() else None
        page_name = {}
        if pages is not None:
            for r in pages.itertuples(index=False):
                page_name[str(r.sheet_id)] = f"{getattr(r, 'sheet_no', '')} {getattr(r, 'filename', '')}"
        model = texts[texts.source_block_name.isna() & (texts.layer.astype(str).str.upper() != "MARK")]
        items_by_sheet = defaultdict(list)
        for row in model.itertuples(index=False):
            if not str(row.normalized_text or "").strip():
                continue
            items_by_sheet[str(row.sheet_id)].append(to_item(row))
        pcount = Counter()
        for sheet_id, items in items_by_sheet.items():
            for group in clusters(items):
                endpoint_like = any(_strip_external_endpoint_values(t.normalized_text) for t in group)
                res = resolve_overlapping_texts(group)
                bucket = "resolved" if res.resolved else "unresolved"
                totals["locations"] += 1
                totals["endpoint_like_locations"] += int(endpoint_like)
                totals[bucket] += 1
                totals[f"{bucket}_endpoint_like"] += int(endpoint_like)
                pcount[bucket] += 1
                ex = {
                    "project": pid, "sheet_id": sheet_id, "page": page_name.get(sheet_id, ""),
                    "values": list(res.values), "handles": [t.handle for t in group],
                    "reason": res.reason,
                    "winner": res.winner.normalized_text if res.winner else None,
                    "winner_handle": res.winner.handle if res.winner else None,
                    "endpoint_like": endpoint_like,
                }
                examples[bucket + ("_endpoint_like" if endpoint_like else "")].append(ex)
                if not res.resolved:
                    totals["reason:" + res.reason] += 1
        per_project[pid] = dict(pcount)
    result = {"projects": len(projects), "totals": dict(totals), "per_project": per_project,
              "examples": {k: v[:3] for k, v in examples.items()}}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["totals"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
