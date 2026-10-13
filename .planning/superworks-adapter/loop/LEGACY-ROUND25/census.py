"""Read final replay artifacts; write an isolated, reproducible legacy census.

Literal endpoint matches are diagnostics, not electrical equivalence or a
production supersession decision. No replay inputs or production code change.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

SW_KEYS = ("superworks", "superworks_constraints", "sw_conflicts",
           "sw_dictionary_warnings", "sw_backplate_corroboration")


def decode(value):
    if isinstance(value, (dict, list)):
        return value
    if value is None or pd.isna(value):
        return None
    return json.loads(value)


def clean(value):
    if value is None or pd.isna(value):
        return None
    return str(value).strip() or None


def endpoint_key(pair):
    left, right = clean(pair.left_value), clean(pair.right_value)
    return tuple(sorted((left, right))) if left and right else None


def counts(rows, key):
    return dict(sorted(Counter(row[key] for row in rows).items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    rows, issues, manifests = [], [], []
    ledger_counts = Counter()
    retirement_checks = Counter()
    corroboration_checks = Counter()
    for project in sorted(args.run.glob("p[0-9][0-9][0-9]")):
        findings, = project.glob("*/findings")
        inputs = [findings / "pairs.parquet", findings / "pages.parquet",
                  findings / "superworks_supersession.parquet",
                  findings.parent / "audit/issues.parquet"]
        for path in inputs:
            manifests.append({"path": str(path.resolve()),
                              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        pairs = pd.read_parquet(inputs[0])
        pages = {p.sheet_id: p for p in pd.read_parquet(inputs[1]).itertuples(index=False)}
        final = {p.pair_id: p for p in pairs.itertuples(index=False)}
        assert len(final) == len(pairs), f"Duplicate pair ids: {project}"
        replacements = set()
        for entry in pd.read_parquet(inputs[2]).itertuples(index=False):
            ledger_counts[entry.category] += 1
            old, news = decode(entry.old_pair), decode(entry.new_pairs) or []
            if old:
                replacements.update(p["pair_id"] for p in news)
            if entry.category in ("I", "J"):
                old_final = final.get(old["pair_id"])
                assert old_final is not None and old_final.status == "discard"
                assert any(final.get(p["pair_id"]) is not None
                           and final[p["pair_id"]].status == "pass" for p in news)
                retirement_checks[entry.category] += 1
        annotated = {}
        by_sheet = defaultdict(list)
        by_project = defaultdict(list)
        for pair in final.values():
            evidence = decode(pair.evidence) or {}
            has_sw = (evidence.get("source") == "superworks"
                      or (pair.pair_kind == "component_mapping"
                          and evidence.get("component_submode") == "superworks_connect_line_port")
                      or pair.pair_id in replacements
                      or any(k in evidence for k in SW_KEYS))
            annotated[pair.pair_id] = (evidence, has_sw)
            key = endpoint_key(pair)
            if has_sw and key:
                by_sheet[(pair.file_id, pair.sheet_id, key)].append(pair)
                by_project[key].append(pair)
            proof = evidence.get("sw_backplate_corroboration")
            if proof:
                partner = final.get(proof["sw_pair_id"])
                assert pair.status == "pass" and partner and partner.status == "pass"
                assert proof["match"] == "row+terminal+device"
                corroboration_checks["same_sheet" if proof["same_sheet"] else "other_sheet"] += 1
        local_rows = {}
        for pair in final.values():
            evidence, has_sw = annotated[pair.pair_id]
            key = endpoint_key(pair)
            peers = by_sheet.get((pair.file_id, pair.sheet_id, key), []) if key else []
            if has_sw:
                counterpart = "has_sw_evidence"
            elif any(p.status == "pass" for p in peers):
                counterpart = "same_sheet_sw_pass"
            elif peers:
                counterpart = "same_sheet_sw_nonpass"
            elif key and key in by_project:
                counterpart = "other_sheet_sw"
            else:
                counterpart = "no_literal_sw_counterpart"
            proof = evidence.get("sw_backplate_corroboration")
            partial = bool((evidence.get("superworks") or {}).get("partial"))
            source = ("backplate_row_corroborated" if proof else
                      "partial_sw" if partial else
                      "sw_produced_or_annotated" if has_sw else "pure_legacy")
            page = pages[pair.sheet_id]
            mapping = evidence.get("table_mapping") or {}
            row = {"project_id": project.name, "pair_id": pair.pair_id,
                   "file_id": pair.file_id, "sheet_id": pair.sheet_id,
                   "filename": page.filename, "sheet_no": page.sheet_no,
                   "status": pair.status, "pair_kind": pair.pair_kind,
                   "source": source, "counterpart": counterpart,
                   "left_value": clean(pair.left_value), "right_value": clean(pair.right_value),
                   "left_text_id": clean(pair.left_text_id), "right_text_id": clean(pair.right_text_id),
                   "line_group_id": clean(pair.line_group_id),
                   "confidence": pair.confidence, "confidence_bucket": pair.confidence_bucket,
                   "submode": mapping.get("mapping_mode") or evidence.get("component_submode") or evidence.get("semantic_kind") or "",
                   "route": page.route_target, "page_subtype": page.page_subtype,
                   "ordinary_pair_eligible": evidence.get("ordinary_pair_eligible"),
                   "sw_peer_ids": ",".join(sorted(p.pair_id for p in peers)),
                   "sw_peer_statuses": ",".join(sorted({p.status for p in peers})),
                   "rationale": pair.rationale}
            rows.append(row)
            local_rows[pair.pair_id] = row
        for issue in pd.read_parquet(inputs[3]).itertuples(index=False):
            primary = clean(issue.primary_pair_id) or clean(issue.pair_id)
            related = list(issue.related_pair_ids) if issue.related_pair_ids is not None else []
            members = set(related + ([primary] if primary else []))
            legacy = sorted(p for p in members if p in local_rows
                            and local_rows[p]["source"] == "pure_legacy")
            issues.append({"project_id": project.name, "issue_id": issue.issue_id,
                           "rule_id": issue.rule_id, "primary_pair_id": primary,
                           "primary_source": local_rows.get(primary, {}).get("source", "unlinked"),
                           "legacy_member_ids": ",".join(legacy), "message": issue.message})
    pure_pass = [r for r in rows if r["source"] == "pure_legacy" and r["status"] == "pass"]
    independent = [r for r in pure_pass if r["counterpart"] == "no_literal_sw_counterpart"]
    summary = {
        "run": str(args.run.resolve()), "projects": len({r["project_id"] for r in rows}),
        "pairs": len(rows), "status_counts": counts(rows, "status"),
        "source_by_status": dict(sorted(Counter(f'{r["source"]}|{r["status"]}' for r in rows).items())),
        "ledger_categories": dict(sorted(ledger_counts.items())),
        "verified_retired_with_surviving_pass_partner": dict(retirement_checks),
        "verified_backplate_corroboration": dict(corroboration_checks),
        "pure_legacy_pass": len(pure_pass), "pure_pass_counterpart": counts(pure_pass, "counterpart"),
        "no_literal_sw_counterpart_pass": len(independent),
        "independent_by_kind": counts(independent, "pair_kind"),
        "independent_by_submode": counts(independent, "submode"),
        "independent_by_project": counts(independent, "project_id"),
        "issues": len(issues), "issue_rules": counts(issues, "rule_id"),
        "issue_primary_source": counts(issues, "primary_source"),
        "issues_with_legacy_members": sum(bool(i["legacy_member_ids"]) for i in issues),
        "limitations": ["Literal unordered value matching is not electrical equivalence.",
                        "SW evidence includes partial annotations and row-only backplate corroboration.",
                        "No production downgrade or counterfactual audit/coverage replay was performed."]}
    assert sum(summary["status_counts"].values()) == len(rows)
    assert sum(summary["pure_pass_counterpart"].values()) == len(pure_pass)
    assert sum(summary["independent_by_kind"].values()) == len(independent)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, values in (("pure_legacy_pass", pure_pass), ("independent_pass", independent),
                         ("issue_dependencies", issues)):
        pd.DataFrame(values).to_csv(args.out / f"{name}.csv", index=False, encoding="utf-8-sig")
    (args.out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.out / "input_manifest.json").write_text(json.dumps(manifests, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
