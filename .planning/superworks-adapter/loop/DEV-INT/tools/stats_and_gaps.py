"""DEV-INT statistics over one replay run (read-only): link counts, exclusion reasons, coverage views by family,
PCL corroboration, and the Top uncovered-port buckets (the next direction).

Usage: python stats_and_gaps.py <round_dir> <out_dir> [--links-parquet <path>]

Inputs per project (findings): sw_ports, sw_port_coverage, sw_symbols, sw_device_internal_links, lines, line_groups,
and superworks_summary.json. Family = the top-level folder under test/ (from the frozen corpus manifest).
Outputs: <out_dir>/stats.json, <out_dir>/gaps.json and, when requested, a combined links parquet for sampling.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path("F:/workspace/XJToolkit")
sys.path.insert(0, str(ROOT / "src"))
from dwg_audit.audit.superworks_device_internal import INTERNAL_CATEGORIES, wire_keys_from_lines  # noqa: E402

TERMINALS = ("端子", "装置端子")
VIEWS = ("strict", "with_continuity", "with_internal", "total")


def _has_text(value) -> bool:
    """True for a non-empty value; parquet stores a missing identity as NaN, which is truthy."""
    if value is None or (isinstance(value, float) and value != value):
        return False
    return bool(str(value).strip())


def _json(value, default):
    if isinstance(value, str):
        return json.loads(value or json.dumps(default))
    if value is None or (isinstance(value, float) and value != value):
        return default
    return value


def _family_map():
    manifest = json.loads((ROOT / ".planning/superworks-adapter/corpus_manifest.json").read_text(encoding="utf-8"))
    return {p["project_id"]: Path(p["input_root"]).relative_to(ROOT / "test").parts[0] for p in manifest["projects"]}


def _project_findings(round_dir: Path):
    for findings in sorted(round_dir.glob("p*/*/findings")):
        yield findings.parent.parent.name, findings


def contact_handle_of(port):
    contacts = _json(port.get("wire_contacts"), [])
    return contacts[0].get("wire_handle") if contacts else ""


def _route_note(port, keys, route_by_wire) -> str:
    """What the wire-route records say about a dangling wire (no other recorded port on the wire)."""
    routes = []
    for contact in _json(port.get("wire_contacts"), []):
        key = (port.get("file_id"), str(contact.get("wire_handle") or ""))
        routes.extend(route_by_wire.get(keys.get(key, key), []))
    if not routes:
        return "无路由记录"
    ends = [end for route in routes for end in _json(route.get("ends_json"), [])]
    if any(end.get("category") == "接地" for end in ends):
        return "接地端"
    if any(end.get("far_source") == "cross_page" for end in ends):
        return "跨页远端"
    if all(int(route.get("end_count") or 0) < 2 for route in routes):
        return "单端记录(另一端未记录)"
    return "双端记录未准入"


def _open_end_probe(port, keys, lines_of_wire, contact, symbols, own_handle, other_lines) -> str:
    """Classify the far end of a dangling wire: a free end, a further line, or a recorded symbol (not the terminal)."""
    import math
    cx, cy = float(contact.get("x", 0.0)), float(contact.get("y", 0.0))
    ends = []
    for line in lines_of_wire:
        for x, y in ((line["start_x"], line["start_y"]), (line["end_x"], line["end_y"])):
            if math.hypot(float(x) - cx, float(y) - cy) > 0.6:
                ends.append((float(x), float(y)))
    if not ends:
        return "无远端"
    x, y = min(ends, key=lambda e: math.hypot(e[0] - cx, e[1] - cy))
    if any(math.hypot(ox - x, oy - y) <= 0.6 for ox, oy in other_lines):
        return "远端接其它导线"
    for handle, sx, sy in symbols:
        if handle != own_handle and math.hypot(sx - x, sy - y) <= 3.0:
            return "远端近旁有 SW 符号"
    return "远端无记录(自由端)"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("round_dir")
    parser.add_argument("out_dir")
    parser.add_argument("--links-parquet", default=None)
    args = parser.parse_args()
    round_dir, out_dir = Path(args.round_dir), Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    family = _family_map()

    family_views = defaultdict(Counter)
    link_rows, exclusions, bucket_counts = [], Counter(), Counter()
    bucket_examples = defaultdict(list)
    block_links, family_links = Counter(), Counter()
    probe_counts = Counter()
    per_project = {}
    for pid, findings in _project_findings(round_dir):
        fam = family.get(pid, "unknown")
        ports = pd.read_parquet(findings / "sw_ports.parquet").to_dict("records")
        port_by_id = {p["record_id"]: p for p in ports}
        coverage = pd.read_parquet(findings / "sw_port_coverage.parquet").to_dict("records")
        symbols = pd.read_parquet(findings / "sw_symbols.parquet")
        block_of = {(r.file_id, r.insert_handle): r.block_name for r in symbols.itertuples()}
        summary = json.loads((findings / "superworks_summary.json").read_text(encoding="utf-8"))
        exclusions.update(summary.get("device_internal", {}).get("stats", {}))
        lines = pd.read_parquet(findings / "lines.parquet").to_dict("records")
        groups = pd.read_parquet(findings / "line_groups.parquet").to_dict("records")
        keys = wire_keys_from_lines(lines, groups)
        wire_members = defaultdict(dict)
        for p in ports:
            for contact in _json(p.get("wire_contacts"), []):
                handle = str(contact.get("wire_handle") or "")
                if not handle:
                    continue
                key = (p["file_id"], handle)
                wire_members[keys.get(key, key)][p["record_id"]] = p
        lines_by_file = defaultdict(list)
        line_members = defaultdict(list)
        for l in lines:
            lines_by_file[l["file_id"]].append(l)
            line_members[keys.get((l["file_id"], str(l["handle"])), (l["file_id"], str(l["handle"])))].append(l)
        symbols_by_file = defaultdict(list)
        for r in symbols.itertuples():
            if pd.notna(r.insert_x) and pd.notna(r.insert_y):
                symbols_by_file[r.file_id].append((r.insert_handle, float(r.insert_x), float(r.insert_y)))
        routes = pd.read_parquet(findings / "sw_wire_routes.parquet").to_dict("records")
        route_by_wire = defaultdict(list)
        for route in routes:
            key = (route["file_id"], str(route["wire_handle"]))
            route_by_wire[keys.get(key, key)].append(route)
        links = pd.read_parquet(findings / "sw_device_internal_links.parquet") if (
            findings / "sw_device_internal_links.parquet").exists() else pd.DataFrame()
        for link in links.to_dict("records"):
            block_links[block_of.get((link["file_id"], link["element_insert_handle"]))] += 1
            family_links[fam] += 1
            row = {"project": pid, "family": fam, **{k: v for k, v in link.items()}}
            link_rows.append(row)
        pcl_total = int(links.pcl_corroborated.astype(bool).sum()) if len(links) else 0
        per_project[pid] = {"family": fam, "links": int(len(links)), "pcl": pcl_total}
        for row in coverage:
            if not bool(row["eligible"]):
                continue
            family_views[fam]["eligible"] += 1
            family_views[fam]["strict"] += int(bool(row["consumed"]))
            family_views[fam]["with_continuity"] += int(bool(row["consumed_with_continuity"]))
            internal_ids = _json(row.get("device_internal_link_ids"), [])
            family_views[fam]["with_internal"] += int(bool(row["consumed"]) or bool(internal_ids))
            family_views[fam]["total"] += int(bool(row["consumed_with_internal"]))
            if bool(row["consumed_with_internal"]):
                continue
            port = port_by_id.get(row["port_id"], {})
            reasons = _json(row.get("reason_codes"), [])
            reason = reasons[0] if reasons else "none"
            other_categories = set()
            others_seen = set()
            for contact in _json(port.get("wire_contacts"), []):
                handle = str(contact.get("wire_handle") or "")
                key = (port.get("file_id"), handle)
                for other_id, other in wire_members.get(keys.get(key, key), {}).items():
                    if other_id == row["port_id"] or other_id in others_seen:
                        continue
                    others_seen.add(other_id)
                    category = other.get("category") or "未分类"
                    if category in INTERNAL_CATEGORIES and not _has_text(other.get("endpoint_identity")):
                        category = f"{category}(无身份)"
                    other_categories.add(category)
            signature = " + ".join(sorted(other_categories)) if other_categories else "悬空(无其它端口)"
            note = "-"
            if not other_categories:
                note = _route_note(port, keys, route_by_wire)
                wire_key = keys.get((port.get("file_id"), str(contact_handle_of(port))), None)
                first = next((c for c in _json(port.get("wire_contacts"), []) if c.get("wire_handle")), None)
                if first is not None:
                    key = (port.get("file_id"), str(first.get("wire_handle")))
                    group = keys.get(key, key)
                    wire_lines = line_members.get(group, [])
                    own_lines = {(l["file_id"], l["handle"]) for l in wire_lines}
                    others_all = [(l["start_x"], l["start_y"]) for l in lines_by_file.get(port.get("file_id"), [])
                                  if (l["file_id"], l["handle"]) not in own_lines] +                                  [(l["end_x"], l["end_y"]) for l in lines_by_file.get(port.get("file_id"), [])
                                  if (l["file_id"], l["handle"]) not in own_lines]
                    probe = _open_end_probe(port, keys, wire_lines, first, symbols_by_file.get(port.get("file_id"), []),
                                            port.get("insert_handle"), others_all)
                    probe_counts[f"{note}|{probe}"] += 1
            bucket = f"{port.get('category') or row['category']} | {reason} | 另一端: {signature} | 路由: {note}"
            bucket_counts[bucket] += 1
            if len(bucket_examples[bucket]) < 3:
                bucket_examples[bucket].append(f"{pid} {row['port_id']}")

    total_views = {}
    for fam, counts in sorted(family_views.items()):
        total_views[fam] = {k: counts[k] for k in ("eligible",) + VIEWS}
    grand = Counter()
    for counts in family_views.values():
        grand.update(counts)
    ratios = {view: (grand[view] / grand["eligible"] if grand["eligible"] else None) for view in VIEWS}
    stats = {
        "projects": len(per_project),
        "links": len(link_rows),
        "pcl_corroborated": sum(v["pcl"] for v in per_project.values()),
        "pcl_ratio": (sum(v["pcl"] for v in per_project.values()) / len(link_rows)) if link_rows else None,
        "exclusion_reasons": dict(sorted(exclusions.items())),
        "links_by_family": dict(sorted(family_links.items())),
        "links_by_element_block": dict(block_links.most_common()),
        "coverage_by_family": total_views,
        "coverage_grand": {"eligible": grand["eligible"], **{v: grand[v] for v in VIEWS},
                           "ratios": ratios},
        "per_project": per_project,
    }
    (out_dir / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    gaps = {
        "uncovered_eligible": sum(bucket_counts.values()),
        "dangling_open_end_probe": dict(probe_counts.most_common(12)),
        "top": [{"rank": i + 1, "bucket": bucket, "count": count, "examples": bucket_examples[bucket]}
                for i, (bucket, count) in enumerate(bucket_counts.most_common(12))],
    }
    (out_dir / "gaps.json").write_text(json.dumps(gaps, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.links_parquet:
        pd.DataFrame(link_rows).to_parquet(args.links_parquet, index=False)
    print(json.dumps({"links": stats["links"], "pcl_ratio": stats["pcl_ratio"], "grand": stats["coverage_grand"]},
                     ensure_ascii=False, indent=1))
    for row in gaps["top"][:10]:
        print(row["count"], row["bucket"])


if __name__ == "__main__":
    main()
