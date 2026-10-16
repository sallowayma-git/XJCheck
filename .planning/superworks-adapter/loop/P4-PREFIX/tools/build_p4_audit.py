"""Build a reproducible screenshot sample for P4 fixed-fact normalizations.

The input is the 77-project P4 event extract in .tmp. The script only reads
the extract, corpus manifest, and frozen DXFs; it writes sample evidence under
.tmp/precision_loop_20261015/P4-PREFIX.
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
import re
from collections import Counter
from pathlib import Path

import ezdxf
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle
from ezdxf.addons.drawing import Frontend
from ezdxf.addons.drawing.config import ColorPolicy, Configuration
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
from ezdxf.addons.drawing.properties import RenderContext


ROOT = Path(__file__).resolve().parents[5]
EVENTS = ROOT / ".tmp/precision_loop_20261015/p4_events.json"
MANIFEST = ROOT / ".planning/superworks-adapter/corpus_manifest.json"
OUT = ROOT / ".tmp/precision_loop_20261015/P4-PREFIX-v2"
SEED = 20261016
SAMPLE_PER_LARGE_FORMAT = 30
ROWS_PER_IMAGE = 4


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def format_class(value: str) -> str:
    if re.fullmatch(r"\d+-\d+n\d+", value, re.IGNORECASE):
        return "section-n-number"
    if re.fullmatch(r"\d+n\d+", value, re.IGNORECASE):
        return "n-number"
    if re.fullmatch(r"[A-Za-z]+\d+-\d+", value):
        return "alpha-num-hyphen-num"
    if re.fullmatch(r"[A-Za-z]+\d+", value):
        return "alpha-num"
    return "other"


def sample_distinct_sources(review_events, size, files, rng):
    by_source = {}
    for event in review_events:
        source_hash = files[(event["pid"], event["file"])]["sha256"]
        by_source.setdefault(source_hash, []).append(event)
    chosen_hashes = rng.sample(sorted(by_source), size)
    return [rng.choice(by_source[source_hash]) for source_hash in chosen_hashes]


def build_sample(events, files):
    by_class = {}
    for event in events:
        cls = format_class(event["after"])
        by_class.setdefault(cls, []).append(event)

    rng = random.Random(SEED)
    selected = []
    design = {}
    for cls in ("n-number", "section-n-number"):
        group = by_class[cls]
        passes = [e for e in group if e["status"] == "pass"]
        reviews = [e for e in group if e["status"] != "pass"]
        sample = sample_distinct_sources(reviews, SAMPLE_PER_LARGE_FORMAT, files, rng)
        selected.extend((cls, e, "seeded_random_distinct_source_sample") for e in sample)
        selected.extend((cls, e, "all_pass_pairs") for e in passes)
        design[cls] = {
            "population": len(group),
            "review_population": len(reviews),
            "review_sample": len(sample),
            "unique_review_source_population": len({files[(e["pid"], e["file"])]["sha256"] for e in reviews}),
            "unique_review_sources_sampled": len({files[(e["pid"], e["file"])]["sha256"] for e in sample}),
            "pass_population_and_sample": len(passes),
            "method": "one seeded random review event from each sampled unique source DWG; all pass events included",
        }

    for cls in ("alpha-num-hyphen-num", "alpha-num"):
        group = by_class[cls]
        selected.extend((cls, e, "census_rare_format") for e in group)
        design[cls] = {
            "population": len(group),
            "sample": len(group),
            "method": "census of the format class",
        }

    # Wire-component rows are a distinct evidence path and contain all six
    # pass cases. Add one review event from every unique source DWG in this
    # path, even when the format sample already covers that source.
    wire_reviews = [e for e in events
                    if e["kind"] == "wire_component_mapping" and e["status"] != "pass"]
    wire_by_format = {}
    for event in wire_reviews:
        wire_by_format.setdefault(format_class(event["after"]), []).append(event)
    wire_source_counts = {}
    for cls, group in wire_by_format.items():
        by_source = {}
        for event in group:
            source_hash = files[(event["pid"], event["file"])]["sha256"]
            by_source.setdefault(source_hash, []).append(event)
        for source_hash in sorted(by_source):
            selected.append((cls, rng.choice(by_source[source_hash]), "wire_review_source_census"))
        wire_source_counts[cls] = {
            "wire_review_population": len(group),
            "unique_source_dwgs": len(by_source),
            "sampled_source_dwgs": len(by_source),
        }
    design["wire_component_review_by_format"] = wire_source_counts

    # Do not judge a duplicated project copy of the same source pair twice.
    # Keep the first source-hash/pair representation and retain all project IDs.
    dedup = {}
    for cls, event, reason in selected:
        source = files[(event["pid"], event["file"])]
        key = (source["sha256"], event["file"], event["sheet"], event["pair_id"],
               event["side"], event["before"], event["after"], event["kind"], event["status"])
        if key not in dedup:
            dedup[key] = [cls, event, reason, [event["pid"]]]
        else:
            dedup[key][3].append(event["pid"])
            if reason == "all_pass_pairs":
                dedup[key][2] = reason

    rows = []
    for number, (cls, event, reason, represented_projects) in enumerate(
        sorted(dedup.values(), key=lambda row: (row[0], row[1]["pid"], row[1]["file"], row[1]["pair_id"])),
        start=1,
    ):
        source = files[(event["pid"], event["file"])]
        dxf = Path(source["dxf_path"])
        if not dxf.is_file():
            raise FileNotFoundError(f"frozen DXF missing for {event['pid']}/{event['file']}: {dxf}")
        actual_hash = hashlib.sha256(dxf.read_bytes()).hexdigest()
        if actual_hash != source["dxf_sha256"]:
            raise RuntimeError(f"frozen DXF hash mismatch: {event['pid']}/{event['file']}")

        evidence = event["evidence"]
        side = event["side"]
        sw_side = evidence["superworks"][side]
        normalization = next(
            x for x in evidence["fixed_fact_normalizations"] if x["side"] == side
        )
        port_ids = set(normalization.get("port_ids", []))
        port = next((p for p in sw_side.get("ports", []) if p["port_id"] in port_ids), None)
        if port is None:
            raise RuntimeError(f"matching SW port missing: {event['pid']}/{event['pair_id']}")

        rows.append({
            "case_no": number,
            "format_class": cls,
            "selection_reason": reason,
            "seed": SEED,
            "pid": event["pid"],
            "represented_projects": sorted(set(represented_projects)),
            "file_id": event["file"],
            "sheet_id": event["sheet"],
            "pair_id": event["pair_id"],
            "pair_kind": event["kind"],
            "status": event["status"],
            "recognition_state": evidence.get("recognition_state"),
            "side": side,
            "before": event["before"],
            "after": event["after"],
            "source_dwg_sha256": source["sha256"],
            "source_dxf_sha256": source["dxf_sha256"],
            "dxf_path": str(dxf),
            "line_start": evidence["line_start"],
            "line_end": evidence["line_end"],
            "pair_left_raw": evidence.get("selected_left_raw_text"),
            "pair_right_raw": evidence.get("selected_right_raw_text"),
            "sw_identity": sw_side.get("value"),
            "sw_port_id": port["port_id"],
            "sw_port_start": port["start"],
            "sw_port_end": port["end"],
            "sw_port_validation": port.get("validation", {}),
            "screenshot": None,
            "row_in_screenshot": None,
            "identity_judgement": "",
            "identity_manual_review_needed": "",
            "pair_manual_review_needed": "",
            "identity_reason": "",
            "pair_reason": "",
        })
    return rows, design


def center_of(port_start, port_end):
    return [(port_start[0] + port_end[0]) / 2, (port_start[1] + port_end[1]) / 2]


def draw_panel(ax, row, doc, zoom_port: bool):
    config = Configuration.defaults().with_changes(color_policy=ColorPolicy.COLOR_SWAP_BW)
    Frontend(RenderContext(doc), MatplotlibBackend(ax), config=config).draw_layout(
        doc.modelspace(), finalize=False
    )
    line_a, line_b = row["line_start"], row["line_end"]
    port_center = center_of(row["sw_port_start"], row["sw_port_end"])
    selected_endpoint = line_a if row["side"] == "left" else line_b

    if zoom_port:
        half = 12.0
        x0, x1 = port_center[0] - half, port_center[0] + half
        y0, y1 = port_center[1] - half, port_center[1] + half
        ax.add_patch(Rectangle((port_center[0] - 0.8, port_center[1] - 0.8), 1.6, 1.6,
                               fill=False, ec="#16852c", lw=1.8, zorder=55))
        ax.text(port_center[0] + 1.2, port_center[1] + 1.0,
                "SW " + str(row["after"]), color="#16852c", fontsize=8, zorder=60)
        title = "SW identity port (green square)"
    else:
        coords = [line_a, line_b, port_center]
        pad = 10.0
        x0 = min(p[0] for p in coords) - pad
        x1 = max(p[0] for p in coords) + pad
        y0 = min(p[1] for p in coords) - pad
        y1 = max(p[1] for p in coords) + pad
        ax.add_patch(Circle(tuple(selected_endpoint), 1.0, fill=False,
                            ec="#1452cc", lw=1.8, zorder=55))
        ax.text(selected_endpoint[0] + 1.4, selected_endpoint[1] + 1.0,
                "V1 " + str(row["before"]), color="#1452cc", fontsize=8, zorder=60)
        ax.add_patch(Rectangle((port_center[0] - 0.8, port_center[1] - 0.8), 1.6, 1.6,
                               fill=False, ec="#16852c", lw=1.8, zorder=55))
        ax.text(port_center[0] + 1.2, port_center[1] - 1.8,
                "SW " + str(row["after"]), color="#16852c", fontsize=8, zorder=60)
        title = "Pair wire and normalized endpoint"

    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(title, fontsize=8)


def render(rows):
    OUT.mkdir(parents=True, exist_ok=True)
    docs = {}
    for start in range(0, len(rows), ROWS_PER_IMAGE):
        group = rows[start:start + ROWS_PER_IMAGE]
        image_name = f"P4_{group[0]['case_no']:04d}_{group[-1]['case_no']:04d}.png"
        fig, axes = plt.subplots(len(group), 2, figsize=(13, 4.1 * len(group)), dpi=115)
        if len(group) == 1:
            axes = [axes]
        for index, row in enumerate(group):
            dxf = row["dxf_path"]
            if dxf not in docs:
                try:
                    docs[dxf] = ezdxf.readfile(dxf)
                except Exception:
                    docs[dxf] = ezdxf.recover.readfile(dxf)[0]
            draw_panel(axes[index][0], row, docs[dxf], zoom_port=False)
            draw_panel(axes[index][1], row, docs[dxf], zoom_port=True)
            title = (
                f"#{row['case_no']:04d} {row['format_class']} | {row['pid']} "
                f"{row['file_id']}/{row['sheet_id']} {row['pair_id']} | "
                f"{row['pair_kind']} {row['status']} | {row['side']} "
                f"{row['before']} -> {row['after']} | "
                f"pair: {row['pair_left_raw']} -> {row['pair_right_raw']}"
            )
            fig.text(0.012, 1 - (index + 0.07) / len(group), title,
                     fontsize=8.2, va="top", ha="left")
            row["screenshot"] = image_name
            row["row_in_screenshot"] = index + 1
        fig.subplots_adjust(left=0.015, right=0.985, top=0.985, bottom=0.01,
                            hspace=0.40, wspace=0.10)
        fig.savefig(OUT / image_name, dpi=115)
        plt.close(fig)
        print(f"wrote {image_name}", flush=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    events = read_json(EVENTS)
    manifest = read_json(MANIFEST)
    files = {(p["project_id"], f["file_id"]): f
             for p in manifest["projects"] for f in p["files"]}
    rows, design = build_sample(events, files)
    render(rows)
    (OUT / "sample.json").write_text(
        json.dumps({"seed": SEED, "design": design, "sample": rows},
                   ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with (OUT / "judgements.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        fields = ["case_no", "format_class", "selection_reason", "pid", "file_id",
                  "sheet_id", "pair_id", "pair_kind", "status", "recognition_state", "side", "before",
                  "after", "source_dwg_sha256", "source_dxf_sha256", "screenshot",
                  "row_in_screenshot", "identity_judgement", "identity_manual_review_needed",
                  "pair_manual_review_needed", "identity_reason", "pair_reason"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in fields} for row in rows)

    print(json.dumps({"sample_size": len(rows),
                      "classes": dict(Counter(row["format_class"] for row in rows)),
                      "unique_source_dwgs": len({row["source_dwg_sha256"] for row in rows}),
                      "out": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
