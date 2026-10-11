"""LOGGEN-MISMATCH step 1 (read-only): compare every resolved SuperWORKS port identity with the drawn text around it.

Usage: python build_ends.py <round14_dir> <out_dir>

Inputs are only the replay products <round14_dir>/pNNN/*/findings/*.parquet (sw_wire_routes, sw_ports,
sw_part_instances, texts, sw_connect_labels, text_assignments). Writes ends.pkl (one row per unique resolved port),
wire_checks.pkl (connect-label destination vs far end, two-ended records) and stats.json.

Verdict of one port identity I (own drawn texts only; connect labels and cross-reference texts beginning with
'*' or '&' are excluded; R_NEAR = 12, R_WIDE = 30 page units):
  agree_exact              a text within R_WIDE equals I (spaces removed)
  agree_format             equal once hyphens, '&', '_', '.' are ignored
  agree_composed_pin       I = label + one drawn pin text; the label is on the sheet (also as a part ending in a
                           letter or hyphen, e.g. K861-1X in K861-1X4)
  agree_segmented          I = label + pin made of several drawn pieces (C13 = header 'C' + row '13')
  agree_*_contact_suffix   as above with a trailing contact index (-1, -2 ...) removed
  agree_group_header_left  terminal-strip group header left of the port (COM3 + cell 5 for COM3-5)
  agree_row_partial        backplate only: label on the sheet and the row text (last two digits) near the port
  unrelated_text_nearby    the nearest identity-like own text is not similar to I
  connect_only_differs     no own text; only connect-label destinations are near, and they differ from I
  connect_only_agree       no own text; a connect label equals I
  unverifiable             no drawn text within R_WIDE
  disagree_<shape>         an own identity-like text is similar to I and differs (none remain in the final run)
slot_check (backplate 3-digit numbers) records the header digit and the copy-rank of the row text as evidence.
"""
from __future__ import annotations

import difflib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

R_NEAR = 12.0
R_WIDE = 30.0
BACKPLATE_PAGE = "背板表格型图"
IDENT_LIKE = re.compile(r"(?=.*\d)(?=.*[A-Za-z\-])")
ROUND_GLOB = "p*"


def strict(s) -> str:
    return re.sub(r"\s+", "", str(s or "")).casefold()


def loose(s) -> str:
    return re.sub(r"[\s&_.\-]+", "", str(s or "")).casefold()


def split_digits(s: str) -> tuple[str, str]:
    m = re.fullmatch(r"(.*?)(\d+)", s or "")
    return (m[1], m[2]) if m else (s or "", "")


def shape(identity: str, drawn: str) -> str:
    """How the drawn text differs from the identity (identity = I, drawn = C)."""
    i, c = strict(identity), strict(drawn)
    if loose(i) == loose(c):
        return "format_only"
    pi, di = split_digits(i)
    pc, dc = split_digits(c)
    if di and dc and pi.rstrip("-") == pc.rstrip("-"):
        if len(di) == len(dc) == 3 and di[1:] == dc[1:] and di[0] != dc[0]:
            return "slot_digit"
        if di[-2:] != dc[-2:]:
            return "row_digits"
        return "port_number_other"
    if di and di == dc:
        return "format_only" if loose(pi) == loose(pc) else "prefix_differs"
    return "prefix_and_port"


def classify_class(category: str, kind: str, backplate: bool) -> str:
    if backplate:
        return "背板端口"
    if category in ("端子", "装置端子"):
        return category
    if kind == "part" or category == "内部元件":
        return "内部元件"
    return "其他"


def label_pin_splits_any(identity: str):
    """(label, pin) splits with a non-empty label and a non-empty pin; a one-character label must be a drawn text itself."""
    out = []
    for k in range(1, len(identity)):
        label = identity[:k].rstrip("-")
        pin = identity[k:].lstrip("-")
        if label and pin:
            out.append((label, pin))
    return out


def label_pin_splits(identity: str):
    """(label, pin) splits where the pin is all digits."""
    out = []
    for k in range(1, len(identity)):
        label = identity[:k].rstrip("-")
        pin = identity[k:].lstrip("-")
        if label and pin.isdigit():
            out.append((label, pin))
    return out


XREF_PREFIX = ("*", "&")


class FileTexts:
    def __init__(self, frame: pd.DataFrame, connect_ids: set[str]):
        self.handles = frame["handle"].fillna("").astype(str).tolist()
        self.values = frame["value"].tolist()
        self.strict_values = {strict(v) for v in self.values}
        # One string of all sheet texts: substring test for a label written inside a longer text (K861-1X in K861-1X4).
        self.joined = chr(10).join(strict(v) for v in self.values)
        self.joined_loose = chr(10).join(loose(v) for v in self.values)
        self.loose_values = {loose(v) for v in self.values}
        self.is_xref = np.array([str(v).startswith(XREF_PREFIX) for v in self.values], dtype=bool)
        self.cx = frame["cx"].to_numpy(dtype=float)
        self.cy = frame["cy"].to_numpy(dtype=float)
        self.is_connect = frame["text_id"].isin(connect_ids).to_numpy()
        self.text_id = frame["text_id"].tolist()

    def near(self, x: float, y: float, radius: float):
        d = np.hypot(self.cx - x, self.cy - y)
        idx = np.nonzero(d <= radius)[0]
        return [(i, float(d[i])) for i in idx]


def label_on_sheet(label: str, texts: "FileTexts") -> bool:
    """A label is a drawn text, or a part of one ending at a letter or hyphen (K861-1X in K861-1X4). A part ending
    in a digit (3-21n5 in 3-21n532) is not accepted: the digit belongs to the pin."""
    key = loose(label)  # hyphens and spaces are formatting only (K8611X vs K861-1X)
    if not key:
        return False
    if key in texts.loose_values:
        return True
    return len(key) >= 2 and not key[-1].isdigit() and key in texts.joined_loose


def segment(text: str, pieces: set[str]):
    """Split text into consecutive pieces each equal to a drawn text (fewest pieces first); None if impossible."""
    n = len(text)
    if not n:
        return None
    best = [None] * (n + 1)
    best[0] = []
    for end in range(1, n + 1):
        for start in range(max(0, end - 12), end):
            if best[start] is None:
                continue
            piece = text[start:end]
            if piece in pieces:
                cand = best[start] + [piece]
                if best[end] is None or len(cand) < len(best[end]):
                    best[end] = cand
    return best[n] if best[n] is not None and len(best[n]) <= 4 else None


def group_header_left(identity: str, texts: FileTexts, wide: list, near_set: set, px: float, py: float):
    """Terminal strips print a group header (COM3) left of its cells, one cell digit per terminal (COM3-5).
    Accept when a header text equal to a prefix group of the identity sits left of the port on the same row band
    (<= 40 units, DXF x grows to the right) and the remaining piece is a drawn text near the port."""
    s_id = strict(identity)
    for i, _ in wide:
        if texts.is_connect[i] or texts.is_xref[i]:
            continue
        v = strict(texts.values[i])
        k = s_id.find(v) if v else -1
        if k <= 0 or v == s_id or not (px - 40 <= texts.cx[i] <= px):
            continue
        if abs(texts.cy[i] - py) > 5.0:  # the wire end sits a few units above the cell row (COM3 row at y 199.4, port at 202.9)
            continue
        rest = s_id[k + len(v):].lstrip("-")
        if rest and rest.replace("-", "") in near_set and len(rest) <= 3:
            return {"header": texts.values[i], "header_dx": round(px - texts.cx[i], 2), "cell": rest}
    return None


def verdict(identity: str, texts: FileTexts, backplate: bool, wide: list, near: list, px=None, py=None):
    """Return (verdict, detail dict) using own texts only; connect labels are handled separately.
    wide / near: (index, distance) lists within R_WIDE / R_NEAR of the port contact."""
    own_wide = [(texts.values[i], d) for i, d in wide if not texts.is_connect[i] and not texts.is_xref[i]]
    own_near = [(texts.values[i], d) for i, d in near if not texts.is_connect[i] and not texts.is_xref[i]]
    numeric_near = [(v, d) for v, d in own_near if re.fullmatch(r"\d{1,4}", strict(v))]
    s_id = strict(identity)
    for v, d in sorted(own_wide, key=lambda x: x[1]):
        if strict(v) == s_id:
            return "agree_exact", {"text": v, "dist": round(d, 2)}
    for v, d in sorted(own_wide, key=lambda x: x[1]):
        if loose(v) == loose(identity):
            return "agree_format", {"text": v, "dist": round(d, 2)}
    # Composed identity = sheet label + pin. The pin may be one drawn text (1X4 -> "1X4") or several
    # drawn pieces side by side (C13 -> header "C" + row "13"; 1X2 -> "1X" + "2"; COM4-A -> "COM4" + "A").
    near_set = {strict(v) for v, _ in own_near}
    variants = [(identity, "")]
    contact = re.fullmatch(r"(.+?)(-\d+)", identity)
    if contact:
        variants.append((contact[1], "contact_suffix"))
    near_set_nodash = {v.replace("-", "") for v in near_set}
    for base, suffix in variants:
        for label_text, pin_text in label_pin_splits_any(base):
            if not label_on_sheet(label_text, texts):
                continue
            pieces = segment(strict(pin_text).replace("-", ""), near_set_nodash)
            if not pieces:
                continue
            kind = "agree_composed_pin" if len(pieces) == 1 else "agree_segmented"
            if suffix:
                kind += "_" + suffix
            return kind, {"label": label_text, "pin": pin_text, "pieces": pieces}
    for label, pin in label_pin_splits(identity):
        if strict(label) not in texts.strict_values or len(pin) < 2:
            continue
        for v, d in numeric_near:
            if strict(v) == pin[-2:]:
                return "agree_row_partial", {"label": label, "row_text": v, "dist": round(d, 2)}
    # The nearest identity-like own text decides; a farther one may be a neighbouring terminal's text.
    if px is not None:
        header = group_header_left(identity, texts, wide, near_set, px, py)
        if header:
            return "agree_group_header_left", header
    cands = sorted((d, v) for v, d in own_near if IDENT_LIKE.search(strict(v)) and strict(v) != s_id)
    if cands:
        d, best = cands[0]
        if difflib.SequenceMatcher(None, strict(best), s_id).ratio() >= 0.5:
            return "disagree_" + shape(identity, best), {"drawn": best, "dist": round(d, 2)}
        return "unrelated_text_nearby", {"drawn": best, "dist": round(d, 2)}
    if backplate and label_pin_splits(identity):
        label, pin = label_pin_splits(identity)[0]
        two = [v for v, _ in numeric_near if len(strict(v)) == 2]
        if two and label in texts.strict_values and not any(strict(v) == pin[-2:] for v in two):
            return "disagree_row_digits", {"label": label, "row_texts": sorted(set(two))}
    connect = [(texts.values[i], d) for i, d in near if texts.is_connect[i]]
    if connect:
        if any(strict(v) == s_id for v, _ in connect):
            return "connect_only_agree", {"connect": [v for v, _ in connect][:3]}
        return "connect_only_differs", {"connect": [v for v, _ in connect][:3]}
    return "unverifiable", {}


def slot_check(number: str, texts: FileTexts, x: float, y: float):
    """Evidence for the first digit of a 3-digit backplate number (group/slot digit).
    header: a single digit 1-9 printed in the same column (|dx| <= 2.5, |dy| <= 12) as the row text.
    rank:   left-to-right rank of the row text among same-row copies on the sheet (one copy per slot)."""
    if len(number) != 3 or not number.isdigit():
        return None
    row = number[1:]
    rows = [(i, d) for i, d in texts.near(x, y, R_NEAR) if strict(texts.values[i]) == row]
    if not rows:
        return {"row_text": False}
    i, _ = min(rows, key=lambda t: t[1])
    cx0, cy0 = texts.cx[i], texts.cy[i]
    digit = int(number[0])
    values = np.array([strict(v) for v in texts.values])
    column = (np.abs(texts.cx - cx0) <= 2.5) & (np.abs(texts.cy - cy0) <= 12) & (np.abs(texts.cy - cy0) > 0.5)
    heads = [j for j in np.nonzero(column)[0] if re.fullmatch(r"[1-9]", values[j])]
    header = None
    if heads:
        j = min(heads, key=lambda j: abs(texts.cy[j] - cy0))
        header = int(values[j])
    # copies of one backplate instance: texts whose handle is "<insert>:VIRTUAL:<n>" for the same insert
    insert = texts.handles[i].split(":")[0] if ":" in texts.handles[i] else None
    same_insert = np.array([insert is not None and h.startswith(insert + ":") for h in texts.handles])
    same = np.nonzero((values == row) & (np.abs(texts.cy - cy0) < 0.5) & same_insert)[0]
    copies = sorted(same, key=lambda j: texts.cx[j])
    rank = copies.index(i) + 1 if i in copies else None
    return {"row_text": True, "digit": digit, "header_digit": header,
            "header_match": None if header is None else header == digit,
            "copies": len(copies), "rank": rank,
            "rank_match": None if rank is None or len(copies) < 2 else rank == digit}


def load(fdir: Path):
    wr = pd.read_parquet(fdir / "sw_wire_routes.parquet", columns=["record_id", "source_kind", "wire_handle", "ends_json"])
    sp = pd.read_parquet(fdir / "sw_ports.parquet", columns=["record_id", "file_id", "insert_handle", "port_number", "category",
                                                           "start_x", "start_y", "end_x", "end_y", "endpoint_identity"])
    spi = pd.read_parquet(fdir / "sw_part_instances.parquet", columns=["file_id", "insert_handle", "block_name", "part_type", "ports"])
    tx = pd.read_parquet(fdir / "texts.parquet", columns=["text_id", "file_id", "handle", "text", "normalized_text",
                                                        "bbox_min_x", "bbox_min_y", "bbox_max_x", "bbox_max_y", "insert_x", "insert_y"])
    cl = pd.read_parquet(fdir / "sw_connect_labels.parquet", columns=["record_id", "file_id", "text", "line_handle", "part_id",
                                                                    "port_number", "endpoint_identity"])
    ta = pd.read_parquet(fdir / "text_assignments.parquet", columns=["file_id", "page_type"]).drop_duplicates("file_id")
    return wr, sp, spi, tx, cl, dict(zip(ta.file_id, ta.page_type))


def connect_text_ids(cl: pd.DataFrame) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for row in cl.itertuples():
        try:
            tj = json.loads(row.text)
        except (TypeError, ValueError):
            continue
        if tj.get("text_id"):
            out[row.file_id].add(tj["text_id"])
    return out


def build_ports(sp: pd.DataFrame, spi: pd.DataFrame) -> dict:
    ports = {}
    for r in sp.itertuples():
        ports[r.record_id] = {"kind": "sw", "file_id": r.file_id, "category": r.category or "", "insert": str(r.insert_handle),
                              "number": str(r.port_number), "x": (float(r.start_x) + float(r.end_x)) / 2,
                              "y": (float(r.start_y) + float(r.end_y)) / 2, "identity": r.endpoint_identity,
                              "block": None, "part_type": None}
    for r in spi.itertuples():
        plist = json.loads(r.ports) if isinstance(r.ports, str) else (r.ports or [])
        for p in plist:
            rid = p.get("record_id")
            if not rid or p.get("start_x") is None:
                continue
            ports[rid] = {"kind": "part", "file_id": r.file_id, "category": "", "insert": str(r.insert_handle),
                          "number": str(p.get("port_number")), "x": (float(p["start_x"]) + float(p["end_x"])) / 2,
                          "y": (float(p["start_y"]) + float(p["end_y"])) / 2, "identity": p.get("endpoint_identity"),
                          "block": r.block_name, "part_type": r.part_type}
    return ports


def process_project(pid: str, fdir: Path):
    wr, sp, spi, tx, cl, page_types = load(fdir)
    ports = build_ports(sp, spi)
    conn = connect_text_ids(cl)
    tx = tx.copy()
    tx["value"] = tx["normalized_text"].where(tx["normalized_text"].notna() & (tx["normalized_text"] != ""), tx["text"]).fillna("").astype(str)
    tx["cx"] = (tx["bbox_min_x"] + tx["bbox_max_x"]) / 2
    tx["cy"] = (tx["bbox_min_y"] + tx["bbox_max_y"]) / 2
    files = {}
    for fid, frame in tx.groupby("file_id"):
        frame = frame[frame["value"].str.len() > 0].reset_index(drop=True)
        files[fid] = FileTexts(frame, conn.get(fid, set()))

    # Resolved sw_port ends, unique per port.
    unique: dict[str, dict] = {}
    records_per_port: Counter = Counter()
    ident_per_port: dict[str, set] = defaultdict(set)
    end_rows = []
    for r in wr.itertuples():
        for index, e in enumerate(json.loads(r.ends_json)):
            if e.get("status") != "resolved" or e.get("identity_source") != "sw_port":
                continue
            pids = e.get("port_ids") or []
            if not pids:
                continue
            pid_key = pids[0]
            ident_per_port[pid_key].add(e.get("identity"))
            records_per_port[pid_key] += 1
            if pid_key not in unique:
                unique[pid_key] = {"port_id": pid_key, "identity": e.get("identity"), "role": e.get("role"),
                                   "end_index": index, "record_id": r.record_id, "wire_handle": r.wire_handle,
                                   "source_kind": r.source_kind, "file_id_end": e.get("file_id")}
    rows = []
    for pk, info in unique.items():
        port = ports.get(pk)
        if port is None:
            rows.append({**info, "project": pid, "file_id": None, "geometry": False})
            continue
        fid = port["file_id"]
        ft = files.get(fid)
        backplate = page_types.get(fid) == BACKPLATE_PAGE
        cls = classify_class(port["category"], port["kind"], backplate)
        row = {**info, "project": pid, "file_id": fid, "geometry": True, "port_kind": port["kind"],
               "category": port["category"], "end_class": cls, "backplate": backplate, "page_type": page_types.get(fid),
               "insert": port["insert"], "number": port["number"], "block": port["block"], "part_type": port["part_type"],
               "x": port["x"], "y": port["y"], "records": records_per_port[pk],
               "identity_conflict": len(ident_per_port[pk]) > 1}
        if ft is None:
            row.update(verdict="unverifiable", detail={})
        else:
            wide = ft.near(port["x"], port["y"], R_WIDE)
            near = [(i, d) for i, d in wide if d <= R_NEAR]
            v, detail = verdict(info["identity"], ft, backplate, wide, near, port["x"], port["y"])
            row.update(verdict=v, detail=detail)
            if backplate:
                row["slot"] = slot_check(port["number"], ft, port["x"], port["y"])
            conn_near = [ft.values[i] for i, d in near if ft.is_connect[i]]
            row["connect_near"] = conn_near[:4]
        rows.append(row)
    ends = pd.DataFrame(rows)
    return ends, files, ports, cl, wr


def wire_destination_checks(pid, wr, cl):
    """Connect-label destination on each two-ended record vs the other end's identity / far text."""
    labels = []
    for row in cl.itertuples():
        if not row.line_handle:
            continue
        try:
            value = json.loads(row.text).get("value", "")
        except (TypeError, ValueError):
            value = ""
        labels.append({"file_id": row.file_id, "line": str(row.line_handle), "value": value,
                       "part_id": row.part_id, "port_number": str(row.port_number) if row.port_number is not None else None,
                       "endpoint_identity": row.endpoint_identity})
    by_line = defaultdict(list)
    for lab in labels:
        by_line[(lab["file_id"], lab["line"])].append(lab)
    out = []
    for r in wr.itertuples():
        ends = json.loads(r.ends_json)
        resolved = [e for e in ends if e.get("status") in ("resolved", "resolved_by_text")]
        if len(ends) != 2 or len(resolved) != 2 or not r.wire_handle:
            continue
        wire = str(r.wire_handle)
        for e_local, e_far in ((ends[0], ends[1]), (ends[1], ends[0])):
            file_id = e_local.get("file_id")
            if not file_id:
                continue
            for lab in by_line.get((file_id, wire), []):
                local_port = lab["port_number"]
                th = str(e_local.get("terminal_handle") or "")
                part_ok = bool(th) and str(lab["part_id"] or "").endswith("/" + th)
                if not part_ok or local_port is None or str(e_local.get("port_number")) != local_port:
                    continue
                dest_parts = [p.strip().strip("&").strip() for p in re.split(r"[,，]", lab["value"]) if p.strip().strip("&").strip()]
                far_id = e_far.get("identity")
                far_text = e_far.get("far_text_identity")
                for dest in dest_parts:
                    if strict(dest) == strict(far_id):
                        verdict = "dest_eq_far_identity"
                    elif far_id and loose(dest) == loose(far_id):
                        verdict = "dest_format_far_identity"
                    elif far_text and strict(dest) == strict(far_text):
                        verdict = "dest_eq_far_text_only"
                    elif far_text and loose(dest) == loose(far_text):
                        verdict = "dest_format_far_text_only"
                    else:
                        verdict = "dest_differs"
                    out.append({"project": pid, "record_id": r.record_id, "source_kind": r.source_kind, "wire": wire,
                                "file_id": file_id, "local_port_number": local_port, "local_identity": e_local.get("identity"),
                                "dest": dest, "far_identity": far_id, "far_text": far_text,
                                "far_status": e_far.get("status"), "far_source": e_far.get("far_source"), "verdict": verdict})
    return out


def main(round_dir: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    all_ends, all_wire = [], []
    stats = {"projects": 0, "projects_without_routes": [], "per_project": {}}
    for pdir in sorted(round_dir.glob(ROUND_GLOB)):
        if not pdir.is_dir():
            continue
        fdir = next((c for c in pdir.glob("*/findings") if (c / "sw_wire_routes.parquet").exists()), None)
        if fdir is None:
            stats["projects_without_routes"].append(pdir.name)
            continue
        ends, files, ports, cl, wr = process_project(pdir.name, fdir)
        all_ends.append(ends)
        all_wire.extend(wire_destination_checks(pdir.name, wr, cl))
        stats["projects"] += 1
        stats["per_project"][pdir.name] = int(len(ends))
        print(pdir.name, len(ends), flush=True)
    ends = pd.concat(all_ends, ignore_index=True)
    ends.to_pickle(out_dir / "ends.pkl")
    pd.DataFrame(all_wire).to_pickle(out_dir / "wire_checks.pkl")
    stats["end_rows"] = int(len(ends))
    stats["wire_check_rows"] = len(all_wire)
    (out_dir / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
