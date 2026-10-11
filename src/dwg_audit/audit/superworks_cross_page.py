"""Cross-page continuity of SuperWORKS terminal-strip rows (X2), and equivalence of strip rows (XPAGE-2).

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

Equivalence (XPAGE-2). A disagreeing target is not a contradiction when its other end, or its identity, is
electrically the row itself. Strip rows are equivalent when they are joined on the strip page:

- a *short bridge* (the yellow bar between two adjacent terminal circles, drawn as two vertical segments
  meeting at the cell boundary: ``short_bridge_pairs``);
- a *one-hop* reference: a row names, as its far value, the identity of another row that names the first
  one back (a wire between two rows of the same page);
- a range identity ``U3D7~8`` names every member ``U3D7``, ``U3D8``.

The equivalence group of a row is the union of these. A disagreement is *explained* (relation
``continuity_group``, reported, not coverage, not a candidate) when the target identity, or the other end of
the target's own wire, lies in the row's group or one hop from it. A target claimed by two or more rows is a
shared node: the rows and the target's other end meet on one port, so the disagreement is not reported.

Targets that still disagree are reported, never made issues here:

- ``contradiction_candidate``: the target is consumed by a non-discard pair whose other end is a known value
  that is neither in the row's equivalence group nor the row identity or far values.
- ``identity_mismatch_unconsumed``: the target is free and its identity differs from every far value.
  A consumed target whose other end is empty has no evidence to compare, and is counted, not reported.

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
RELATION_GROUP = "continuity_group"
CANDIDATE_CONSUMED = "contradiction_candidate"
CANDIDATE_FREE = "identity_mismatch_unconsumed"
_PAGE_NUMBER = re.compile(r"\s*(\d+)")
_VALUE_SEPARATOR = re.compile(r"[,，;；]")
_RANGE_LABEL = re.compile(r"(.+?)(\d+)[~～](\d+)")
_MAX_RANGE_MEMBERS = 200
# Short bridge geometry (drawn on the terminal-strip page): a circle at the centre of each row cell, and
# segments of this length from a circle edge to the cell boundary.
_ROW_CENTRE_OFFSET = 1.5
_CIRCLE_RADIUS = 0.75
_SEGMENT_LENGTH = 1.75
_TOL = 0.05


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


def expand_identity(value) -> set[str]:
    """Casefold identity keys a strip value names: 'U3D7~8' -> {'u3d7~8', 'u3d7', 'u3d8'}."""
    text = _text(value)
    if not text:
        return set()
    keys = {text.casefold()}
    match = _RANGE_LABEL.fullmatch(text)
    if match and 0 <= int(match[3]) - int(match[2]) < _MAX_RANGE_MEMBERS:
        keys.update(f"{match[1]}{number}".casefold() for number in range(int(match[2]), int(match[3]) + 1))
    return keys


def _connection_values(connections) -> set[str]:
    values = set()
    for connection in connections:
        for part in _VALUE_SEPARATOR.split(_text(connection.get("normalized") or connection.get("value"))):
            part = part.strip().strip("&").strip()
            if part:
                values.add(part.casefold())
    return values


def short_bridge_pairs(strip_rows, lines) -> list[tuple[str, str]]:
    """Consecutive strip rows joined by a short bridge drawn on their strip page.

    strip_rows: dicts with record_id, file_id, group (the strip table key, e.g. the header handle), x, y (the
        row text position). lines: dicts with file_id, x0, y0, x1, y1 (the drawn LINE segments of the pages).

    Two rows of one table are joined when both halves of the bridge exist at the boundary between them, at the
    same x: a vertical segment from the upper circle's lower edge to the boundary and one from the boundary to
    the lower circle's upper edge. Geometry only; the colour of the bridge is not stored in the findings.
    """
    vertical = defaultdict(list)
    for line in lines:
        if abs(float(line["x0"]) - float(line["x1"])) > 0.01:
            continue
        lo, hi = sorted((float(line["y0"]), float(line["y1"])))
        if abs((hi - lo) - _SEGMENT_LENGTH) <= 0.02:
            vertical[line["file_id"]].append((float(line["x0"]), lo, hi))
    tables = defaultdict(list)
    for row in strip_rows:
        if row.get("x") is None or row.get("y") is None or row.get("group") is None:
            continue
        tables[(row["file_id"], row["group"])].append(row)
    links = []
    for (file_id, _), rows in tables.items():
        segments = vertical.get(file_id)
        if not segments or len(rows) < 2:
            continue
        rows = sorted(rows, key=lambda r: -(float(r["y"]) + _ROW_CENTRE_OFFSET))
        for upper, lower in zip(rows, rows[1:]):
            cu = float(upper["y"]) + _ROW_CENTRE_OFFSET
            cl = float(lower["y"]) + _ROW_CENTRE_OFFSET
            if abs((cu - cl) - 5.0) > _TOL:
                continue
            mid = (cu + cl) / 2
            up_end, low_end = cu - _CIRCLE_RADIUS, cl + _CIRCLE_RADIUS
            xs_up = {x for x, lo, hi in segments if _near_pair(lo, hi, mid, up_end)}
            xs_low = {x for x, lo, hi in segments if _near_pair(lo, hi, mid, low_end)}
            shared = [x for x in xs_up if any(abs(x - y) <= _TOL for y in xs_low)]
            if shared:
                links.append((upper["record_id"], lower["record_id"]))
    return links


def _near_pair(lo, hi, a, b) -> bool:
    return (abs(lo - min(a, b)) <= _TOL and abs(hi - max(a, b)) <= _TOL)


class _Components:
    def __init__(self):
        self._parent = {}

    def find(self, item):
        self._parent.setdefault(item, item)
        while self._parent[item] != item:
            self._parent[item] = self._parent[self._parent[item]]
            item = self._parent[item]
        return item

    def union(self, a, b):
        root_a, root_b = self.find(a), self.find(b)
        if root_a != root_b:
            self._parent[root_a] = root_b

    def members_by_root(self):
        out = defaultdict(set)
        for item in list(self._parent):
            out[self.find(item)].add(item)
        return out


def build_cross_page_links(strip_rows, ports, pairs, pages, bridges=()) -> dict:
    """Continuity links, equivalence, candidates and coverage for the cross-page references of strip rows.

    strip_rows: dicts with record_id, sheet_id, file_id, endpoint_identity, connections (dicts with text_id and
        value/normalized) and cross_page_refs (dicts with handle, port_number, page_name).
    ports: dicts with record_id, file_id, sheet_id, insert_handle, port_number, endpoint_identity, category and
        has_wire_contact.
    pairs: dicts with pair_id, status, sheet_id, left_value, right_value, left_text_id, right_text_id,
        left_port_ids and right_port_ids. Discard pairs are ignored.
    pages: dicts with file_id and sheet_no.
    bridges: pairs of strip-row record_ids that are electrically joined on their page (see short_bridge_pairs).

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

    # Equivalence of strip rows: bridge components, plus one-hop reciprocal references.
    strips = {row["record_id"]: row for row in strip_rows}
    far_of = {rid: _connection_values(row.get("connections") or []) for rid, row in strips.items()}
    components = _Components()
    for rid in strips:
        components.find(rid)
    bridged = 0
    for upper, lower in bridges:
        if upper in strips and lower in strips:
            components.union(upper, lower)
            bridged += 1
    stats["bridge_links"] = bridged
    members_of = components.members_by_root()

    def members(rid):
        return members_of.get(components.find(rid), {rid})
    identity_index = defaultdict(set)
    for rid, row in strips.items():
        for key in expand_identity(row.get("endpoint_identity")):
            identity_index[key].add(rid)
    reciprocal = defaultdict(set)
    for rid, row in strips.items():
        own = expand_identity(row.get("endpoint_identity"))
        for value in far_of[rid]:
            for other in identity_index.get(value, ()):
                if other != rid and far_of[other] & own:
                    reciprocal[rid].add(other)

    group_cache = {}

    def group_of(rid):
        if rid not in group_cache:
            member_set = members(rid)
            ident, far = set(), set()
            for m in member_set:
                ident |= expand_identity(strips[m].get("endpoint_identity"))
                far |= {k for v in far_of[m] for k in expand_identity(v)}
            hop_ident, hop_far = set(), set()
            for m in member_set:
                for other in reciprocal.get(m, ()):
                    for o in members(other):
                        hop_ident |= expand_identity(strips[o].get("endpoint_identity"))
                        hop_far |= {k for v in far_of[o] for k in expand_identity(v)}
            group_cache[rid] = (ident, far, hop_ident, hop_far)
        return group_cache[rid]

    # First pass: resolve every cross-page reference of a strip row that has a supporting pair. Each claim is
    # kept with its target port, so a port claimed by two or more rows can be recognised as a shared node.
    resolved = []
    claimants = defaultdict(set)
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
            claimants[target["record_id"]].add(row["record_id"])
            resolved.append({"row": row, "row_key": row_key, "far": far, "supporting": supporting, "handle": handle,
                             "port_number": port_number, "number": number, "hit_file": hits[0], "target": target,
                             "target_key": target_key})

    # Second pass: classify each claim against the row's own identity, its far values and its equivalence group.
    links, candidates = [], []
    claims = defaultdict(list)
    for item in resolved:
        row, row_key, far = item["row"], item["row_key"], item["far"]
        target, target_key = item["target"], item["target_key"]
        supporting = item["supporting"]
        target_consumers = consumers.get(target["record_id"], [])
        other_raw = set()
        other_values = set()
        for pair, side in target_consumers:
            other = pair.get("right_value") if side == "left" else pair.get("left_value")
            if _key(other) and _key(other) != target_key:
                other_raw.add(_key(other))
                other_values |= expand_identity(other)
        explained = {row_key} | far
        link_id = "XPL:" + hashlib.sha1(
            f"{row['record_id']}|{item['handle']}|{item['port_number']}".encode("utf-8")).hexdigest()[:16]
        record = {
            "link_id": link_id, "strip_record_id": row["record_id"], "strip_sheet_id": row["sheet_id"],
            "strip_file_id": row["file_id"], "strip_identity": _text(row.get("endpoint_identity")),
            "ref_handle": item["handle"], "ref_port_number": item["port_number"], "ref_page_no": item["number"],
            "target_port_id": target["record_id"], "target_file_id": item["hit_file"],
            "target_identity": _text(target.get("endpoint_identity")),
            "target_wire_contact": bool(target.get("has_wire_contact")),
            "far_values": sorted(far), "supporting_pair_ids": sorted(supporting),
            "consumer_pair_ids": sorted({pair["pair_id"] for pair, _ in target_consumers}),
            "consumer_other_values": sorted(other_raw),
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
            if target_consumers and not other_raw:
                # The consumer's other end carries no value: nothing to compare, so no evidence either way.
                stats["consumer_other_empty"] += 1
                continue
            if target_consumers and (other_values & explained):
                stats["differs:consumed_agrees_with_row_or_far"] += 1
                continue
            group_ident, group_far, hop_ident, hop_far = group_of(row["record_id"])
            target_keys = expand_identity(target.get("endpoint_identity"))
            reason = None
            if target_keys & group_ident:
                reason = "target_in_group"
            elif target_keys & group_far:
                reason = "target_in_group_far"
            elif other_values & (group_ident | group_far):
                reason = "other_in_group"
            elif target_keys & (hop_ident | hop_far):
                reason = "target_in_hop"
            elif other_values & (hop_ident | hop_far):
                reason = "other_in_hop"
            elif target_consumers and len(claimants[target["record_id"]]) >= 2:
                # A claimed port whose own wire is known: the claimants and that wire meet on one node.
                reason = "shared_target_node"
            if reason is not None:
                record["relation"] = RELATION_GROUP
                record["equivalence"] = reason
                record["candidate"] = None
                record["covers_target"] = False
                stats[f"{RELATION_GROUP}:{reason}"] += 1
                links.append(record)
                continue
            if target_consumers:
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
