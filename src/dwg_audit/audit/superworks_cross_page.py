"""Cross-page continuity of SuperWORKS terminal-strip rows (X2).

A terminal-strip row can carry a destination text ``未定义<handle>:<port>_<page no> <page name>``: its wire
leaves this page at that row and continues on page ``<page no>``, where the device port ``<handle>:<port>``
sits. The row's own connection texts name the same far end, and a non-discard pair already records that
connection on this page. The target port is therefore the far end of a connection that is already drawn
here. It is not a new wire, so this module never creates a Pair: it records a *continuity link* and reports
it as coverage. Pairs, and every rule that reads them, are unchanged.

Two relations are accepted, both requiring the row to carry a non-discard pair on one of its connections
(the connection is represented on this page):

- ``continuity_conn``: the target identity equals a far value the row names (a connection text, or the
  other side of a pair on that connection).
- ``continuity_row``: the target identity equals the row's own identity, i.e. the same terminal name drawn
  on the target page.

A target covered by a link counts as consumed for coverage only when it is otherwise unconsumed and has a
wire contact. Identities are compared exactly (casefold), never by prefix, so a continuity claim needs the
same identity text on both sides.

Targets that disagree with the row are reported, never made issues here:

- ``contradiction_candidate``: the target is consumed by a non-discard pair whose other end is neither the
  row identity nor a far value of the row: this page says the wire goes to A, the page it names carries B on
  that port.
- ``identity_mismatch_unconsumed``: the target is free and its identity differs from every far value.

Target resolution needs the page number. Handles are per drawing and copied drawings reuse them, so a handle
that exists only on a different page is a stale reference and is not linked.
"""
from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict

TERMINAL_CATEGORIES = frozenset({"端子", "装置端子"})
RELATION_CONN = "continuity_conn"
RELATION_ROW = "continuity_row"
CANDIDATE_CONSUMED = "contradiction_candidate"
CANDIDATE_FREE = "identity_mismatch_unconsumed"
_PAGE_NUMBER = re.compile(r"\s*(\d+)")
_VALUE_SEPARATOR = re.compile(r"[,，;；]")


def _text(value) -> str:
    if value is None or (isinstance(value, float) and value != value):
        return ""
    return str(value).strip()


def _key(value) -> str:
    return _text(value).casefold()


def page_number(page_name) -> str | None:
    """Leading page number of a destination text ("13 非电量信号输出回路3" -> "13")."""
    match = _PAGE_NUMBER.match(_text(page_name))
    return str(int(match.group(1))) if match else None


def _connection_values(connections) -> set[str]:
    values = set()
    for connection in connections:
        for part in _VALUE_SEPARATOR.split(_text(connection.get("normalized") or connection.get("value"))):
            part = part.strip().strip("&").strip()
            if part:
                values.add(part.casefold())
    return values


def build_cross_page_links(strip_rows, ports, pairs, pages) -> dict:
    """Continuity links, candidates and coverage for the cross-page references of terminal-strip rows.

    strip_rows: dicts with record_id, sheet_id, file_id, endpoint_identity, connections (dicts with text_id and
        value/normalized) and cross_page_refs (dicts with handle, port_number, page_name).
    ports: dicts with record_id, file_id, sheet_id, insert_handle, port_number, endpoint_identity, category and
        has_wire_contact.
    pairs: dicts with pair_id, status, sheet_id, left_value, right_value, left_text_id, right_text_id,
        left_port_ids and right_port_ids. Discard pairs are ignored.
    pages: dicts with file_id and sheet_no.

    Returns {"links", "candidates", "stats", "covered"}; ``covered`` maps a target port id to the link ids that
    cover it. The pairs are read, never changed.
    """
    stats = Counter()
    files_by_page = defaultdict(list)
    for page in pages:
        number = _text(page.get("sheet_no")).lstrip("0")
        if number:
            files_by_page[number].append(page["file_id"])
    ports_by_key = defaultdict(list)
    handles_by_file = defaultdict(set)
    for port in ports:
        ports_by_key[(port["file_id"], _text(port["insert_handle"]), _text(port["port_number"]))].append(port)
        handles_by_file[port["file_id"]].add(_text(port["insert_handle"]))
    consumers = defaultdict(list)
    pairs_by_text = defaultdict(list)
    for pair in pairs:
        if _text(pair.get("status")) == "discard":
            continue
        for side in ("left", "right"):
            for port_id in pair.get(f"{side}_port_ids") or []:
                consumers[port_id].append((pair, side))
            text_id = _text(pair.get(f"{side}_text_id"))
            if text_id:
                pairs_by_text[(pair["sheet_id"], text_id)].append((pair, side))

    links, candidates = [], []
    claims = defaultdict(list)
    for row in strip_rows:
        refs = row.get("cross_page_refs") or []
        if not refs:
            continue
        row_key = _key(row.get("endpoint_identity"))
        connections = row.get("connections") or []
        supporting = {}
        for connection in connections:
            for pair, side in pairs_by_text.get((row["sheet_id"], _text(connection.get("text_id"))), []):
                supporting[pair["pair_id"]] = (pair, side)
        far = _connection_values(connections)
        for pair, side in supporting.values():
            other = pair.get("right_value") if side == "left" else pair.get("left_value")
            if _key(other):
                far.add(_key(other))
        far.discard(row_key)
        for ref in refs:
            stats["refs"] += 1
            handle, port_number = _text(ref.get("handle")), _text(ref.get("port_number"))
            number = page_number(ref.get("page_name"))
            if number is None:
                stats["no_page_number"] += 1
                continue
            files = files_by_page.get(number, [])
            if not files:
                stats["page_not_in_project"] += 1
                continue
            hits = [f for f in files if (f, handle, port_number) in ports_by_key]
            if not hits:
                # The handle may exist only on another drawing (a stale reference), or nowhere in the project.
                elsewhere = any(handle in handles for file_id, handles in handles_by_file.items() if file_id not in files)
                stats["handle_on_other_page" if elsewhere else "target_absent"] += 1
                continue
            if len(hits) > 1:
                stats["ambiguous_page"] += 1
                continue
            if hits[0] == row["file_id"]:
                stats["same_page"] += 1
                continue
            target_hits = ports_by_key[(hits[0], handle, port_number)]
            if len(target_hits) > 1:
                stats["ambiguous_port"] += 1
                continue
            target = target_hits[0]
            if target.get("category") not in TERMINAL_CATEGORIES:
                stats["target_not_terminal"] += 1
                continue
            target_key = _key(target.get("endpoint_identity"))
            if not target_key:
                stats["target_no_identity"] += 1
                continue
            if not supporting:
                stats["row_has_no_strip_pair"] += 1
                continue
            target_consumers = consumers.get(target["record_id"], [])
            other_values = set()
            for pair, side in target_consumers:
                other = pair.get("right_value") if side == "left" else pair.get("left_value")
                if _key(other) and _key(other) != target_key:
                    other_values.add(_key(other))
            explained = {row_key} | far
            link_id = "XPL:" + hashlib.sha1(
                f"{row['record_id']}|{handle}|{port_number}".encode("utf-8")).hexdigest()[:16]
            record = {
                "link_id": link_id, "strip_record_id": row["record_id"], "strip_sheet_id": row["sheet_id"],
                "strip_file_id": row["file_id"], "strip_identity": _text(row.get("endpoint_identity")),
                "ref_handle": handle, "ref_port_number": port_number, "ref_page_no": number,
                "target_port_id": target["record_id"], "target_file_id": hits[0],
                "target_identity": _text(target.get("endpoint_identity")),
                "target_wire_contact": bool(target.get("has_wire_contact")),
                "far_values": sorted(far), "supporting_pair_ids": sorted(supporting),
                "consumer_pair_ids": sorted({pair["pair_id"] for pair, _ in target_consumers}),
                "consumer_other_values": sorted(other_values),
            }
            if target_key == row_key:
                record["relation"] = RELATION_ROW
            elif target_key in far:
                record["relation"] = RELATION_CONN
            else:
                record["relation"] = "differs"
                if not far:
                    stats["differs_without_far_value"] += 1
                    continue
                if target_consumers:
                    if other_values & explained:
                        stats["differs:consumed_agrees_with_row_or_far"] += 1
                        continue
                    record["candidate"] = CANDIDATE_CONSUMED
                else:
                    record["candidate"] = CANDIDATE_FREE
                stats["candidate:" + record["candidate"]] += 1
                candidates.append(record)
                continue
            record["candidate"] = None
            record["covers_target"] = bool(not target_consumers and record["target_wire_contact"])
            if record["covers_target"]:
                claims[target["record_id"]].append(link_id)
                stats[f"{record['relation']}:covers"] += 1
            elif target_consumers:
                stats[f"{record['relation']}:target_already_consumed"] += 1
                if not (other_values & explained):
                    # Informational only: the identity agrees, but the target's own wire goes elsewhere.
                    stats[f"{record['relation']}:target_consumer_other_differs"] += 1
            else:
                stats[f"{record['relation']}:no_wire_contact"] += 1
            links.append(record)

    covered = {}
    by_id = {link["link_id"]: link for link in links}
    for port_id, link_ids in claims.items():
        if len(link_ids) > 1:
            stats["multi_claim_not_covered"] += 1
            for link_id in link_ids:
                by_id[link_id]["covers_target"] = False
            continue
        covered[port_id] = link_ids
    stats["covered_targets"] = len(covered)
    return {"links": links, "candidates": candidates, "stats": dict(stats), "covered": covered}
