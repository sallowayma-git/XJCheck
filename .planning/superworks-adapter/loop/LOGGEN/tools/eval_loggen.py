"""Read-only evaluation of sw_wire_routes.parquet against production pairs (LOGGEN phase 1).

Usage: python eval_loggen.py <replay_output_dir> <out_dir>

Per project it reads findings/ of the replay (pairs, sw_wire_routes, sw_ports, sw_port_coverage,
lines, line_groups) and writes:
  <out_dir>/<pid>.json       counts and sample lists for one project
  <out_dir>/summary.json     all projects aggregated
Nothing under src/ or tests/ is touched. Equivalence rules are the production helpers in
dwg_audit.audit.superworks_extractor (_key, _destination_keys, _clean_sw_endpoint_value).
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
sys.path.insert(0, str(ROOT / "src"))
from dwg_audit.audit.superworks_extractor import _clean_sw_endpoint_value, _destination_keys, _key  # noqa: E402

PROJECTS = ["p001", "p003", "p022", "p044", "p050", "p051", "p061", "p071", "p075", "p076"]
TERMINAL = {"端子", "装置端子"}


def _load_json(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return None


def _nonempty(value) -> bool:
    return value is not None and not (isinstance(value, float) and math.isnan(value)) and str(value).strip() != ""


def verdict(identity: str, value, aliases) -> str:
    """Production equivalence of a record identity and a pair side value."""
    if not _nonempty(value):
        return "value_missing"
    ik = _key(identity)
    raw = str(value)
    vk = _key(_clean_sw_endpoint_value(raw))
    if ik == _key(raw) or ik == vk:
        return "agree_exact"
    if ik in _destination_keys(raw):
        return "agree_range"
    if ik in {_key(a) for a in aliases or [] if a}:
        return "agree_alias"
    head = ik[:-len(vk)] if vk and ik.endswith(vk) else ""
    if head and any(ch.isalpha() for ch in head) and any(ch.isdigit() for ch in vk):
        return "agree_prefix"
    return "conflict"


def end_category(end: dict) -> str:
    if end.get("role") == "FAR" and not end.get("terminal_handle"):
        return "跨页文本端"
    category = end.get("category") or ""
    if category in TERMINAL:
        return category
    if category in {"接地", "线圈", "接插件"}:
        return category
    if end.get("role") in {"LOCAL"} or (end.get("terminal_handle_kind") == "INSERT" and not category):
        return "内部元件"
    return category or "未分类"


def analyze_project(pid: str, findings: Path, dxf_dir: dict) -> dict:
    routes = pd.read_parquet(findings / "sw_wire_routes.parquet")
    pairs = pd.read_parquet(findings / "pairs.parquet")
    lines = pd.read_parquet(findings / "lines.parquet", columns=["file_id", "line_id", "handle"])
    groups = pd.read_parquet(findings / "line_groups.parquet", columns=["file_id", "line_group_id", "member_line_ids"])
    ports = pd.read_parquet(findings / "sw_ports.parquet")
    coverage = pd.read_parquet(findings / "sw_port_coverage.parquet")

    handle_of = {(r.file_id, r.line_id): r.handle for r in lines.itertuples()}
    group_wires = {}
    for g in groups.itertuples():
        ids = _load_json(g.member_line_ids) or []
        group_wires[(g.file_id, g.line_group_id)] = {handle_of.get((g.file_id, i)) for i in ids} - {None}
    wire_groups = defaultdict(set)
    for key, handles in group_wires.items():
        for h in handles:
            wire_groups[(key[0], h)].add(key)
    group_pairs = defaultdict(list)
    for p in pairs.itertuples():
        group_pairs[(p.file_id, p.line_group_id)].append(p)
    wire_pairs = defaultdict(list)
    for (file_id, handle), keys in wire_groups.items():
        for key in keys:
            for p in group_pairs.get(key, []):
                if p.status != "discard":
                    wire_pairs[(file_id, handle)].append(p)

    # Production sides with SuperWORKS evidence, keyed by terminal (file, insert handle, port number).
    side_index = defaultdict(list)
    pair_status = {}
    pair_wire = {}
    for p in pairs.itertuples():
        pair_status[p.pair_id] = p.status
        pair_wire[p.pair_id] = group_wires.get((p.file_id, p.line_group_id), set())
        evidence = _load_json(p.evidence) or {}
        sw = evidence.get("superworks") or {}
        for name, value in (("left", p.left_value), ("right", p.right_value)):
            side = sw.get(name)
            if not side:
                continue
            side_index[(p.file_id, str(side.get("symbol_handle")), str(side.get("port_number")))].append({
                "pair_id": p.pair_id, "pair_kind": p.pair_kind, "status": p.status, "side": name,
                "value": None if not _nonempty(value) else str(value),
                "sw_identity": side.get("value"), "category": side.get("category"),
                "aliases": side.get("endpoint_aliases") or [], "line_group_id": p.line_group_id,
                "active": p.status != "discard", "file_id": p.file_id,
            })

    # Port table lookups for strict coverage.
    port_by_record = {r.record_id: r for r in ports.itertuples()}
    eligible_ports = []
    for c in coverage.itertuples():
        if not c.eligible or c.category not in TERMINAL:
            continue
        port = port_by_record.get(c.port_id)
        if port is None:
            continue
        eligible_ports.append({"port_id": c.port_id, "file_id": port.file_id, "insert": str(port.insert_handle),
                               "port": str(port.port_number), "identity": port.endpoint_identity if _nonempty(port.endpoint_identity) else None,
                               "category": c.category, "consumed": bool(c.consumed), "sheet_id": port.sheet_id})

    counts = Counter()
    side_forms = Counter()
    conflict_samples, agree_samples = [], []
    supplement = Counter()
    supplement_end_cats = Counter()
    supplement_end_cats_nonself = Counter()
    supplement_samples = []
    reasons = Counter()
    end_status = Counter()
    records = []
    record_index = {}

    for r in routes.itertuples():
        ends = _load_json(r.ends_json) or []
        reason_list = _load_json(r.reason_codes_json) or []
        for code in reason_list:
            if not str(code).startswith("end_"):
                reasons[f"record:{code}"] += 1
        counts[f"records:{r.source_kind}"] += 1
        counts[f"records:{r.source_kind}:ends_{r.end_count}"] += 1
        if r.source_kind == "LOGGEN" and r.end_count == 0:
            counts["records:LOGGEN:no_ends"] += 1
        for e in ends:
            status = e.get("status")
            end_status[(r.source_kind, e.get("role") if e.get("role") in ("LOCAL", "FAR") else "PART2", status)] += 1
            if status not in ("resolved", "resolved_by_text"):
                reasons[f"end:{status}:{end_category(e)}"] += 1
        if r.source_kind == "LOGGEN" and pd.notna(r.lineno_end_index):
            counts["lineno:matched_end"] += 1
        elif r.source_kind == "LOGGEN" and r.end_count:
            counts["lineno:unmatched"] += 1

        identities = [e.get("identity") for e in ends]
        both = len(ends) >= 2 and all(_nonempty(x) for x in identities)
        rec = {"record_id": r.record_id, "file_id": r.file_id, "sheet_id": r.sheet_id, "kind": r.source_kind,
               "wire": r.wire_handle, "both": both, "ends": ends, "coverage": []}
        records.append(rec)
        record_index[r.record_id] = rec

        covered_pair_sets = []
        end_active = []
        for e in ends:
            key = (e.get("file_id"), str(e.get("terminal_handle") or ""), str(e.get("port_number") or ""))
            matches = side_index.get(key, []) if e.get("terminal_handle") else []
            if e.get("terminal_handle") and e.get("file_id") is None:
                matches = []
            active = [m for m in matches if m["active"]]
            end_active.append(bool(active))
            covered_pair_sets.append({m["pair_id"] for m in active})
            e["_cat"] = end_category(e)
            if not matches:
                coverage_state = "none"
            elif active:
                coverage_state = "active"
            else:
                coverage_state = "discard_only"
            rec["coverage"].append(coverage_state)
            for m in matches:
                if not e.get("identity"):
                    continue
                form = verdict(e["identity"], m["value"], m["aliases"])
                if m["value"] is None:
                    side_forms["value_missing"] += 1
                    continue
                cat = e["_cat"]
                if m["active"]:
                    counts[f"side:{form}"] += 1
                    counts[f"side:{form}:{cat}"] += 1
                    side_forms[(form, cat)] += 1
                    sample = {"record_id": r.record_id, "file_id": r.file_id, "wire": r.wire_handle,
                              "end_index": e.get("end_index"), "identity": e.get("identity"),
                              "pair_id": m["pair_id"], "pair_value": m["value"], "pair_status": m["status"],
                              "pair_kind": m["pair_kind"], "side": m["side"], "category": cat,
                              "kind": r.source_kind, "terminal": e.get("terminal_handle"),
                              "port": e.get("port_number"), "end_file": e.get("file_id"),
                              "line_group_id": m["line_group_id"]}
                    if form == "conflict":
                        counts[f"conflict:{cat}"] += 1
                        conflict_samples.append(sample)
                    else:
                        agree_samples.append(sample)
                else:
                    counts[f"side:discard:{cat}"] += 1

        if both and not (any(len(s & t) for i, s in enumerate(covered_pair_sets) for t in covered_pair_sets[i + 1:])):
            # Both ends resolved but no single active pair holds both terminals.
            if all(end_active):
                klass = "both_ends_active_separate_pairs"
            elif any(end_active):
                klass = "one_end_active"
            else:
                klass = "no_active_end"
            if klass != "both_ends_active_separate_pairs":
                wp = wire_pairs.get((r.file_id, r.wire_handle), []) if r.wire_handle else []
                wire_state = "wire_no_active_pair" if not wp else "wire_has_active_pair"
                if wp:
                    wire_values = [p for p in wp if _nonempty(p.left_value) or _nonempty(p.right_value)]
                    agree = any(verdict(e["identity"], v, None) != "conflict"
                                for p in wire_values for v in (p.left_value, p.right_value) if _nonempty(v)
                                for e in ends if _nonempty(e.get("identity")))
                    wire_state = ("wire_has_active_pair_value_agrees" if agree
                                  else "wire_has_active_pair_no_agreeing_value" if wire_values
                                  else "wire_has_active_pair_no_values")
                supplement[klass] += 1
                supplement[f"wire:{wire_state}"] += 1
                selfloop = len({e.get("identity") for e in ends if _nonempty(e.get("identity"))}) == 1
                supplement["selfloop_same_identity_both_ends" if selfloop else "not_selfloop"] += 1
                if not selfloop:
                    for e in ends:
                        supplement_end_cats_nonself[e["_cat"]] += 1
                    supplement[f"nonself|{klass}|{'-'.join(sorted(e['_cat'] for e in ends))}"] += 1
                cats = tuple(sorted(e["_cat"] for e in ends))
                supplement[f"{klass}|{'-'.join(cats)}"] += 1
                for e in ends:
                    supplement_end_cats[e["_cat"]] += 1
                supplement_samples.append({"record_id": r.record_id, "file_id": r.file_id, "sheet_id": r.sheet_id,
                                           "klass": klass, "wire_state": wire_state, "selfloop": selfloop,
                                           "cats": list(cats), "wire": r.wire_handle,
                                           "source_kind": r.source_kind, "linestyle": r.linestyle,
                                           "ends": [{k: e.get(k) for k in ("role", "terminal_handle", "port_number",
                                                                          "device", "identity", "status", "file_id",
                                                                          "_cat")} for e in ends]})
            else:
                counts["both_ends_active_separate_pairs"] += 1
        elif both:
            counts["both_ends_covered_by_one_pair"] += 1
        counts["records_both_resolved"] += int(both)

    # Strict coverage (docs/COV-GAP): potential uplift from record ends with resolved identities.
    rec_end_lookup = defaultdict(list)
    for rec in records:
        if not rec["both"]:
            continue
        for index, e in enumerate(rec["ends"]):
            if e.get("terminal_handle") and e.get("file_id") and _nonempty(e.get("identity")):
                others = {o.get("identity") for j, o in enumerate(rec["ends"]) if j != index}
                rec_end_lookup[(e["file_id"], str(e["terminal_handle"]), str(e.get("port_number") or ""))].append(
                    (e["identity"], others))
    strict = Counter()
    strict_samples = []
    for port in eligible_ports:
        strict[f"eligible:{port['category']}"] += 1
        if port["consumed"]:
            strict[f"consumed:{port['category']}"] += 1
            continue
        found = rec_end_lookup.get((port["file_id"], port["insert"], port["port"]), [])
        matching = [others for ident, others in found if port["identity"] and _key(ident) == _key(port["identity"])]
        if matching:
            selfloop = all(port["identity"] in others and len(others) == 1 for others in matching)
            strict[f"potential_selfloop:{port['category']}" if selfloop else f"potential:{port['category']}"] += 1
            if selfloop:
                continue
            if len(strict_samples) < 40:
                strict_samples.append({k: port[k] for k in ("port_id", "file_id", "insert", "port", "identity", "category")})
        elif found:
            strict[f"potential_identity_differs:{port['category']}"] += 1
    return {
        "project": pid,
        "counts": dict(counts),
        "side_forms": {str(k): v for k, v in side_forms.items()},
        "end_status": {"|".join(map(str, k)): v for k, v in end_status.items()},
        "reasons": dict(reasons),
        "supplement": dict(supplement),
        "supplement_end_categories": dict(supplement_end_cats),
        "supplement_end_categories_nonself": dict(supplement_end_cats_nonself),
        "strict": dict(strict),
        "conflict_samples": conflict_samples,
        "agree_samples": agree_samples[:400],
        "supplement_samples": supplement_samples,
        "strict_samples": strict_samples,
        "pair_count": int(len(pairs)),
        "pair_status": dict(Counter(pairs.status)),
    }


def main(output_root: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / ".planning/superworks-adapter/corpus_manifest.json").read_text(encoding="utf-8"))
    dxf_dir = {}
    for project in manifest["projects"]:
        dxf_dir[project["project_id"]] = {f["file_id"]: f["dxf_path"] for f in project["files"]}
    summary = {}
    for pid in PROJECTS:
        complete = json.loads((output_root / pid / "complete.json").read_text(encoding="utf-8"))
        findings = Path(complete["project_dir"]) / "findings"
        result = analyze_project(pid, findings, dxf_dir[pid])
        result["elapsed_seconds"] = complete.get("elapsed_seconds")
        (out_dir / f"{pid}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        summary[pid] = {k: v for k, v in result.items() if k not in ("conflict_samples", "agree_samples",
                                                                    "supplement_samples", "strict_samples")}
        print(pid, "done", flush=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
