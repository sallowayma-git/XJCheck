"""Metadata-owned recognition over the existing producers' wires and table rows."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import time
from collections import Counter, defaultdict, deque
from dataclasses import asdict, replace

from dwg_audit.domain.models import Pair, SwPort, LineGroup
from dwg_audit.audit.superworks_device_internal import DEVICE_INTERNAL, device_internal_verdict, label_of
from dwg_audit.audit.superworks_wire_walk import (device_frame, inside_rect, mark_touches, rectangles,
                                                 segment_index as walk_segment_index, walk_wire)
from dwg_audit.extract.superworks_loggen import SYMB2_IDENTITY_SOURCE, SYMB2_STATUS
from dwg_audit.extract.superworks_semantics import (CONNECT_ANCHOR_COINCIDENT_TOL,
    SuperworksData, normalize)

_TRUE_CONFLICTS = {
    "dangling_label_handle", "stale_label_reference", "label_owner_mismatch",
    "nonreciprocal_label", "nonreciprocal_pin", "dangling_pin_handle",
    "stale_pin_reference", "invalid_strip_header_reference",
    "invalid_strip_connection_reference", "competing_physical_port_instances",
    "competing_physical_port_identities",
}

# Same-identity wire groups are diagnostics, never production claims.  They are
# recorded with one of these two reason codes and are excluded from every
# cross-page, duplicate and cardinality rule.
SELF_CONNECTION_REASONS = {
    "same_physical_port_at_both_ends": "same_physical_port",
    "same_logical_identity_other_contact": "same_logical_identity_other_contact",
}

_COMPONENT_VIEW_CATEGORIES = {"元件接线图", "背板接线图", "背板表格型图"}


def _id(key):
    return "PSW" + hashlib.sha256(key.encode()).hexdigest()[:16]


def _key(value):
    return re.sub(r"\s+", "", normalize(value or "")).casefold()


def _contact_gap(left, right):
    return min(math.hypot(a[0] - b[0], a[1] - b[1])
               for a in ((left.start_x, left.start_y), (left.end_x, left.end_y))
               for b in ((right.start_x, right.start_y), (right.end_x, right.end_y)))


def _coincident_ports(ports, key):
    """Return the first physically coincident competing port pair, else None.

    Distinct positions may legitimately repeat one terminal name; the user has
    confirmed that only physical contact competition is a conflict.
    """
    for index, left in enumerate(ports):
        for right in ports[index + 1:]:
            if key(left) == key(right):
                continue
            gap = _contact_gap(left, right)
            if gap <= max(left.tolerance, right.tolerance) + 1e-8:
                return left, right, gap
    return None


def _pin_is_resolved(port):
    pin = port.pin if isinstance(port.pin, dict) else {}
    return bool(pin.get("resolved") and pin.get("normalized"))


def _view_scope(view, *, file_id, sheet_id, view_key, scope_key, record_id, page=None, sheet_order=None):
    return {
        "source": "superworks", "view": view, "view_key": view_key, "scope_key": scope_key,
        "record_id": record_id, "file_id": file_id, "sheet_id": sheet_id,
        "sheet_order": sheet_order if sheet_order is not None else (page.sheet_order if page else None),
        "page_type": page.page_type if page else None,
        "sheet_category": page.sheet_category if page else None,
    }


def _view_for_page(page):
    category = getattr(page, "sheet_category", None) or ""
    if category in _COMPONENT_VIEW_CATEGORIES:
        return "component_diagram"
    if category == "屏端子图":
        return "terminal_strip"
    return "schematic"


def _category(old, new):
    if new and new.status == "review" and new.evidence.get("sw_conflicts"):
        return "D"
    if old is None or not old.left_value or not old.right_value:
        return "A"
    if (old.left_value, old.right_value, old.left_text_id, old.right_text_id) == (new.left_value,new.right_value,new.left_text_id,new.right_text_id):
        return "F" if (old.confidence,old.status,old.pair_kind)!=(new.confidence,new.status,new.pair_kind) else "E"
    if (old.left_text_id,old.right_text_id)==(new.left_text_id,new.right_text_id):
        return "C"
    return "B"


class PortIndex:
    def __init__(self, ports):
        self.cells=defaultdict(list)
        self.max_tol=0.0
        for port in ports:
            self.max_tol=max(self.max_tol,port.tolerance)
            for x,y in ((port.start_x,port.start_y),(port.end_x,port.end_y)):
                self.cells[(math.floor(x/2),math.floor(y/2))].append(port)

    def find(self,x,y):
        result={}
        radius=math.ceil(self.max_tol/2)+1
        for dx in range(-radius,radius+1):
            for dy in range(-radius,radius+1):
                for p in self.cells.get((math.floor(x/2)+dx,math.floor(y/2)+dy),()):
                    distance=min(math.hypot(x-a,y-b) for a,b in ((p.start_x,p.start_y),(p.end_x,p.end_y)))
                    if distance<=p.tolerance+1e-8:
                        result[p.record_id]=p
        return list(result.values())


def _point_key(x,y):
    return round(x,5),round(y,5)


class WireNetwork:
    """Endpoint junctions and explicit dots only; no arbitrary crossings or block artwork."""
    def __init__(self,lines,dots,member_ids):
        self.edges=defaultdict(list)
        self.positions={}
        for line in lines:
            if line.source_block_name or (line.line_id not in member_ids and line.layer.upper() != "CONNECT"):
                continue
            a,b=(line.start_x,line.start_y),(line.end_x,line.end_y)
            points=[(0.0,a),(1.0,b)]
            vx,vy=b[0]-a[0],b[1]-a[1]
            denominator=vx*vx+vy*vy
            if denominator:
                for dot in dots:
                    fraction=((dot.x-a[0])*vx+(dot.y-a[1])*vy)/denominator
                    if 0<fraction<1 and math.hypot(a[0]+fraction*vx-dot.x,a[1]+fraction*vy-dot.y)<1e-5:
                        points.append((fraction,(dot.x,dot.y)))
            points.sort()
            for (_,p),(_,q) in zip(points,points[1:]):
                pk,qk=_point_key(*p),_point_key(*q)
                self.positions[pk],self.positions[qk]=p,q
                self.edges[pk].append((qk,line.line_id))
                self.edges[qk].append((pk,line.line_id))

    def reachable(self,x,y,index,excluded):
        root=_point_key(x,y)
        queue=deque([(root,[])])
        visited={root}
        found={}
        while queue:
            node,path=queue.popleft()
            if path:
                for port in index.find(*self.positions.get(node,node)):
                    found[port.record_id]=(port,path)
            for neighbor,line_id in self.edges.get(node,()):
                if line_id in excluded or neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append((neighbor,path+[line_id]))
        return list(found.values())


def _endpoint(ports, path=None):
    identities={_key(p.endpoint_identity) for p in ports if p.endpoint_identity}
    conflicts=[]
    for port in ports:
        for reason in port.reason_codes:
            # An empty or unresolved pin number is an unresolved endpoint, not a
            # metadata conflict.
            if reason == "nonreciprocal_pin" and not _pin_is_resolved(port):
                continue
            conflicts.append(reason)
    competing=[]
    if len(identities) > 1:
        pair = _coincident_ports(ports, lambda port: _key(port.endpoint_identity))
        if pair:
            conflicts.append("competing_physical_port_identities")
            competing.append(pair)
    elif len({p.symbol_id for p in ports}) > 1:
        # Competing instances are a conflict only when their contacts coincide.
        pair = _coincident_ports(ports, lambda port: port.symbol_id)
        if pair:
            conflicts.append("competing_physical_port_instances")
            competing.append(pair)
    if not ports:
        return None
    selected=ports[0]
    text=selected.label if selected.category=="端子" else selected.pin
    if not selected.endpoint_identity:
        conflicts.append("unresolved_endpoint_identity")
    if any(not p.validation.get("port_touched_by_wire") for p in ports):
        conflicts.append("port_not_touched_by_wire")
    aliases = sorted({alias for alias in (selected.pin or {}).get("endpoint_aliases", [])
                      if alias and alias != selected.endpoint_identity})
    return {"value": selected.endpoint_identity if len(identities)<=1 else None, "candidate_values":sorted({p.endpoint_identity for p in ports if p.endpoint_identity}), "category":selected.category, "text_id":text.get("text_id"),
            **({"endpoint_aliases": aliases} if aliases else {}),
            "label_text_id":selected.label.get("text_id"), "pin_text_id":selected.pin.get("text_id"),
            "label_handle":selected.label.get("handle"),"pin_handle":selected.pin.get("handle"),
            "symbol_handle":selected.insert_handle,"symbol_id":selected.symbol_id,
            "port_number":selected.port_number, "port_ids":sorted(p.record_id for p in ports),
            "ports":[{"port_id":p.record_id,"symbol_id":p.symbol_id,"port_number":p.port_number,
                      "category":p.category,"endpoint_identity":p.endpoint_identity,
                      "start":[p.start_x,p.start_y],"end":[p.end_x,p.end_y],
                      "tolerance":p.tolerance,"validation":p.validation} for p in ports],
            "competing_ports":[{"left":a.record_id,"right":b.record_id,
                                "left_symbol":a.symbol_id,"right_symbol":b.symbol_id,
                                "left_port_number":a.port_number,"right_port_number":b.port_number,
                                "gap":gap} for a,b,gap in competing],
            "validation":selected.validation,"network_line_ids":path or [],
            "wire_touched":all(p.validation.get("port_touched_by_wire") for p in ports),
            "reason_codes":sorted(set(conflicts))}


def _true_conflicts(reasons):
    return sorted(set(reasons) & _TRUE_CONFLICTS)


def _legacy_pairs_on_label_anchor_with_other_port(old, label, group_by_id):
    """Legacy component pairs for this connect label whose port number disagrees with the
    SW connect line, while their own supporting wire ends on the label's anchor.

    Such a pair is kept over the SW result: the wire geometry says the legacy port is the
    one physically at this terminal, and the SW port was read from a neighbouring leader.
    """
    ax, ay = label.text.get("anchor_x"), label.text.get("anchor_y")
    if ax is None or ay is None:
        return []
    disputed = []
    for pair in old:
        legacy_port = pair.evidence.get("component_port")
        if legacy_port in (None, "") or str(legacy_port) == str(label.port_number):
            continue
        group = group_by_id.get(pair.line_group_id)
        if group is None:
            continue
        ends = ((group.start_x, group.start_y), (group.end_x, group.end_y))
        if any(math.hypot(x - ax, y - ay) <= CONNECT_ANCHOR_COINCIDENT_TOL for x, y in ends):
            disputed.append(pair)
    return disputed


def _strip_scope_index(data):
    rows_by_endpoint = defaultdict(list)
    for row in data.strip_rows:
        if not row.endpoint_identity or not row.header.get("resolved") or not row.validation.get("reciprocal_ok"):
            continue
        header_handle = row.header.get("handle")
        header_text_id = row.header.get("text_id")
        if not header_handle and not header_text_id:
            continue
        scope = (row.file_id, header_handle or header_text_id)
        rows_by_endpoint[_key(row.endpoint_identity)].append((scope, row))
    return rows_by_endpoint


def _same_strip_relation(left, right, rows_by_endpoint, xml_ranks):
    if left["category"] != "端子" or right["category"] != "端子":
        return None
    left_rows = rows_by_endpoint.get(_key(left["value"]), [])
    right_rows = rows_by_endpoint.get(_key(right["value"]), [])
    left_scopes = {scope for scope, _ in left_rows}
    right_scopes = {scope for scope, _ in right_rows}
    shared = left_scopes & right_scopes
    if len(shared) != 1:
        return None
    scope = next(iter(shared))
    rows_for = lambda records: [row for row_scope, row in records if row_scope == scope]
    left_owner, right_owner = rows_for(left_rows), rows_for(right_rows)
    if not left_owner or not right_owner:
        return None
    header = left_owner[0].header
    return {
        "kind": "same_terminal_strip_header",
        "scope_key": f"{scope[0]}:{scope[1]}",
        "header_handle": header.get("handle"),
        "header_text_id": header.get("text_id"),
        "header_value": header.get("normalized"),
        "xml_rank": xml_ranks.get(_key(header.get("normalized", ""))),
        "left_rows": [{"row_id": row.record_id, "row_handle": row.row_handle,
                       "row_text_id": row.row.get("text_id")} for row in left_owner],
        "right_rows": [{"row_id": row.record_id, "row_handle": row.row_handle,
                        "row_text_id": row.row.get("text_id")} for row in right_owner],
        "authority": "reciprocal_strip_row_identity_and_header_handle",
    }


def _self_connection_reason(left, right):
    """F1: one logical identity at both ends of one wire group."""
    if not left or not right:
        return None
    if set(left.get("port_ids") or []) & set(right.get("port_ids") or []):
        return "same_physical_port_at_both_ends"
    left_value, right_value = left.get("value"), right.get("value")
    if left_value and right_value and _key(left_value) == _key(right_value):
        return "same_logical_identity_other_contact"
    return None


def _self_connection_detail(left, right):
    if set(left.get("port_ids") or []) & set(right.get("port_ids") or []):
        return "same_physical_port"
    if left.get("symbol_id") and left.get("symbol_id") == right.get("symbol_id"):
        return "same_instance_other_port"
    return "other_instance"


def _spans_one_symbol(left, right):
    """True when the group's own geometry bridges two contacts of one symbol.

    A wire drawn across a symbol makes the group start and end on the two ports
    of that same instance; the span between the contacts belongs to the symbol,
    so the group is split at the port instead of being kept as a wire.
    """
    return bool(
        left.get("symbol_id")
        and left.get("symbol_id") == right.get("symbol_id")
        and not left.get("network_line_ids")
        and not right.get("network_line_ids")
    )


_RANGE_SUFFIX = re.compile(r"(.+?)[~～]\d+")
_RANGE_LABEL = re.compile(r"(.+?)(\d+)[~～](\d+)")
_MAX_RANGE_MEMBERS = 200


def _strip_range_base(value):
    """'1-4Q2D3~7' -> '1-4Q2D3'; a range suffix is removed before header lookup."""
    text = str(value or "")
    match = _RANGE_SUFFIX.fullmatch(text)
    return match[1] if match else text


# SuperWORKS draws '&' and '*' as decorative boundary marks around an external
# endpoint (e.g. "* 1n2107", "1I2D1 *"). Only leading/trailing runs of them and
# the blanks beside them are removed; interior characters, and '@' (a layout
# marker still under review, L-17), are left as written.
_SW_ENDPOINT_DECORATION_PATTERN = re.compile(r"^[\s&*]+|[\s&*]+$")


def _clean_sw_endpoint_value(value):
    """Canonical SuperWORKS external endpoint text; the caller keeps the raw text."""
    return _SW_ENDPOINT_DECORATION_PATTERN.sub("", normalize(str(value or "")))


def _destination_keys(value):
    """Identity keys a strip connection value names; a range N~M names each member."""
    keys = set()
    for piece in re.split(r"[,，]", normalize(str(value or ""))):
        piece = _clean_sw_endpoint_value(piece)
        if not piece:
            continue
        match = _RANGE_LABEL.fullmatch(piece)
        if match and 0 <= int(match[3]) - int(match[2]) < _MAX_RANGE_MEMBERS:
            keys.update(_key(f"{match[1]}{number}") for number in range(int(match[2]), int(match[3]) + 1))
        else:
            keys.add(_key(piece))
    return keys


class StripMembership:
    """Terminal-strip header of a terminal identity, from metadata only.

    1. the header of the strip row(s) that carry the identity (exact, then with
       the range suffix removed);
    2. only when no strip row carries the identity, the longest LdDzbInfo.xml
       strip name that prefixes it, the remainder beginning with the row number.
    """

    def __init__(self, data):
        self.headers = defaultdict(dict)
        self.destinations = defaultdict(set)
        for row in data.strip_rows:
            if not row.endpoint_identity:
                continue
            key = _key(row.endpoint_identity)
            # The strip the row belongs to, not its header text: a continuation header
            # ("上接3-21GD16") names the rows above it, so two rows of one strip (GD16 under
            # the first header, GD17 under the continuation) must compare as the same strip.
            header = (row.validation or {}).get("strip_name") or (row.header or {}).get("normalized")
            if header:
                self.headers[key][_key(header)] = header
            for connection in row.connections:
                self.destinations[key].update(_destination_keys(connection.get("value", "")))
        names = [item.get("name") for item in data.dictionary.get("strip_order", []) if item.get("name")]
        self.xml_names = sorted(((_key(name), name) for name in names), key=lambda item: -len(item[0]))

    @staticmethod
    def _identities(value, aliases):
        return [value, *aliases] if value else list(aliases)

    def header_for(self, value, aliases=()):
        """Return (header, method); header is None when it cannot be decided."""
        identities = self._identities(value, aliases)
        if not identities:
            return None, "no_identity"
        for candidates in (identities, [_strip_range_base(v) for v in identities]):
            found = {}
            for candidate in candidates:
                found.update(self.headers.get(_key(candidate), {}))
            if len(found) == 1:
                return next(iter(found.values())), "strip_row_header"
            if len(found) > 1:
                return None, "ambiguous_strip_row_header"
        for candidate in (_strip_range_base(v) for v in identities):
            key = _key(candidate)
            for name_key, name in self.xml_names:
                # The remainder is the row number, which may carry a letter suffix (6A).
                if key.startswith(name_key) and key[len(name_key):][:1].isdigit():
                    return name, "project_strip_name_prefix"
        return None, "unresolved"

    @staticmethod
    def _match_keys(value, aliases):
        identities = StripMembership._identities(value, aliases)
        return {_key(v) for v in identities} | {_key(_strip_range_base(v)) for v in identities}

    def is_row_identity(self, value):
        """True when the value is the identity of a terminal-strip row (range suffix removed if needed)."""
        return any(self.headers.get(key) for key in self._match_keys(value, ()))

    def lists(self, owner, owner_aliases, listed, listed_aliases):
        """True when the strip row(s) of `owner` list `listed` among their connections."""
        listed_keys = self._match_keys(listed, listed_aliases)
        return any(self.destinations.get(own, set()) & listed_keys
                   for own in self._match_keys(owner, owner_aliases))

    def corroborates(self, left, left_aliases, right, right_aliases):
        """True when a row of one end lists the other end among its connections."""
        return self.lists(left, left_aliases, right, right_aliases) or self.lists(right, right_aliases, left, left_aliases)


_CONTRACT_KEYS = ("terminal_short_bridge", "terminal_cross_strip_link", "strip_header",
                  "strip_headers", "strip_corroborated", "strip_membership", "strip_membership_detail")


def _strip_contract_fields(membership, left_value, left_aliases, right_value, right_aliases, *, directed=False):
    """The F3 same-strip / cross-strip fields for one terminal-terminal link.

    `directed` asks for the corroboration of the right end's row alone: the row
    of the right end must list the left end (used when the right end is the other
    terminal of a strip connection, so the connection itself cannot corroborate).
    """
    left_header, left_method = membership.header_for(left_value, left_aliases)
    right_header, right_method = membership.header_for(right_value, right_aliases)
    if not left_header or not right_header:
        return {"strip_membership": "unknown", "strip_membership_detail": {"left": left_method, "right": right_method}}
    if _key(left_header) == _key(right_header):
        return {"terminal_short_bridge": True, "strip_header": left_header, "strip_membership": "same_strip"}
    if directed:
        corroborated = membership.lists(right_value, right_aliases, left_value, left_aliases)
    else:
        corroborated = membership.corroborates(left_value, left_aliases, right_value, right_aliases)
    return {"terminal_cross_strip_link": True, "strip_corroborated": corroborated,
            "strip_headers": [left_header, right_header], "strip_membership": "cross_strip"}


def _classify_terminal_strip_pairs(output, membership):
    """Write the same-strip / cross-strip contract onto SuperWORKS terminal-terminal pairs."""
    for pair in output:
        evidence = pair.evidence or {}
        if evidence.get("source") != "superworks" or evidence.get("pair_kind") not in ("ordinary_pair", "bridge_mapping"):
            continue
        sw = evidence.get("superworks") or {}
        left, right = sw.get("left") or {}, sw.get("right") or {}
        if left.get("category") != "端子" or right.get("category") != "端子":
            continue
        for key in _CONTRACT_KEYS:
            evidence.pop(key, None)
        evidence.update(_strip_contract_fields(
            membership, left.get("value"), left.get("endpoint_aliases") or [],
            right.get("value"), right.get("endpoint_aliases") or []))


def _table_mapping_strip_fields(membership, own_value, destination):
    """The F3 contract for one terminal-strip connection, when its destination is a strip identity.

    The destination must itself name a terminal-strip row; a destination that is not a
    strip identity (a component terminal, a page reference) gets no contract fields.
    """
    if not own_value or not destination or not membership.is_row_identity(destination):
        return {}
    return _strip_contract_fields(membership, own_value, [], destination, [], directed=True)


# L-12 S1 (Y2b): a one-sided legacy ordinary pair whose missing line end carries a SuperWORKS
# connect text is completed from that text.  The text is attributed by its layout outline
# (text_geometry_json corners), not by its anchor: a row label's anchor can sit midway
# between two row ends while its outline touches only its own row.  The missing end must lie
# within SW_LABEL_BOX_TOL_HEIGHTS text heights of the outline, the present end must lie outside
# that window, and the missing end must be the sheet's nearest line end by at least
# SW_LABEL_SEPARATION.  1.0 is the lower example the L-12 brief gives; the four known-good
# GND fills of p075 (PC0123, PC0185, PC0331, PC0393) have an outline margin of 1.24 over the
# next row end, and a 1.5 (half a text height) margin would reject them.
SW_LABEL_BOX_TOL_HEIGHTS = 1.5
SW_LABEL_SEPARATION = 1.0
_SW_LABEL_UNRESOLVED_GEOMETRY = {"ambiguous_connect_line", "connect_line_geometry_not_unique"}
_CJK_PATTERN = re.compile(r"[㐀-鿿豈-﫿]")
_VALUE_SEPARATOR_PATTERN = re.compile(r"[,，]")


def _is_blank_value(value):
    return value is None or (isinstance(value, float) and math.isnan(value)) or not str(value).strip()


def _collect_text_ids(value, found):
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).endswith("text_id") and isinstance(item, str) and item:
                found.add(item)
            _collect_text_ids(item, found)
    elif isinstance(value, list):
        for item in value:
            _collect_text_ids(item, found)
    return found


def _used_text_ids(output):
    used = set()
    for pair in output:
        used.update(text_id for text_id in (pair.left_text_id, pair.right_text_id) if text_id)
        _collect_text_ids(pair.evidence, used)
    return used


def _fillable_one_sided_pair(pair, group):
    """The legacy one-sided pairs that R-PAIR-MISSING-SIDE reports, and only those."""
    if pair.status == "discard" or group is None:
        return False
    if pair.pair_kind != "ordinary_pair" or pair.evidence.get("ordinary_pair_eligible", True) is False:
        return False
    if pair.evidence.get("source") == "superworks":
        return False
    if _is_blank_value(pair.left_value) == _is_blank_value(pair.right_value):
        return False
    layers = {str(layer).upper() for layer in group.layer_hints}
    return not (layers and layers.issubset({"DIM"}))


def _missing_end_points(pair, group):
    """(missing end, present end) of the pair's line group, judged from the present text."""
    missing_side = "left" if _is_blank_value(pair.left_value) else "right"
    px, py = ((pair.right_coord_x, pair.right_coord_y) if missing_side == "left"
              else (pair.left_coord_x, pair.left_coord_y))
    if px is None or py is None:
        return None
    ends = [(group.start_x, group.start_y), (group.end_x, group.end_y)]
    distances = [math.hypot(x - px, y - py) for x, y in ends]
    if abs(distances[0] - distances[1]) < 1e-9:
        return None
    far = 0 if distances[0] > distances[1] else 1
    return missing_side, ends[far], ends[1 - far]


def _connect_text_value(label):
    """Canonical single endpoint value of a connect text, or None when it is not one value."""
    value = _clean_sw_endpoint_value(label.text.get("value", ""))
    if not value or _VALUE_SEPARATOR_PATTERN.search(value) or _CJK_PATTERN.search(value):
        return None
    return value


def _text_outline(text):
    """A text's layout outline as four (x, y) corners from text_geometry_json, else None."""
    try:
        corners = json.loads(text.text_geometry_json or "{}").get("corners")
    except (AttributeError, TypeError, ValueError):
        return None
    if not isinstance(corners, list) or len(corners) != 4:
        return None
    return [(float(x), float(y)) for x, y in corners]


def _segment_distance(point, start, end):
    px, py = point
    ax, ay = start
    bx, by = end
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    t = 0.0 if length_sq == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _outline_distance(point, corners):
    """Distance from a point to a convex outline; zero when the point lies inside it."""
    count = len(corners)
    px, py = point
    sides = [(corners[(i + 1) % count][0] - corners[i][0]) * (py - corners[i][1])
             - (corners[(i + 1) % count][1] - corners[i][1]) * (px - corners[i][0]) for i in range(count)]
    if all(side >= 0 for side in sides) or all(side <= 0 for side in sides):
        return 0.0
    return min(_segment_distance(point, corners[i], corners[(i + 1) % count]) for i in range(count))


def _fill_one_sided_pairs_from_connect_labels(output, connect_labels, line_groups, audit_ids, ledger, text_map):
    """Complete one-sided legacy pairs from unclaimed SuperWORKS connect texts.

    Fail-closed: a pair is completed only when exactly one unclaimed connect text on the same
    sheet has its outline within the window of the missing end, outside it at the present end,
    and the missing end is its nearest line end by at least SW_LABEL_SEPARATION; that text must be the only
    candidate for that end.  Multi-value texts, texts already used by any pair, and pairs with
    two sides are left untouched.
    """
    group_by_id = {group.line_group_id: group for group in line_groups}
    used = _used_text_ids(output)
    sides = []
    for index, pair in enumerate(output):
        group = group_by_id.get(pair.line_group_id)
        if not _fillable_one_sided_pair(pair, group):
            continue
        ends = _missing_end_points(pair, group)
        if ends is None:
            continue
        sides.append((index, pair, *ends))
    labels = []
    for label in connect_labels:
        text_id = label.text.get("text_id")
        if label.sheet_id not in audit_ids or not text_id or text_id in used:
            continue
        if _true_conflicts(label.reason_codes) or set(label.reason_codes) & _SW_LABEL_UNRESOLVED_GEOMETRY:
            continue
        value = _connect_text_value(label)
        text = text_map.get(text_id)
        outline = _text_outline(text) if text is not None else None
        if value is None or outline is None:
            continue
        labels.append((label, value, outline, text.height))
    sheet_ends = defaultdict(set)
    for group in line_groups:
        sheet_ends[(group.file_id, group.sheet_id)].update({(group.start_x, group.start_y), (group.end_x, group.end_y)})
    qualifying = defaultdict(list)
    claimants = defaultdict(list)
    measures = {}
    for position, (_, pair, missing_side, missing_end, present_end) in enumerate(sides):
        ends = sheet_ends[(pair.file_id, pair.sheet_id)]
        for li, (label, _, outline, height) in enumerate(labels):
            if label.sheet_id != pair.sheet_id or label.file_id != pair.file_id:
                continue
            tolerance = SW_LABEL_BOX_TOL_HEIGHTS * height
            d_missing = _outline_distance(missing_end, outline)
            if d_missing > tolerance:
                continue
            d_present = _outline_distance(present_end, outline)
            if d_present <= tolerance:
                continue
            second = min((_outline_distance(end, outline) for end in ends if end != missing_end), default=math.inf)
            if second - d_missing < SW_LABEL_SEPARATION:
                continue
            qualifying[position].append(li)
            claimants[li].append(position)
            measures[(position, li)] = (d_missing, d_present, second, tolerance)
    for position, (index, pair, missing_side, missing_end, present_end) in enumerate(sides):
        if len(qualifying[position]) != 1 or len(claimants[qualifying[position][0]]) != 1:
            continue
        li = qualifying[position][0]
        label, value, _, height = labels[li]
        d_missing, d_present, second, tolerance = measures[(position, li)]
        text_id = label.text.get("text_id")
        evidence = copy.deepcopy(pair.evidence)
        evidence["sw_missing_side_fill"] = {"source": "superworks_connect_label", "side": missing_side,
            "connect_label_id": label.record_id, "text_id": text_id,
            "raw_value": label.text.get("value"), "value": value,
            "attribution": "text_bbox", "text_height": height,
            "bbox_distance": round(d_missing, 4), "present_end_bbox_distance": round(d_present, 4),
            "second_end_distance": None if math.isinf(second) else round(second, 4),
            "tolerance": round(tolerance, 4), "separation_min": SW_LABEL_SEPARATION,
            "scoring": "not_applicable_review"}
        new = replace(pair,
            **{f"{missing_side}_value": value, f"{missing_side}_text_id": text_id,
               f"{missing_side}_coord_x": label.text.get("x"), f"{missing_side}_coord_y": label.text.get("y")},
            status="review", confidence_bucket="review",
            rationale=f"SuperWORKS connect text supplies the missing {missing_side} endpoint; legacy score does not apply, retained for review",
            evidence=evidence)
        output[index] = new
        ledger.append({"element_key": f"sw_missing_side:{label.record_id}", "category": _category(pair, new),
                       "reason": "sw_connect_label_missing_side_fill",
                       "old_pair": asdict(pair), "new_pairs": [asdict(new)]})


def _wire_pair(*, pair_id, line_group_id, sheet_id, file_id, coords, scope_id, left, right, origin,
               conflicts, strip_relation, page_map, review_reasons=()):
    """The SuperWORKS wire Pair for two resolved endpoints.

    Shared by the line-group path of extract_superworks_pairs and the wire-route admission, so a
    pair from either source carries the same fields, status rule and view scope. `conflicts` are
    the true metadata conflicts (kept in evidence); `review_reasons` only force review.
    `coords` is (x1, y1, x2, y2) of the wire, or None when the wire has no geometry.
    """
    if left["category"]==right["category"]=="端子" and strip_relation:
        kind="bridge_mapping"
        bridge_kind="superworks_terminal_strip_same_header"
    else:
        kind="ordinary_pair" if left["category"]==right["category"]=="端子" else "wire_component_mapping"
        bridge_kind=None
    evidence={"source":"superworks","superworks":{"source":"superworks","left":left,"right":right},
              "sw_conflicts":conflicts,"ordinary_pair_eligible":kind=="ordinary_pair",
              "electrical_union_eligible":False,"internal_connectivity_inferred":False,
              "pair_kind":kind,"sheet_order":page_map[sheet_id].sheet_order,
              "selected_left_raw_text":left["value"],"selected_right_raw_text":right["value"],
              "semantic_marker_texts":[left["value"],right["value"]]}
    evidence["superworks"]["line_group_origin"]=origin
    page=page_map.get(sheet_id)
    evidence["view_scope"]=_view_scope(_view_for_page(page),
        file_id=file_id,sheet_id=sheet_id,
        view_key=f"{file_id}:{sheet_id}:schematic",
        scope_key=f"{file_id}:{sheet_id}:{scope_id}",
        record_id=scope_id,page=page)
    if strip_relation:
        evidence["superworks"]["strip_relation"]=strip_relation
    if bridge_kind:
        evidence.update(semantic_kind="terminal_bridge_mapping",bridge_mapping_kind=bridge_kind)
    blocked=bool(conflicts or review_reasons)
    evidence["native_resolution_state"] = "CONFIRMED_CONFLICT" if conflicts else "AMBIGUOUS" if review_reasons else "RESOLVED"
    new=Pair(pair_id=pair_id,line_group_id=line_group_id,
        sheet_id=sheet_id,file_id=file_id,selected_pair_candidate_id=None,
        left_value=left["value"],right_value=right["value"],confidence=.99 if not blocked else .5,
        status="pass" if not blocked else "review",
        rationale="SuperWORKS identity verified against existing wire endpoints" if not blocked else ";".join(list(conflicts)+list(review_reasons)),
        confidence_bucket="high" if not blocked else "review",evidence=evidence,
        left_text_id=left["text_id"],right_text_id=right["text_id"],left_coord_x=coords[0],left_coord_y=coords[1],
        right_coord_x=coords[2],right_coord_y=coords[3],pair_key=f'{left["value"]}->{right["value"]}',pair_kind=kind)
    return new


# LOGGEN phase 2 (wire-route admission). A wire-route record (XRECORD LD_SYMB2LOGGEN or PCL) names the
# SuperWORKS identity at each end of one drawn wire. The rules below add pairs only for records whose
# two ends are both unconsumed terminals; everything else is recorded, never turned into an issue here.
_WIRE_ROUTE_TERMINALS = {"端子", "装置端子"}
# Only an end resolved to a SuperWORKS port identity takes part in admission and reconciliation; an end
# resolved by its text alone (cross-page target not a single SW port) carries no SW identity to compare.
_WIRE_ROUTE_RESOLVED = {"resolved"}
_WIRE_ROUTE_TEXT_ONLY = {"resolved_by_text"}
# Strip rows name the component connected to a terminal in cells styled with this text (PIN-1 row check).
_STRIP_COMPONENT_STYLE = "端子排内接元件"


def _is_blank_side(value):
    return value is None or (isinstance(value, float) and math.isnan(value)) or not str(value).strip()


def _identities_agree(identity, value, aliases=()):
    """Production equivalence of a record identity and a pair side value (the LOGGEN evaluation rules):
    equal after cleaning, a member of a range value, an alias, or the same identity with a letter prefix."""
    if not identity or _is_blank_side(value):
        return False
    identity_key = _key(identity)
    raw = str(value)
    value_key = _key(_clean_sw_endpoint_value(raw))
    if identity_key in (_key(raw), value_key):
        return True
    if identity_key in _destination_keys(raw):
        return True
    if identity_key in {_key(alias) for alias in aliases or [] if alias}:
        return True
    head = identity_key[:-len(value_key)] if value_key and identity_key.endswith(value_key) else ""
    return bool(head and any(ch.isalpha() for ch in head) and any(ch.isdigit() for ch in value_key))


def _is_provisional_half(pair, cut_group_ids):
    """WIRE-BREAK: a non-pass pair on a line group that a symbol-body cut created holds no port.

    The cut leaves the wire's far end on a symbol body, which has no text candidate: the group-level pair is then a
    provisional claim (one-sided, or a review built from a bare number), and the wire-route record of the same wire
    is the authoritative pair for that end. Pass pairs are verified and keep their ports.
    """
    if (pair.evidence or {}).get("sw_wire_route"):
        return False
    return (pair.line_group_id in cut_group_ids
            and (pair.status != "pass" or not pair.left_value or not pair.right_value))


def _provisional_pairs_by_port(pairs, cut_group_ids):
    """port_id -> provisional pairs (see _is_provisional_half) that name the port in their SuperWORKS sides."""
    result = defaultdict(list)
    for pair in pairs:
        if pair.status == "discard" or not _is_provisional_half(pair, cut_group_ids):
            continue
        sw = (pair.evidence or {}).get("superworks") or {}
        for side in ("left", "right"):
            for port_id in (sw.get(side) or {}).get("port_ids") or []:
                result[port_id].append(pair)
    return result


def _consumed_ports(pairs, cut_group_ids=frozenset()):
    """port_id -> [(pair, side)] for every non-discard pair that names the port in its SuperWORKS sides."""
    consumed = defaultdict(list)
    for pair in pairs:
        if pair.status == "discard" or _is_provisional_half(pair, cut_group_ids):
            continue
        sw = (pair.evidence or {}).get("superworks") or {}
        for side in ("left", "right"):
            for port_id in (sw.get(side) or {}).get("port_ids") or []:
                consumed[port_id].append((pair, side))
    return consumed


def _same_segment(group, line):
    a, b = (line.start_x, line.start_y), (line.end_x, line.end_y)
    if a > b:
        a, b = b, a
    return min(
        max(math.hypot(group.start_x - a[0], group.start_y - a[1]), math.hypot(group.end_x - b[0], group.end_y - b[1])),
        max(math.hypot(group.end_x - a[0], group.end_y - a[1]), math.hypot(group.start_x - b[0], group.start_y - b[1])),
    ) < 1e-5


def _symb2_physical_pin(end):
    return (end["file_id"], str(end["terminal_handle"]), str(end["port_number"]))


def _symb2_endpoint(end, text_ids):
    """The endpoint of an unregistered INSERT end: identity from its own label and slot text, no SuperWORKS
    port. Its category is empty, so the pair is a wire-component mapping (never a terminal pair)."""
    evidence = end.get("symb2") or {}
    slot_id = text_ids.get((end["file_id"], evidence.get("slot_handle")))
    label_id = text_ids.get((end["file_id"], evidence.get("label_handle")))
    return {"value": end["identity"], "candidate_values": [end["identity"]], "category": "",
            "text_id": slot_id or label_id, "label_text_id": label_id, "pin_text_id": slot_id,
            "label_handle": evidence.get("label_handle"), "pin_handle": evidence.get("slot_handle"),
            "symbol_handle": end.get("terminal_handle"), "symbol_id": None,
            "port_number": str(end.get("port_number") or ""), "port_ids": [], "ports": [],
            "network_line_ids": [], "wire_touched": False, "reason_codes": [], "competing_ports": [],
            "validation": {}, "identity_source": SYMB2_IDENTITY_SOURCE}


def _strip_row_verdict(terminal_value, identity, strip_rows_by_endpoint):
    """Whether the terminal strip row of the terminal names the candidate identity among its component
    connections ('端子排内接元件'). A terminal without a strip row gives 'row_missing' (not a contradiction)."""
    records = strip_rows_by_endpoint.get(_key(terminal_value), [])
    if not records:
        return "row_missing"
    for _, row in records:
        for connection in row.connections or []:
            if connection.get("style") == _STRIP_COMPONENT_STYLE and _key(identity) in {
                    _key(piece) for piece in _destination_keys(connection.get("value"))}:
                return "agree"
    return "disagree"


def _symb2_reason(end, endpoint, terminal, symb2_ctx):
    """Project-level admission of an unregistered INSERT end: the identity has one terminal partner over the
    project, one wire record per pin, and no contradiction from the terminal's strip row. (reason or None)."""
    identity_key = _key(endpoint["value"])
    if len(symb2_ctx["partners_by_identity"].get(identity_key, ())) > 1:
        return "symb2_identity_conflict"
    if len(symb2_ctx["records_by_pin"].get(_symb2_physical_pin(end), ())) != 1:
        return "symb2_pin_not_single"
    if _strip_row_verdict(terminal["value"], endpoint["value"], symb2_ctx["strip_rows"]) == "disagree":
        return "symb2_strip_row_disagrees"
    return None


def _symb2_rejection(end):
    rejects = (end.get("symb2") or {}).get("rejects") or []
    return "symb2_" + rejects[0] if rejects else "end_unresolved"


def _admission_reason(row, ends, audit_ids, ports_by_key, consumed, symb2_ctx):
    """(reason, None) for the first rule a record fails; (None, (endpoints, end_ports)) when eligible.

    end_ports holds the SuperWORKS ports of the terminal end only; an unregistered INSERT end has none.
    """
    if row["sheet_id"] not in audit_ids:
        return "sheet_not_audited", None
    if len(ends) != 2:
        return "not_two_ends", None
    if any(end.get("status") not in _WIRE_ROUTE_RESOLVED | {SYMB2_STATUS} for end in ends):
        unresolved = next(end for end in ends if end.get("status") not in _WIRE_ROUTE_RESOLVED | {SYMB2_STATUS})
        return (_symb2_rejection(unresolved) if unresolved.get("status") == "insert_not_sw" else "end_unresolved"), None
    if any(end.get("far_source") == "cross_page" for end in ends):
        return "cross_page_end", None
    internal = [end for end in ends if end.get("status") == SYMB2_STATUS]
    if len(internal) > 1:
        return "two_internal_ends", None
    if any(end.get("file_id") != row["file_id"] for end in ends):
        return "cross_file", None
    for end in ends:
        if end.get("status") == SYMB2_STATUS:
            continue
        if not (end.get("category") or ""):
            return "internal_end", None
        if end.get("category") not in _WIRE_ROUTE_TERMINALS:
            return "non_terminal_end", None
    endpoints = []
    end_ports = []
    for end in ends:
        if end.get("status") == SYMB2_STATUS:
            endpoints.append(_symb2_endpoint(end, symb2_ctx["text_ids"]))
            continue
        ports = [port for port in ports_by_key.get((end["file_id"], str(end["terminal_handle"]), str(end["port_number"])), [])
                 if port.sheet_id == row["sheet_id"]]
        endpoint = _endpoint(ports) if ports else None
        if endpoint is None or not endpoint["value"]:
            return "identity_not_single", None
        if _key(endpoint["value"]) != _key(end["identity"]):
            return "identity_mismatch", None
        if endpoint["category"] not in _WIRE_ROUTE_TERMINALS:
            return "non_terminal_end", None
        end_ports.append(ports)
        endpoints.append(endpoint)
    if any(set(endpoint["port_ids"]) & set(consumed) for endpoint in endpoints):
        return "end_consumed", None
    left, right = endpoints
    if _self_connection_reason(left, right):
        return "self_connection", None
    if internal:
        internal_index = next(i for i, end in enumerate(ends) if end.get("status") == SYMB2_STATUS)
        terminal = endpoints[1 - internal_index]
        reason = _symb2_reason(ends[internal_index], endpoints[internal_index], terminal, symb2_ctx)
        if reason:
            return reason, None
    return None, (endpoints, end_ports)


def _symb2_context(rows, data, strip_rows_by_endpoint, texts):
    """Project-wide facts for the unregistered-INSERT ends.

    partners_by_identity: the terminal identities each identity is wired to, over every pin that names it
    (candidate pins through their record's terminal end; SuperWORKS pins through the terminals on their
    wires). A device pin drawn on two sheets is one identity with one partner and is fine; the same identity
    wired to two different terminals is a conflict. Pins with no known partner add nothing.
    records_by_pin: the wire records of each candidate pin (one per pin).
    """
    terminal_on_wire = defaultdict(set)
    for port in data.ports:
        if port.category in _WIRE_ROUTE_TERMINALS and port.endpoint_identity:
            for contact in port.wire_contacts or []:
                terminal_on_wire[(port.file_id, contact.get("wire_handle"))].add(_key(port.endpoint_identity))
    partners_by_identity = defaultdict(set)
    for port in data.ports:
        if port.category in _WIRE_ROUTE_TERMINALS or not port.endpoint_identity:
            continue
        for contact in port.wire_contacts or []:
            partners_by_identity[_key(port.endpoint_identity)] |= terminal_on_wire.get((port.file_id, contact.get("wire_handle")), set())
    for part in data.part_instances:
        for port in part.ports or []:
            if not port.get("endpoint_identity"):
                continue
            for contact in port.get("wire_contacts") or []:
                partners_by_identity[_key(port["endpoint_identity"])] |= terminal_on_wire.get(
                    (part.file_id, contact.get("wire_handle")), set())
    records_by_pin = defaultdict(set)
    for row in rows:
        ends = json.loads(row["ends_json"])
        for index, end in enumerate(ends):
            if end.get("status") != SYMB2_STATUS:
                continue
            other = ends[1 - index] if len(ends) == 2 else {}
            if other.get("status") in _WIRE_ROUTE_RESOLVED and other.get("category") in _WIRE_ROUTE_TERMINALS and other.get("identity"):
                partners_by_identity[_key(end["identity"])].add(_key(other["identity"]))
            records_by_pin[_symb2_physical_pin(end)].add(row["record_id"])
    text_ids = {}
    for text in texts or []:
        text_ids.setdefault((text.file_id, str(text.handle)), text.text_id)
    return {"partners_by_identity": partners_by_identity, "records_by_pin": records_by_pin,
            "strip_rows": strip_rows_by_endpoint, "text_ids": text_ids}


def _admit_wire_routes(output, data, rows, *, lines, line_groups, audit_ids, page_map,
                       strip_rows_by_endpoint, xml_ranks, texts=None):
    """Add SuperWORKS wire pairs for eligible wire-route records. Only ever appends pairs.

    A record is eligible when both ends are resolved terminals of one audited sheet, neither end
    port is named by a non-discard pair, and the wire's group carries no non-discard pair. The pair
    is built by _wire_pair, the same builder as the line-group path. It is pass only when the wire
    handle exists and touches a port at each end, and no true conflict is present; otherwise review.
    """
    stats = Counter()
    ports_by_key = defaultdict(list)
    for port in data.ports:
        ports_by_key[(port.file_id, port.insert_handle, str(port.port_number))].append(port)
    line_by_key = {}
    for line in lines:
        if not line.source_block_name:
            line_by_key.setdefault((line.file_id, line.handle), line)
    groups_by_id = {group.line_group_id: group for group in line_groups}
    cut_groups = getattr(data, "topology_cut_group_ids", None) or frozenset()
    active_groups = {(pair.sheet_id, pair.line_group_id) for pair in output
                     if pair.status != "discard" and not _is_provisional_half(pair, cut_groups)}
    consumed = _consumed_ports(output, cut_groups)
    provisional_by_port = _provisional_pairs_by_port(output, cut_groups)
    displaced_ids = set()
    symb2_ctx = _symb2_context(rows, data, strip_rows_by_endpoint, texts)
    for row in rows:
        ends = json.loads(row["ends_json"])
        reason, found = _admission_reason(row, ends, audit_ids, ports_by_key, consumed, symb2_ctx)
        if reason is not None:
            row["admission_reason"] = reason
            stats[f"not_admitted:{reason}"] += 1
            continue
        endpoints, end_ports = found
        left, right = endpoints
        symb2_ends = [end for end in ends if end.get("status") == SYMB2_STATUS]
        wire = row.get("wire_handle")
        line = line_by_key.get((row["file_id"], wire)) if wire else None
        if line is not None and line.sheet_id != row["sheet_id"]:
            line = None
        confirmed = line is not None and all(
            any(contact.get("wire_handle") == wire for port in ports for contact in port.wire_contacts)
            for ports in end_ports)
        review = []
        if line is None:
            review.append("wire_geometry_missing")
        elif not confirmed:
            review.append("wire_not_touching_port")
        if symb2_ends:
            # A pin named only by its own INSERT text is never pass in this stage (LOGGEN-3 PIN-1 rule R1).
            review.append("pin_identity_symb2_text_slot")
            if wire is None:
                review.append("no_wire_handle")
        group = None
        line_group_id = None
        coords = None
        origin = "wire_route_record"
        if line is not None:
            gid = "GWSW" + hashlib.sha256(
                f"{line.file_id}:{line.sheet_id}:{line.handle}:{line.line_id}".encode()).hexdigest()[:16]
            group = groups_by_id.get(gid)
            if group is None:
                group = next((g for g in line_groups if g.sheet_id == line.sheet_id
                              and line.line_id in g.member_line_ids and _same_segment(g, line)), None)
            if group is not None and (line.sheet_id, group.line_group_id) in active_groups:
                row["admission_reason"] = "group_has_active_pair"
                stats["not_admitted:group_has_active_pair"] += 1
                continue
            if group is None:
                a, b = (line.start_x, line.start_y), (line.end_x, line.end_y)
                if a > b:
                    a, b = b, a
                group = LineGroup(line_group_id=gid, sheet_id=line.sheet_id, file_id=line.file_id,
                    start_x=a[0], start_y=a[1], end_x=b[0], end_y=b[1], length=line.length,
                    wire_candidate_score=1.0, member_line_ids=[line.line_id], layer_hints=[line.layer],
                    orientation="vertical" if abs(a[0] - b[0]) < 1e-6 else "horizontal" if abs(a[1] - b[1]) < 1e-6 else "diagonal")
                line_groups.append(group)
                groups_by_id[gid] = group
            line_group_id = group.line_group_id
            coords = (group.start_x, group.start_y, group.end_x, group.end_y)
            origin = "metadata_wire_reference" if line_group_id.startswith("GWSW") else "legacy_line_group"
        reasons = sorted({code for endpoint in endpoints for code in endpoint["reason_codes"]})
        conflicts = _true_conflicts(reasons)
        strip_relation = _same_strip_relation(left, right, strip_rows_by_endpoint, xml_ranks)
        new = _wire_pair(pair_id=_id(f"wire-route:{row['record_id']}"), line_group_id=line_group_id,
            sheet_id=row["sheet_id"], file_id=row["file_id"], coords=coords or (None, None, None, None),
            scope_id=line_group_id or row["record_id"], left=left, right=right, origin=origin,
            conflicts=conflicts, strip_relation=strip_relation, page_map=page_map, review_reasons=review)
        new.evidence["sw_wire_route"] = {"record_id": row["record_id"], "source_kind": row["source_kind"],
            "wire_handle": wire, "wire_confirmed": confirmed, "review_reasons": review,
            "identity_source": SYMB2_IDENTITY_SOURCE if symb2_ends else "sw_port",
            "no_wire_handle": wire is None}
        if symb2_ends:
            new.evidence["symb2_text_slot"] = [{
                "identity": end["identity"], "identity_source": SYMB2_IDENTITY_SOURCE,
                "terminal_handle": end["terminal_handle"], "port_number": end["port_number"],
                "label_text": (end.get("symb2") or {}).get("label_text"),
                "slot_text": (end.get("symb2") or {}).get("slot_text"),
                "record_device": (end.get("symb2") or {}).get("record_device"),
                "record_seq": (end.get("symb2") or {}).get("record_seq"),
                "terminal_strip_verdict": _strip_row_verdict(
                    (endpoints[1 - i])["value"], end["identity"], strip_rows_by_endpoint),
            } for i, end in enumerate(ends) if end.get("status") == SYMB2_STATUS]
            stats["admitted:symb2_text_slot"] += 1
        output.append(new)
        # WIRE-BREAK: a provisional legacy pair on a port this wire-route record now pairs is replaced by it.
        for port_id in endpoints[0]["port_ids"] + endpoints[1]["port_ids"]:
            for old in provisional_by_port.get(port_id, ()):
                if id(old) not in displaced_ids:
                    displaced_ids.add(id(old))
                    stats["displaced_provisional"] += 1
        if line_group_id:
            active_groups.add((row["sheet_id"], line_group_id))
        for side, endpoint in (("left", left), ("right", right)):
            for port in endpoint["ports"]:
                data.coverage_observations.append({"port_id": port["port_id"], "sheet_id": row["sheet_id"],
                    "file_id": row["file_id"], "line_group_id": line_group_id,
                    "line_group_origin": origin, "endpoint_side": side,
                    "identity_resolved": True, "wire_touched": bool(endpoint.get("wire_touched")),
                    "network_line_ids": []})
            for port_id in endpoint["port_ids"]:
                consumed[port_id].append((new, side))
        row["admission_status"] = "admitted_pass" if new.status == "pass" else "admitted_review"
        row["admission_reason"] = None
        row["admitted_pair_id"] = new.pair_id
        stats[f"admitted:{new.status}"] += 1
        stats[f"admitted:{new.status}:{new.pair_kind}"] += 1
    if displaced_ids:
        output[:] = [pair for pair in output if id(pair) not in displaced_ids]
    return stats


def _attach_wire_route_conflict(pair, item):
    items = pair.evidence.setdefault("sw_wire_route_conflict", [])
    if not any(old["record_id"] == item["record_id"] and old["kind"] == item["kind"]
               and old["pair_side"] == item["pair_side"] for old in items):
        items.append(item)


def _check_consumed_end(row, ends, index, pair, side, stats, wires_of):
    """Compare one record end with the pair that consumes its port. Returns the verdict for this end.

    Only SuperWORKS terminal identities are compared. Internal component pins carry several naming
    forms for one pin (e.g. "8ID3" beside "8n1505"), so an internal end never yields a conflict.

    - Same-port disagreement: when the pair is review and its own SuperWORKS side identity is exactly
      the record identity, the legacy side value (a numeric candidate) is replaced by that identity;
      otherwise it is recorded as a conflict.
    - Other end: the record's other terminal differs from the pair's other terminal. Recorded as a
      conflict only when the pair is on the same wire; on another wire the port simply carries a second
      wire (fan-out), which is counted but not recorded.
    Nothing here creates a pair.
    """
    end = ends[index]
    identity = end["identity"]
    end_is_terminal = end.get("category") in _WIRE_ROUTE_TERMINALS
    other = "right" if side == "left" else "left"
    sw = (pair.evidence.get("superworks") or {})
    own_value = getattr(pair, f"{side}_value")
    verdicts = set()
    if not end_is_terminal:
        return "unchecked"
    if not _is_blank_side(own_value) and not _identities_agree(identity, own_value):
        sw_side = sw.get(side) or {}
        sw_value = sw_side.get("value")
        if pair.status == "review" and sw_value and _key(sw_value) == _key(identity):
            setattr(pair, f"{side}_value", sw_value)
            if sw_side.get("text_id"):
                setattr(pair, f"{side}_text_id", sw_side["text_id"])
            pair.pair_key = f"{pair.left_value or '?'}->{pair.right_value}"
            pair.evidence.setdefault("sw_wire_route_fix", []).append({"record_id": row["record_id"],
                "side": side, "from_value": own_value, "to_value": sw_value})
            stats["value_fixed"] += 1
            verdicts.add("value_fixed")
        else:
            _attach_wire_route_conflict(pair, {"record_id": row["record_id"], "kind": "same_port_value_differs",
                "pair_side": side, "record_identity": identity, "pair_value": own_value})
            stats["conflict:same_port_value_differs"] += 1
            verdicts.add("conflict")
    if len(ends) == 2:
        other_end = ends[1 - index]
        other_value = getattr(pair, f"{other}_value")
        other_side = sw.get(other) or {}
        if (other_end.get("status") in _WIRE_ROUTE_RESOLVED and other_end.get("category") in _WIRE_ROUTE_TERMINALS
                and other_side.get("category") in _WIRE_ROUTE_TERMINALS and other_end.get("identity")
                and not _is_blank_side(other_value)):
            if _identities_agree(other_end["identity"], other_value):
                verdicts.add("agree")
            elif row.get("wire_handle") in wires_of(pair):
                _attach_wire_route_conflict(pair, {"record_id": row["record_id"], "kind": "other_end_differs",
                    "pair_side": side, "record_identity": identity, "record_other_identity": other_end["identity"],
                    "pair_value": own_value, "pair_other_value": other_value})
                stats["conflict:other_end_differs"] += 1
                verdicts.add("conflict")
            else:
                stats["fanout:other_wire_other_end"] += 1
                verdicts.add("fanout")
        else:
            verdicts.add("unchecked")
    if "conflict" in verdicts:
        return "conflict"
    if "value_fixed" in verdicts:
        return "value_fixed"
    if "fanout" in verdicts:
        return "fanout"
    return "agree" if "agree" in verdicts else "unchecked"


_CONSUMED_STATUS = {"conflict": "consumed_conflict", "value_fixed": "consumed_value_fixed",
                    "fanout": "consumed_fanout", "agree": "consumed_agree", "unchecked": "consumed_unchecked"}


def _reconcile_consumed_wire_routes(rows, consumed, stats, wires_of):
    """Record-level checks for records that were not admitted but have a consumed end (phase-1
    "one end consumed" records). These records never become pairs."""
    for row in rows:
        if row.get("admission_status"):
            continue
        ends = json.loads(row["ends_json"])
        verdicts = []
        for index, end in enumerate(ends):
            if end.get("status") not in _WIRE_ROUTE_RESOLVED:
                continue
            hits = []
            for port_id in end.get("port_ids") or []:
                for pair, side in consumed.get(port_id, []):
                    if not any(known is pair and known_side == side for known, known_side in hits):
                        hits.append((pair, side))
            for pair, side in hits:
                verdicts.append(_check_consumed_end(row, ends, index, pair, side, stats, wires_of))
        if not verdicts:
            continue
        for verdict in ("conflict", "value_fixed", "fanout", "agree", "unchecked"):
            if verdict in verdicts:
                row["admission_status"] = _CONSUMED_STATUS[verdict]
                break
        stats[f"record:{row['admission_status']}"] += 1


def _wire_route_census(rows):
    """Counts of the records that are not integrated (internal component ends) and of cross-page far ends."""
    census = Counter()
    for row in rows:
        ends = json.loads(row["ends_json"])
        census[f"records:{row['source_kind']}"] += 1
        if any(end.get("status") in _WIRE_ROUTE_RESOLVED | {SYMB2_STATUS} and not (end.get("category") or "") for end in ends):
            census["records_with_internal_end"] += 1
        local = next((end for end in ends if end.get("role") == "LOCAL"), None)
        for end in ends:
            if end.get("far_source") != "cross_page":
                continue
            census["cross_page_far_ends"] += 1
            if local is not None and local.get("category") in _WIRE_ROUTE_TERMINALS:
                census["cross_page_local_terminal"] += 1
            status = end.get("status")
            if status == "resolved_by_text":
                # The target did not resolve to one SW port; the record's text stands in for it.
                census["cross_page_text_fallback"] += 1
            elif status != "resolved":
                census["cross_page_far_unresolved"] += 1
            elif not end.get("far_text_identity"):
                census["cross_page_text_absent"] += 1
            elif _identities_agree(end.get("identity"), end.get("far_text_identity")):
                census["cross_page_text_agrees"] += 1
            else:
                census["cross_page_text_differs"] += 1
    return dict(census)


def _run_wire_route_admission(output, data, *, lines, line_groups, audit_ids, page_map,
                              strip_rows_by_endpoint, xml_ranks, sheet_numbers, texts=None):
    """Resolve the wire-route records read by cad_extract, admit eligible ones, reconcile the rest."""
    from dwg_audit.extract.superworks_loggen import build_wire_route_rows
    rows, route_stats = build_wire_route_rows(list(data.wire_route_pages), data, sheet_numbers,
                                              dict(data.wire_route_failures))
    admission = _admit_wire_routes(output, data, rows, lines=lines, line_groups=line_groups, audit_ids=audit_ids,
                                   page_map=page_map, strip_rows_by_endpoint=strip_rows_by_endpoint, xml_ranks=xml_ranks,
                                   texts=texts)
    consumed_stats = Counter()
    handle_by_line = {line.line_id: line.handle for line in lines}
    members_by_group = {(group.sheet_id, group.line_group_id): group.member_line_ids for group in line_groups}

    def wires_of(pair):
        """Wire handles a pair is drawn on: its own wire-route record, or its line group's members."""
        wires = set()
        route = (pair.evidence or {}).get("sw_wire_route") or {}
        if route.get("wire_handle"):
            wires.add(route["wire_handle"])
        for line_id in members_by_group.get((pair.sheet_id, pair.line_group_id), []):
            if line_id in handle_by_line:
                wires.add(handle_by_line[line_id])
        return wires

    _reconcile_consumed_wire_routes(rows, _consumed_ports(output, getattr(data, "topology_cut_group_ids", None) or frozenset()), consumed_stats, wires_of)
    for row in rows:
        row.setdefault("admission_status", None)
        if row["admission_status"] is None:
            row["admission_status"] = "not_admitted"
    data.wire_route_stats = {**route_stats,
        "admission": {**dict(admission), **dict(consumed_stats)},
        "census": _wire_route_census(rows),
        "status_counts": dict(Counter(row["admission_status"] for row in rows))}
    data.wire_route_rows = rows


DEVICE_INTERNAL_DISCARD = "device_internal"


def _pair_end(pair, side, ports_by_id):
    """The device-internal view of one SuperWORKS side: category, label, identity and port ids.

    A side with a SuperWORKS port takes its category and label from that port. An unregistered INSERT end has no
    port: its label is the device name its own record names (symb2_text_slot), and it is marked unregistered.
    """
    evidence = pair.evidence or {}
    end = (evidence.get("superworks") or {}).get(side) or {}
    port_ids = list(end.get("port_ids") or [])
    port = next((ports_by_id[port_id] for port_id in port_ids if port_id in ports_by_id), None)
    if port is not None:
        # The port's own identity (label + pin tail), as DEV-INT reads it; the pair value of an ordinary pair can be
        # a bare number ("719") that carries no device label.
        identity = port.endpoint_identity or end.get("value") or getattr(pair, f"{side}_value") or ""
        label, resolved = label_of({"label": port.label})
        return {"identity": identity, "category": port.category or "", "label": label, "label_resolved": resolved,
                "unregistered": False, "port_ids": port_ids}
    identity = getattr(pair, f"{side}_value") or end.get("value") or ""
    slot = next((item for item in evidence.get("symb2_text_slot") or [] if item.get("identity") == identity), None)
    unregistered = bool(not port_ids and end.get("identity_source") == SYMB2_IDENTITY_SOURCE and slot)
    device = (slot or {}).get("record_device") or ""
    return {"identity": identity, "category": end.get("category") or "", "label": device if unregistered else "",
            "label_resolved": bool(unregistered and device), "unregistered": unregistered, "port_ids": port_ids}


def _discard_device_internal_pairs(output, data):
    """DEV-INT-DISCARD: a non-discard pair the device-internal rule accepts becomes a silent discard.

    The rule is device_internal_verdict, the same function the DEV-INT links use. Pass and review pairs alike are
    discarded; the evidence records discard_reason and the decision. Only pairs that already carry SuperWORKS sides
    are read. Returns counters: discarded:<status> and discarded:<status>:<pair_kind>, and the verdicts of the
    pairs with a device-terminal side that were kept, so the unrecognised remainder can be read off the summary.
    """
    ports_by_id = {port.record_id: port for port in data.ports}
    stats = Counter()
    for index, pair in enumerate(output):
        if pair.status == "discard" or not (pair.evidence or {}).get("superworks"):
            continue
        ends = {side: _pair_end(pair, side, ports_by_id) for side in ("left", "right")}
        verdicts = {}
        for terminal, other in (("left", "right"), ("right", "left")):
            verdicts[terminal] = device_internal_verdict(ends[terminal], ends[other])
            if verdicts[terminal] == DEVICE_INTERNAL:
                break
        hit = next((side for side in ("left", "right") if verdicts.get(side) == DEVICE_INTERNAL), None)
        if hit is None:
            for side in ("left", "right"):
                if ends[side]["category"] == "装置端子":
                    stats[f"kept:{verdicts[side]}"] += 1
            continue
        terminal, other = ends[hit], ends["right" if hit == "left" else "left"]
        evidence = copy.deepcopy(pair.evidence or {})
        evidence["discard_reason"] = DEVICE_INTERNAL_DISCARD
        evidence["native_resolution_state"] = "EXCLUDED"
        evidence["device_internal_discard"] = {
            "status_before": pair.status, "pair_kind": pair.pair_kind, "terminal_side": hit,
            "terminal_identity": terminal["identity"], "terminal_label": terminal["label"],
            "terminal_port_ids": terminal["port_ids"], "other_identity": other["identity"],
            "other_category": other["category"], "other_label": other["label"],
            "other_port_ids": other["port_ids"], "other_unregistered": other["unregistered"],
            "rule": "device_internal_verdict"}
        output[index] = replace(pair, status="discard", evidence=evidence,
            rationale=f"{DEVICE_INTERNAL_DISCARD}: {terminal['identity']} 与本装置内部元件 {other['identity']} 相连，不进入匹配")
        stats[f"discarded:{pair.status}"] += 1
        stats[f"discarded:{pair.status}:{pair.pair_kind}"] += 1
    return dict(stats)


def _walk_marks(data, sheet_id):
    """Symbol marks of a sheet: registered ports and unregistered SYMB2 TERMPOINTs, with the device-internal view."""
    marks = []
    for port in data.ports:
        if port.sheet_id != sheet_id:
            continue
        label, resolved = label_of({"label": port.label})
        marks.append({"key": port.symbol_id, "rid": port.record_id,
                      "segment": (float(port.start_x), float(port.start_y), float(port.end_x), float(port.end_y)),
                      "other": {"category": port.category or "", "label": label, "label_resolved": resolved,
                                "unregistered": False, "identity": port.endpoint_identity or ""}})
    for block in data.unregistered_symb2:
        if block.get("sheet_id") != sheet_id:
            continue
        key = f"SW:{block.get('file_id')}:{sheet_id}:{block.get('instance_path')}"
        for termpoint in block.get("termpoints") or []:
            (ax, ay), (bx, by) = termpoint.get("a") or (0.0, 0.0), termpoint.get("b") or (0.0, 0.0)
            marks.append({"key": key, "rid": f"{block.get('record_id')}#{termpoint.get('number')}",
                          "segment": (float(ax), float(ay), float(bx), float(by)),
                          "other": {"category": "", "label": block.get("label_value") or "",
                                    "label_resolved": bool(block.get("label_resolved")), "unregistered": True,
                                    "identity": ""}})
    return marks


def _discard_walked_half_pairs(output, data, lines, line_groups, texts=(), block_rows=()):
    """WIRE-BREAK (rounds 24-25): a one-sided pair on a cut line group, whose resolved end is a device terminal, becomes
    a device-internal discard when the wire walked from its open end reaches only internal pins of the same device.

    The walk (superworks_wire_walk) follows corners and T junctions over model lines and the visible block lines of
    element instances, and stops at every SW symbol mark (no connection through a terminal or an element pin).
    Every symbol reached must be internal to the terminal's device:
    - a pin with a resolved label: device_internal_verdict must give DEVICE_INTERNAL (rule wire_walk_internal);
    - a pin with an unresolved label (an SW internal element or coil, or an unregistered block pin): accepted only
      inside the device frame, which must be unique (rule wire_walk_internal_frame). The frame holds every terminal
      port and carries the device label text; the walked wire and the reached pins must lie inside it.
    Any reached terminal, other-device terminal, external pin or object outside the frame keeps the pair as it was.
    Returns counters walk_discarded:<status> and walk_kept:<reason>.
    """
    stats = Counter()
    if not line_groups or not getattr(data, "topology_cut_group_ids", None):
        return dict(stats)
    groups = {group.line_group_id: group for group in line_groups}
    model = walk_segment_index(lines)
    walkable = defaultdict(list, {sheet: list(segs) for sheet, segs in model.items()})
    for sheet_id, x1, y1, x2, y2 in block_rows:
        walkable[sheet_id].append((float(x1), float(y1), float(x2), float(y2)))
    text_rows = defaultdict(list)
    for text in texts:
        if text.text and str(text.text).strip():
            text_rows[text.sheet_id].append((str(text.normalized_text or text.text).strip(),
                                             (float(text.bbox_min_x), float(text.bbox_min_y),
                                              float(text.bbox_max_x), float(text.bbox_max_y))))
    frames = {}
    marks_by_sheet = {}
    ports_by_id = {port.record_id: port for port in data.ports}
    for index, pair in enumerate(output):
        if pair.status == "discard" or not (pair.evidence or {}).get("superworks"):
            continue
        if pair.line_group_id not in data.topology_cut_group_ids or bool(pair.left_value) == bool(pair.right_value):
            continue
        resolved_side = "left" if pair.left_value else "right"
        terminal = _pair_end(pair, resolved_side, ports_by_id)
        if terminal["category"] != "装置端子":
            continue
        group = groups.get(pair.line_group_id)
        if group is None:
            stats["walk_kept:no_line_group"] += 1
            continue
        terminal_ports = [ports_by_id[port_id] for port_id in terminal["port_ids"] if port_id in ports_by_id]
        terminal_keys = {port.symbol_id for port in terminal_ports}
        terminal_points = [((port.start_x + port.end_x) / 2.0, (port.start_y + port.end_y) / 2.0)
                           for port in terminal_ports]
        ends = [(float(group.start_x), float(group.start_y)), (float(group.end_x), float(group.end_y))]

        def at_terminal(point):
            return any(mark_touches(point, (port.start_x, port.start_y, port.end_x, port.end_y))
                       for port in terminal_ports)

        far = [end for end in ends if not at_terminal(end)]
        if len(far) != 1 or not any(at_terminal(end) for end in ends):
            stats["walk_kept:no_open_end"] += 1
            continue
        if pair.sheet_id not in marks_by_sheet:
            marks_by_sheet[pair.sheet_id] = _walk_marks(data, pair.sheet_id)
        marks = marks_by_sheet[pair.sheet_id]
        by_rid = {mark["rid"]: mark for mark in marks}
        walk_marks = [(mark["key"], mark["rid"], mark["segment"]) for mark in marks]
        visited, end_points, reached_keys = walk_wire(walkable.get(pair.sheet_id, []), far[0], walk_marks)
        reached = [by_rid[rid] for _, rid in sorted(reached_keys)
                   if rid in by_rid and by_rid[rid]["key"] not in terminal_keys]
        if not reached:
            stats["walk_kept:nothing_reached"] += 1
            continue
        blocked = None
        unresolved = []
        for mark in reached:
            other = mark["other"]
            if other["category"] in ("端子", "装置端子") or (other["category"] and not other["unregistered"]
                                                           and other["category"] not in ("内部元件", "线圈")):
                blocked = f"other_end_category:{other['category']}"
                break
            if not other["label_resolved"]:
                if other["category"] in ("内部元件", "线圈") or other["unregistered"]:
                    unresolved.append(mark)
                    continue
                blocked = "other_label_unresolved"
                break
            verdict = device_internal_verdict(terminal, other)
            if verdict != DEVICE_INTERNAL:
                blocked = verdict
                break
        if blocked is None and unresolved:
            if pair.sheet_id not in frames:
                frames[pair.sheet_id] = rectangles(model.get(pair.sheet_id, []))
            frame = device_frame(frames[pair.sheet_id], terminal["label"], terminal_points,
                                 text_rows.get(pair.sheet_id, []))
            if frame is None:
                blocked = "no_unique_frame"
            elif not all(inside_rect(point, frame) for point in end_points):
                blocked = "walk_leaves_frame"
            elif not all(inside_rect((m["segment"][0], m["segment"][1]), frame)
                         and inside_rect((m["segment"][2], m["segment"][3]), frame) for m in reached):
                blocked = "reached_outside_frame"
        if blocked is not None:
            stats["walk_kept:" + blocked] += 1
            continue
        rule = "wire_walk_internal_frame" if unresolved else "wire_walk_internal"
        evidence = copy.deepcopy(pair.evidence or {})
        evidence["discard_reason"] = DEVICE_INTERNAL_DISCARD
        evidence["native_resolution_state"] = "EXCLUDED"
        evidence["device_internal_discard"] = {
            "status_before": pair.status, "pair_kind": pair.pair_kind, "terminal_side": resolved_side,
            "terminal_identity": terminal["identity"], "terminal_label": terminal["label"],
            "terminal_port_ids": terminal["port_ids"], "other_identity": "", "other_category": "",
            "other_label": "", "other_port_ids": [], "other_unregistered": False, "rule": rule,
            "walk_reached": sorted(mark["rid"] for mark in reached), "walk_segments": len(visited),
            "walk_unresolved": sorted(mark["rid"] for mark in unresolved)}
        output[index] = replace(pair, status="discard", evidence=evidence,
            rationale=f"{DEVICE_INTERNAL_DISCARD}: {terminal['identity']} 的导线沿线网络只到达本装置内部引脚（{rule}），不进入匹配")
        stats[f"walk_discarded:{pair.status}"] += 1
        if unresolved:
            stats[f"walk_discarded_frame:{pair.status}"] += 1
    return dict(stats)


def extract_superworks_pairs(data: SuperworksData, *, pages, texts, lines, line_groups, pairs, table_mappings,
                            wire_route_sheet_numbers=None, block_rows=None, native_only=False, shared_context=None):
    if data is None:
        return pairs,table_mappings,[]
    started=time.perf_counter()
    output=list(pairs)
    ledger=[]
    page_map={p.sheet_id:p for p in pages}
    audit_ids={p.sheet_id for p in pages if p.audit_disposition not in ("skip_stable","classify_only") and p.audit_role!="skip"}
    ports_by_sheet=defaultdict(list)
    for port in data.ports:
        if port.sheet_id in audit_ids:
            ports_by_sheet[port.sheet_id].append(port)
    pairs_by_group=defaultdict(list)
    for pair in pairs:
        pairs_by_group[(pair.sheet_id,pair.line_group_id)].append(pair)
    text_map={t.text_id:t for t in texts}
    indices={sid:PortIndex(ports) for sid,ports in ports_by_sheet.items()}
    networks={}
    represented={line_id for group in line_groups for line_id in group.member_line_ids}
    legacy_groups=list(line_groups)
    groups_by_member=defaultdict(list)
    for group in legacy_groups:
        for member in group.member_line_ids:
            groups_by_member[member].append(group)
    supplemental_for=defaultdict(list)
    if shared_context is not None and not native_only:
        supplemental_for.update(shared_context.supplemental_for)
    strip_rows_by_endpoint = _strip_scope_index(data)
    xml_ranks = {_key(item.get("name", "")): item.get("rank")
                 for item in data.dictionary.get("strip_order", []) if item.get("name")}
    contacts={(p.sheet_id,c["wire_handle"]) for p in data.ports for c in p.wire_contacts}
    source_handles = {line.line_id: line.handle for line in lines}

    def observe(group, state, left=None, right=None, reasons=()):
        handles = sorted({source_handles.get(member, member) for member in group.member_line_ids})
        key = f"{group.file_id}:{group.sheet_id}:wire:{','.join(handles)}:{group.start_x:.9f},{group.start_y:.9f}:{group.end_x:.9f},{group.end_y:.9f}"
        data.resolution_observations.append({"record_id": _id(key), "object_key": key,
            "file_id": group.file_id, "sheet_id": group.sheet_id, "line_group_id": group.line_group_id,
            "state": state, "reason_codes": list(reasons), "source_handles": handles,
            "left": left, "right": right, "coords": [group.start_x, group.start_y, group.end_x, group.end_y]})
    # Preserve every legacy group. Supplemental groups are one-to-one source-wire
    # references, not a regrouping of old geometry or an inferred internal union.
    for line in lines:
        if line.sheet_id not in indices or line.source_block_name:
            continue
        if (line.sheet_id,line.handle) not in contacts:
            continue
        a,b=(line.start_x,line.start_y),(line.end_x,line.end_y)
        if a>b:
            a,b=b,a
        producers=groups_by_member.get(line.line_id,[])
        exact=[g for g in producers if min(
            max(math.hypot(g.start_x-a[0],g.start_y-a[1]),math.hypot(g.end_x-b[0],g.end_y-b[1])),
            max(math.hypot(g.end_x-a[0],g.end_y-a[1]),math.hypot(g.start_x-b[0],g.start_y-b[1])))<1e-5]
        if exact:
            continue
        supplemental=LineGroup(line_group_id="GWSW"+hashlib.sha256(f"{line.file_id}:{line.sheet_id}:{line.handle}:{line.line_id}".encode()).hexdigest()[:16],
            sheet_id=line.sheet_id,file_id=line.file_id,start_x=a[0],start_y=a[1],end_x=b[0],end_y=b[1],
            length=line.length,wire_candidate_score=1.0,member_line_ids=[line.line_id],layer_hints=[line.layer],
            orientation="vertical" if abs(a[0]-b[0])<1e-6 else "horizontal" if abs(a[1]-b[1])<1e-6 else "diagonal")
        line_groups.append(supplemental)
        for producer in producers:
            supplemental_for[(producer.sheet_id,producer.line_group_id)].append(supplemental.line_group_id)
    if native_only and shared_context is not None:
        shared_context.supplemental_for = dict(supplemental_for)

    def replace_claims(old,new,key):
        nonlocal output
        original_still_present = len(old)==1 and any(item is old[0] for item in output)
        removed={id(p) for p in old}
        output=[p for p in output if id(p) not in removed]
        if len(old)==len(new)==1 and original_still_present:
            new[0].pair_id=old[0].pair_id
        output.extend(new)
        for before in old or [None]:
            after=new[0] if len(new)==1 else None
            category=_category(before,after) if after else ("A" if before is None else "F")
            ledger.append({"element_key":key,"category":category,
                           "reason":"metadata_and_geometry_conflict" if category=="D" else "validated_superworks_replacement",
                           "old_pair":asdict(before) if before else None,"new_pairs":[asdict(p) for p in new]})

    split_groups=[]
    for group in line_groups:
        group_key = (group.sheet_id, group.line_group_id)
        if shared_context is not None and not native_only and group_key in shared_context.closed_groups:
            continue
        index=indices.get(group.sheet_id)
        if index is None:
            observe(group, "INCOMPLETE", reasons=["no_sw_ports"])
            continue
        endpoints=[]
        cached = shared_context.endpoint_cache.get(group_key) if shared_context is not None else None
        for side_index, (x,y) in enumerate(((group.start_x,group.start_y),(group.end_x,group.end_y))):
            if cached is not None:
                endpoints.append(cached[side_index])
                continue
            direct=index.find(x,y)
            if direct:
                endpoints.append(_endpoint(direct))
            else:
                if group.sheet_id not in networks:
                    members={line_id for g in line_groups if g.sheet_id==group.sheet_id for line_id in g.member_line_ids}
                    networks[group.sheet_id]=WireNetwork([l for l in lines if l.sheet_id==group.sheet_id],
                        [d for d in data.connect_dots if d.sheet_id==group.sheet_id],members)
                reachable=networks[group.sheet_id].reachable(x,y,index,set(group.member_line_ids))
                endpoints.append(_endpoint([p for p,_ in reachable],sorted({l for _,path in reachable for l in path})))
        if shared_context is not None:
            shared_context.endpoint_cache[group_key] = endpoints
        left,right=endpoints
        old=pairs_by_group.get((group.sheet_id,group.line_group_id),[])
        origin = "metadata_wire_reference" if group.line_group_id.startswith("GWSW") else "legacy_line_group"
        for side, endpoint in (("left", left), ("right", right)):
            if not endpoint:
                continue
            for port in endpoint["ports"]:
                data.coverage_observations.append({"port_id": port["port_id"], "sheet_id": group.sheet_id,
                    "file_id": group.file_id, "line_group_id": group.line_group_id,
                    "line_group_origin": origin, "endpoint_side": side,
                    "identity_resolved": bool(endpoint.get("value")),
                    "wire_touched": bool(endpoint.get("wire_touched")),
                    "network_line_ids": endpoint.get("network_line_ids", [])})
        if not left and not right:
            observe(group, "INCOMPLETE", reasons=["no_sw_endpoint"])
            continue
        reasons=sorted({r for endpoint in endpoints if endpoint for r in endpoint["reason_codes"]})
        conflicts=_true_conflicts(reasons)
        self_reason=_self_connection_reason(left,right)
        if self_reason:
            # F1: both ends resolve to one logical identity.  No production pair
            # is emitted and no cross-page / duplicate / cardinality rule sees
            # it; the group is recorded in the SW diagnostics instead.
            spans=_spans_one_symbol(left,right)
            observe(group, "EXCLUDED" if spans else "AMBIGUOUS", left, right, [SELF_CONNECTION_REASONS[self_reason]])
            data.conflict_observations.append({
                "kind":"self_connection","reason_code":SELF_CONNECTION_REASONS[self_reason],
                "detail":_self_connection_detail(left,right),
                "identity":left.get("value") or right.get("value"),
                "file_id":group.file_id,"sheet_id":group.sheet_id,
                "line_group_id":group.line_group_id,"line_group_origin":origin,
                "left_symbol_id":left.get("symbol_id"),"right_symbol_id":right.get("symbol_id"),
                "left_port_ids":left.get("port_ids"),"right_port_ids":right.get("port_ids"),
                "left_port_number":left.get("port_number"),"right_port_number":right.get("port_number"),
                "left_coord":[group.start_x,group.start_y],"right_coord":[group.end_x,group.end_y],
                "split_at_port":spans,
                "split_result":("symbol_internal_span_retired" if spans else "kept_as_wire_reference"),
                "member_line_ids":list(group.member_line_ids),
            })
            if spans:
                split_groups.append(group)
            continue
        if not left or not right or not left.get("value") or not right.get("value"):
            observe(group, "CONFIRMED_CONFLICT" if conflicts else "INCOMPLETE", left, right,
                    conflicts or reasons or ["endpoint_identity_missing"])
            for before in old:
                evidence=copy.deepcopy(before.evidence)
                evidence["superworks"]={"source":"superworks","left":left,"right":right,
                    "partial":True,"line_group_origin":origin}
                if conflicts:
                    evidence["sw_conflicts"]=sorted(set(evidence.get("sw_conflicts", [])) | set(conflicts))
                replace_claims([before],[replace(before,evidence=evidence)],f"wire:{group.sheet_id}:{group.line_group_id}")
            continue
        conflicts=sorted(set(conflicts))
        strip_relation=_same_strip_relation(left,right,strip_rows_by_endpoint,xml_ranks)
        if (not left.get("wire_touched") or not right.get("wire_touched")) and not conflicts:
            observe(group, "AMBIGUOUS", left, right, reasons or ["physical_wire_contact_unverified"])
            # The wire graph or old line group is not sufficient proof when neither
            # metadata port has a source-wire contact. Keep old producer output.
            for before in old:
                evidence=copy.deepcopy(before.evidence)
                evidence["superworks"]={"source":"superworks","left":left,"right":right,
                    "validation_only":True,"line_group_origin":origin}
                if conflicts:
                    evidence["sw_conflicts"]=sorted(set(evidence.get("sw_conflicts", [])) | set(conflicts))
                replace_claims([before],[replace(before,evidence=evidence)],f"wire:{group.sheet_id}:{group.line_group_id}")
            continue
        new=_wire_pair(pair_id=_id(f"wire:{group.sheet_id}:{group.line_group_id}"),line_group_id=group.line_group_id,
            sheet_id=group.sheet_id,file_id=group.file_id,coords=(group.start_x,group.start_y,group.end_x,group.end_y),
            scope_id=group.line_group_id,left=left,right=right,origin=origin,conflicts=conflicts,
            strip_relation=strip_relation,page_map=page_map)
        observe(group, "CONFIRMED_CONFLICT" if conflicts else "RESOLVED", left, right, conflicts)
        replace_claims(old,[new],f"wire:{group.sheet_id}:{group.line_group_id}")

    # F1: a wire drawn across one symbol has its span split at the port.  Both
    # halves are degenerate, so the group is retired instead of being kept as a
    # wire; the split is recorded in the SW diagnostics above.
    if split_groups:
        dropped={id(group) for group in split_groups}
        line_groups[:]=[group for group in line_groups if id(group) not in dropped]

    # A shifted/merged legacy group may contain several original wires. Retire
    # its claim only when the source-wire replacements resolve both identities;
    # otherwise retain the legacy claim and its explicit physical discrepancies.
    for (sid,gid),supplement_ids in supplemental_for.items():
        replacement=[p for p in output if p.sheet_id==sid and p.line_group_id in supplement_ids
                     and p.evidence.get("source")=="superworks"]
        if not replacement or not all(p.left_value and p.right_value for p in replacement):
            continue
        old_claims=[p for p in output if p.sheet_id==sid and p.line_group_id==gid]
        if not old_claims:
            continue
        output=[p for p in output if p not in old_claims]
        for before in old_claims:
            ledger.append({"element_key":f"wire:{sid}:{gid}","category":"B", "reason":"legacy_group_geometry_disagrees_with_source_wires",
                           "old_pair":asdict(before),"new_pairs":[asdict(p) for p in replacement]})

    sw_mappings=defaultdict(list)
    replaced_row_keys=set()
    membership=StripMembership(data)
    existing_native_rows = {p.evidence.get("superworks", {}).get("row_id") for p in pairs
        if (p.evidence or {}).get("source") == "superworks"} if shared_context is not None and not native_only else set()
    for row in data.strip_rows:
        if row.sheet_id not in audit_ids:
            continue
        if row.record_id in existing_native_rows:
            native = [p for p in output if p.evidence.get("superworks", {}).get("row_id") == row.record_id]
            old = [p for p in pairs if (p.evidence or {}).get("source") != "superworks"
                and p.sheet_id == row.sheet_id and p.pair_kind == "table_mapping"
                and (p.evidence.get("table_mapping") or {}).get("middle_text_id") == row.row.get("text_id")
                and (p.evidence.get("table_mapping") or {}).get("header_text_id") == row.header.get("text_id")]
            if old:
                remove_ids = {id(p) for p in old}
                output = [p for p in output if id(p) not in remove_ids]
                for before in old:
                    ledger.append({"element_key": f"strip:{row.record_id}", "category": "B",
                        "reason": "native_row_supersedes_fallback", "old_pair": asdict(before),
                        "new_pairs": [asdict(p) for p in native]})
            replaced_row_keys.add((row.sheet_id, row.header.get("text_id"), row.row.get("text_id")))
            continue
        row_id=row.row.get("text_id")
        header_id=row.header.get("text_id")
        key=(row.sheet_id,header_id,row_id)
        new=[]
        for connection in row.connections:
            value=normalize(connection.get("value",""))
            if not value:
                continue
            reasons=list(row.reason_codes)
            if not row_id or not header_id or not connection.get("text_id"):
                reasons.append("strip_text_not_extracted")
            # Destination lists are represented as independent mappings, never a fabricated union.
            values=[v for v in (_clean_sw_endpoint_value(p) for p in re.split(r"[,，]",value)) if v]
            for destination in values:
                row_number=int(row.row.get("normalized")) if row.row.get("normalized", "").isdigit() else None
                strip_scope=(row.file_id,row.header.get("handle") or header_id)
                # F4: a destination on this very strip header is a same-row
                # short/series bridge, not an ordinary terminal mapping.
                same_strip_destination=any(scope==strip_scope
                    for scope,_ in strip_rows_by_endpoint.get(_key(destination),[]))
                side=connection["side"]
                # F1: only the connection's own side carries the endpoint, exactly as the
                # legacy TableExtractor writes it (left-side rows: left filled, right empty).
                other_side="right" if side=="left" else "left"
                mapping={"mapping_mode":"terminal_header_table","sheet_id":row.sheet_id,"file_id":row.file_id,
                    "header_prefix":row.validation.get("strip_name") or row.header.get("normalized"),"header_text_id":header_id,
                    "header_handle":row.header.get("handle"),"header_coord":[row.header.get("x"),row.header.get("y")],"row_number":row_number,
                    "middle_value":row.row.get("normalized"),"middle_text_id":row_id,"middle_coord":[row.row.get("x"),row.row.get("y")],
                    "logical_endpoint":row.endpoint_identity,"row_number_sequence_valid":True,
                    "endpoint_column_authority":"superworks_reciprocal_row_reference","sw_row_id":row.record_id,
                    f"{side}_value":destination,f"{side}_text_id":connection.get("text_id"),
                    f"{side}_coord":[connection.get("x"),connection.get("y")],
                    f"{other_side}_value":None,f"{other_side}_text_id":None,f"{other_side}_coord":None,
                    "has_shuoming_column":False,"shuoming_text_id":None,
                    "column_roles":{"left":"terminal_endpoint" if side=="left" else "empty","middle":"row_number",
                    "right":"terminal_endpoint" if side=="right" else "empty","description":"empty"},
                    "sw_branch":connection["branch"],"sw_side":connection["side"],
                    "endpoint_style":connection.get("style"),
                    "same_strip_destination":same_strip_destination,
                    "scope_key":f"{row.file_id}:{row.header.get('handle') or header_id}"}
                conflicts=_true_conflicts(reasons)
                sw_mappings[row.sheet_id].append(mapping)
                complete=bool(row_id and header_id and connection.get("text_id") and row_number is not None)
                new.append(Pair(pair_id=_id(f"{row.record_id}:{side}:{connection['branch']}:{destination}"),line_group_id=None,
                    sheet_id=row.sheet_id,file_id=row.file_id,selected_pair_candidate_id=None,
                    left_value=row.endpoint_identity,right_value=destination,confidence=.99 if complete and not conflicts else .5,
                    status="review" if not complete or conflicts else "pass",confidence_bucket="review" if not complete or conflicts else "high",
                    rationale="SuperWORKS reciprocal terminal-strip row and connection references",pair_kind="table_mapping",
                    left_text_id=row_id,right_text_id=connection.get("text_id"),left_coord_x=row.row.get("x"),left_coord_y=row.row.get("y"),
                    right_coord_x=connection.get("x"),right_coord_y=connection.get("y"),pair_key=f"{row.endpoint_identity}->{destination}",
                    evidence={"source":"superworks","pair_kind":"table_mapping",
                              "native_resolution_state":"CONFIRMED_CONFLICT" if conflicts else "RESOLVED" if complete else "INCOMPLETE",
                              "structured_source":"table_mapping" if complete and not conflicts else None,
                              "table_mapping":mapping,"sw_conflicts":conflicts,
                              "sw_validation_reasons":sorted(set(reasons)),
                              "view_scope":_view_scope("terminal_strip",file_id=row.file_id,sheet_id=row.sheet_id,
                                  view_key=f"{row.file_id}:{row.sheet_id}:strip:{row.header.get('handle') or header_id}",
                                  scope_key=f"{row.file_id}:{row.header.get('handle') or header_id}",
                                  record_id=row.record_id,page=page_map.get(row.sheet_id)),
                              "superworks":{"source":"superworks","row_id":row.record_id,
                                  "header_handle":row.header.get("handle"),"header_text_id":header_id,
                                  "row_handle":row.row_handle,"row_text_id":row_id,
                                  "connection_handle":connection.get("handle"),"connection_text_id":connection.get("text_id"),
                                  "side":side,"branch":connection["branch"],"endpoint_style":connection.get("style"),
                                  "validation":row.validation},
                              "ordinary_pair_eligible":False,"electrical_union_eligible":False}))
                # M2: a connection to another terminal-strip identity carries the F3 same-strip /
                # cross-strip contract, exactly as a terminal-terminal wire pair does.
                new[-1].evidence.update(_table_mapping_strip_fields(membership, row.endpoint_identity, destination))
        if new:
            old=[p for p in pairs if p.sheet_id==row.sheet_id and p.pair_kind=="table_mapping"
                 and (p.evidence.get("table_mapping") or {}).get("middle_text_id")==row_id
                 and (p.evidence.get("table_mapping") or {}).get("header_text_id")==header_id]
            replace_claims(old,new,f"strip:{row.record_id}")
            replaced_row_keys.add(key)
    mappings=copy.deepcopy(table_mappings)
    for item in mappings:
        if shared_context is not None and item.get("source") == "superworks":
            continue
        item["mappings"]=[m for m in item.get("mappings",[]) if (item.get("sheet_id") or m.get("sheet_id"),m.get("header_text_id"),m.get("middle_text_id")) not in replaced_row_keys]
    for sid,rows in sw_mappings.items():
        mappings.append({"sheet_id":sid,"source":"superworks","mappings":rows})

    group_by_id={group.line_group_id:group for group in line_groups}
    existing_native_parts = {(p.file_id, p.sheet_id, p.evidence.get("superworks", {}).get("connection_handle")) for p in pairs
        if _is_sw_component_row(p)} if shared_context is not None and not native_only else set()
    line_id_by_handle = {(line.file_id, line.sheet_id, line.handle): line.line_id for line in lines}
    for label in data.connect_labels:
        if label.sheet_id not in audit_ids:
            continue
        if (label.file_id, label.sheet_id, label.text.get("handle")) in existing_native_parts:
            continue
        old=[p for p in pairs if p.sheet_id==label.sheet_id and p.pair_kind=="component_mapping"
             and label.text.get("text_id") in (p.left_text_id,p.right_text_id)]
        true_conflicts=_true_conflicts(label.reason_codes)
        if not label.endpoint_identity or label.reason_codes:
            data.resolution_observations.append({"record_id": _id(f"connect:{label.record_id}"),
                "object_key": f"connect:{label.record_id}", "file_id": label.file_id, "sheet_id": label.sheet_id,
                "line_group_id": None, "state": "CONFIRMED_CONFLICT" if true_conflicts else "INCOMPLETE",
                "reason_codes": true_conflicts or list(label.reason_codes) or ["component_pin_unresolved"],
                "left": {"value": label.endpoint_identity}, "right": label.text,
                "coords": [label.start_x, label.start_y, label.end_x, label.end_y],
                "source_handles": [label.line_handle], "connect_label_id": label.record_id})
            for p in old:
                current=next((item for item in output if item.pair_id==p.pair_id),p)
                evidence=copy.deepcopy(current.evidence)
                evidence.setdefault("superworks_constraints",[]).append({"source":"superworks","connect_label_id":label.record_id,
                    "reason_codes":label.reason_codes,"true_conflicts":true_conflicts})
                if true_conflicts:
                    evidence["sw_conflicts"]=sorted(set(evidence.get("sw_conflicts",[]))|set(true_conflicts))
                index=output.index(current)
                output[index]=replace(current,evidence=evidence)
            continue
        values=[v for v in (_clean_sw_endpoint_value(p) for p in re.split(r"[,，]",label.text.get("value",""))) if v]
        part=next(p for p in data.part_instances if p.record_id==label.part_id)
        part_ports=[port for port in part.ports if str(port.get("port_number"))==str(label.port_number)
                    and port.get("endpoint_identity")==label.endpoint_identity]
        port=part_ports[0] if len(part_ports)==1 else {}
        support_line_id=line_id_by_handle.get((label.file_id, label.sheet_id, label.line_handle))
        producer_groups=[g for g in groups_by_member.get(support_line_id,[]) if support_line_id] if support_line_id else []
        line_group_id=producer_groups[0].line_group_id if len(producer_groups)==1 else (old[0].line_group_id if old else None)
        disputed=_legacy_pairs_on_label_anchor_with_other_port(old,label,group_by_id)
        if disputed:
            data.conflict_observations.append({"kind":"connect_line_port_disagreement",
                "reason_code":"connect_line_port_disagrees_with_legacy","connect_label_id":label.record_id,
                "sheet_id":label.sheet_id,"file_id":label.file_id,"text_id":label.text.get("text_id"),
                "sw_port_number":label.port_number,"sw_connect_line_handle":label.line_handle,
                "legacy_pair_ids":[p.pair_id for p in disputed],
                "legacy_port_numbers":[p.evidence.get("component_port") for p in disputed]})
            continue
        new=[]
        for destination in values:
            evidence=copy.deepcopy(old[0].evidence) if old else {}
            evidence.update(structured_source="component_mapping",
                native_resolution_state="RESOLVED" if (port.get("pin") or {}).get("independent_verification") else "AMBIGUOUS",
                component_submode="superworks_connect_line_port",logical_endpoint=label.endpoint_identity,
                external_endpoint=destination,external_endpoint_raw=label.text.get("value"),
                external_endpoint_split=destination,external_endpoint_text_id=label.text.get("text_id"),
                component_body=part.block_name,component_body_text_id=part.label.get("text_id"),
                component_port=label.port_number,component_port_text_id=(port.get("pin") or {}).get("text_id"),
                # F4d: a pin resolved only by strip_reverse_corroboration is never an independent check.
                pin_resolution_method=(port.get("pin") or {}).get("pin_resolution_method") or (port.get("pin") or {}).get("resolution_method"),
                independent_pin_verification=bool((port.get("pin") or {}).get("independent_verification", False)),
                component_block_name=part.block_name,line_group_id=line_group_id,
                supporting_line_ids=[support_line_id] if support_line_id else [],
                ordinary_pair_eligible=False,electrical_union_eligible=False,
                view_scope=_view_scope(_view_for_page(page_map.get(label.sheet_id)),
                    file_id=label.file_id,sheet_id=label.sheet_id,
                    view_key=f"{label.file_id}:{label.sheet_id}:component",
                    scope_key=f"{label.file_id}:{label.sheet_id}:{part.instance_path}",
                    record_id=label.record_id,page=page_map.get(label.sheet_id)),
                superworks={"source":"superworks","part_id":label.part_id,"instance_path":part.instance_path,
                    "symbol_handle":part.insert_handle,"port_number":label.port_number,
                    "port_id":port.get("record_id"),"port_resolution_method":(port.get("pin") or {}).get("resolution_method"),
                    "corroborating_strip_text_ids":(port.get("pin") or {}).get("corroborating_strip_text_ids",[]),
                    "label_handle":part.label.get("handle"),"label_text_id":part.label.get("text_id"),
                    "connection_handle":label.text.get("handle"),"connection_text_id":label.text.get("text_id"),
                    "connect_line_handle":label.line_handle,"connect_line_id":support_line_id,
                    "connect_line_geometry_unique":not label.reason_codes},sw_conflicts=[])
            new.append(Pair(pair_id=_id(f"{label.record_id}:{destination}"),line_group_id=line_group_id,
                sheet_id=label.sheet_id,file_id=label.file_id,selected_pair_candidate_id=None,
                left_value=label.endpoint_identity,right_value=destination,confidence=.99,status="pass",confidence_bucket="high",
                rationale="SuperWORKS part and destination with uniquely resolved physical pin",pair_kind="component_mapping",evidence=evidence,
                left_text_id=part.label.get("text_id"),right_text_id=label.text.get("text_id"),
                left_coord_x=label.start_x,left_coord_y=label.start_y,right_coord_x=label.end_x,right_coord_y=label.end_y,
                pair_key=f"{label.endpoint_identity}->{destination}"))
        replace_claims(old,new,f"part:{label.record_id}")
    _fill_one_sided_pairs_from_connect_labels(output, data.connect_labels, line_groups, audit_ids, ledger, text_map)
    # Wire-route admission runs after every line-group, strip and component producer, and before the
    # dictionary check, so admitted pairs receive the same warnings and strip contract as other SW pairs.
    if not native_only and getattr(data, "wire_route_pages", None) and wire_route_sheet_numbers is not None:
        _run_wire_route_admission(output, data, lines=lines, line_groups=line_groups, audit_ids=audit_ids,
                                  page_map=page_map, strip_rows_by_endpoint=strip_rows_by_endpoint,
                                  xml_ranks=xml_ranks, sheet_numbers=wire_route_sheet_numbers, texts=texts)
    # DEV-INT-DISCARD: after admission, so admission sees the ports exactly as before this rule.
    data.device_internal_discard_stats = _discard_device_internal_pairs(output, data)
    # WIRE-BREAK (round 24): one-sided pairs on cut line groups whose open wire reaches only device-internal pins.
    data.device_internal_discard_stats.update(
        _discard_walked_half_pairs(output, data, lines, line_groups, texts=texts, block_rows=block_rows or ()))
    # The dictionary is observational; it cannot demote or validate a connection.
    dictionary={_key(v) for v in data.dictionary.get("names",[])}
    strip_names={_key(v) for v in data.dictionary.get("strip_names",[])}
    for pair in output:
        if pair.evidence.get("source")!="superworks":
            continue
        missing=[]
        for value in (pair.left_value,pair.right_value):
            if value and dictionary and _key(value) not in dictionary and not any(_key(value).startswith(prefix) and _key(value)[len(prefix):].isdigit() for prefix in strip_names):
                missing.append(value)
        if missing:
            pair.evidence["sw_dictionary_warnings"]={"unknown_names":missing,"effect":"warning_only"}
    _classify_terminal_strip_pairs(output, membership)
    data.recognition_seconds=time.perf_counter()-started
    return output,mappings,ledger


def _competing_object_id(sw):
    symbols=set()
    for side in ("left","right"):
        for item in (sw.get(side) or {}).get("competing_ports",[]) or []:
            if item.get("left_symbol"):
                symbols.add(str(item["left_symbol"]))
            if item.get("right_symbol"):
                symbols.add(str(item["right_symbol"]))
    return "|".join(sorted(symbols)) if symbols else None


_SW_COMPONENT_SUBMODE = "superworks_connect_line_port"


def _is_sw_component_row(pair):
    return (pair.pair_kind == "component_mapping"
            and (pair.evidence or {}).get("component_submode") == _SW_COMPONENT_SUBMODE)


def _component_identity(pair):
    # Same sheet, same logical endpoint, same destination, same physical port
    # number, and the same destination text: the identity both producers share.
    return (pair.sheet_id, pair.left_value, pair.right_value,
            str((pair.evidence or {}).get("component_port")), pair.right_text_id)


def supersede_equivalent_component_duplicates(pairs, ledger):
    """Retire legacy component_mapping rows that a SuperWORKS connect-line row repeats.

    The accessory/backplate producer runs after extract_superworks_pairs and
    appends its rows without SuperWORKS supersession, so a legacy row whose
    identity was re-derived from SuperWORKS connect labels survives beside the
    SW row.  Only exact-identity legacy rows (see _component_identity) are
    retired; a legacy row that differs on any identity field is kept.
    """
    sw_rows=defaultdict(list)
    for pair in pairs:
        if _is_sw_component_row(pair) and pair.status=="pass":
            sw_rows[_component_identity(pair)].append(pair)
    if not sw_rows:
        return pairs,ledger
    kept=[]
    for pair in pairs:
        twins=None
        if pair.pair_kind=="component_mapping" and pair.status=="pass" and not _is_sw_component_row(pair):
            twins=sw_rows.get(_component_identity(pair))
        if not twins:
            kept.append(pair)
            continue
        ledger.append({"element_key":f"component_duplicate:{pair.sheet_id}:{pair.pair_id}",
                       "category":"G","reason":"superworks_connect_line_port_supersedes_equivalent_legacy_row",
                       "old_pair":asdict(pair),"new_pairs":[asdict(p) for p in twins]})
    return kept,ledger


# A horizontal table border is a VIRTUAL grid line; the legacy chain may take it for a wire and
# leave one side of its pair empty while a SuperWORKS connect stub already carries the same row end.
BORDER_MIDLINE_TOL_FRACTION = 0.15
BORDER_TEXT_TOL_HEIGHTS = 1.5
BORDER_HORIZONTAL_TOL = 0.01
# A neighbouring border must cover at least this share of the missing end's border span; SW pin
# ticks (1-unit VIRTUAL dashes at the row centre) would otherwise be taken for the adjacent border.
BORDER_NEIGHBOUR_MIN_SPAN_FRACTION = 0.5
TABLE_BORDER_REASON = "table_border_row_duplicates_sw_connect_stub"


def _is_virtual_horizontal_line(line):
    return ":VIRTUAL:" in str(line.handle or "") and abs(line.start_y - line.end_y) <= BORDER_HORIZONTAL_TOL


def _connect_line_ids(pair):
    evidence = pair.evidence or {}
    sw = evidence.get("superworks") or {}
    if sw.get("connect_line_geometry_unique") is False:
        return []
    if sw.get("connect_line_id"):
        return [str(sw["connect_line_id"])]
    return [str(item) for item in evidence.get("supporting_line_ids") or []]


def _border_neighbours(point, owner, borders, span):
    """Nearest horizontal border above and below `point` in the same table.

    A neighbour must cover `point`'s x and at least BORDER_NEIGHBOUR_MIN_SPAN_FRACTION of the
    border span (`span`, the missing end's own border).
    """
    px, py = point
    span_lo, span_hi = span
    above = below = None
    for line in borders:
        if line.handle.split(":VIRTUAL:", 1)[0] != owner:
            continue
        y = line.start_y
        if abs(y - py) <= BORDER_HORIZONTAL_TOL:
            continue
        lo, hi = min(line.start_x, line.end_x), max(line.start_x, line.end_x)
        if not (lo - BORDER_HORIZONTAL_TOL <= px <= hi + BORDER_HORIZONTAL_TOL):
            continue
        if min(hi, span_hi) - max(lo, span_lo) < BORDER_NEIGHBOUR_MIN_SPAN_FRACTION * (span_hi - span_lo):
            continue
        if y > py and (above is None or y < above.start_y):
            above = line
        if y < py and (below is None or y > below.start_y):
            below = line
    return [line for line in (above, below) if line is not None]


def _bbox_corners(text):
    return [(text.bbox_min_x, text.bbox_min_y), (text.bbox_max_x, text.bbox_min_y),
            (text.bbox_max_x, text.bbox_max_y), (text.bbox_min_x, text.bbox_max_y)]


def supersede_border_row_duplicates(pairs, ledger, lines, line_groups, texts):
    """Retire one-sided legacy pairs whose missing end is a table border already carried by a SW row.

    A legacy one-sided pair on a horizontal VIRTUAL table border (every member line VIRTUAL) is
    retired only when all of these hold: its missing end M is the end farther from the present text;
    a SuperWORKS pass row on the same sheet has a connect-stub endpoint E on the midline between M's
    border and a neighbouring border in the same table (|E.y - midline| <= 15% of their spacing, and
    E.x inside their shared span); and that row's external endpoint text lies within 1.5 text heights
    of M.  Every such border is retired, including when two borders claim the same SW row, and
    including when one border has qualifying SW rows on both sides.  The SW rows and all other pairs
    are left unchanged.
    """
    sw_rows = [pair for pair in pairs if _is_sw_component_row(pair) and pair.status == "pass"]
    if not sw_rows:
        return pairs, ledger
    group_by_id = {group.line_group_id: group for group in line_groups}
    line_by_id = {line.line_id: line for line in lines}
    text_by_id = {text.text_id: text for text in texts}
    borders = defaultdict(list)
    for line in lines:
        if _is_virtual_horizontal_line(line):
            borders[(line.file_id, line.sheet_id)].append(line)
    stubs = []
    for sw in sw_rows:
        external = text_by_id.get((sw.evidence or {}).get("external_endpoint_text_id"))
        ends = []
        for line_id in _connect_line_ids(sw):
            line = line_by_id.get(line_id)
            if line is not None:
                ends.extend([(line.start_x, line.start_y), (line.end_x, line.end_y)])
        if external is not None and ends:
            stubs.append((sw, ends, external))
    if not stubs:
        return pairs, ledger
    result = list(pairs)
    for index, pair in enumerate(pairs):
        if _panel_owned(pair):
            continue
        group = group_by_id.get(pair.line_group_id)
        if not _fillable_one_sided_pair(pair, group):
            continue
        members = [line_by_id.get(str(item)) for item in group.member_line_ids]
        if not members or any(m is None or not _is_virtual_horizontal_line(m) for m in members):
            continue
        owners = {m.handle.split(":VIRTUAL:", 1)[0] for m in members}
        if len(owners) != 1:
            continue
        (owner,) = owners
        ends = _missing_end_points(pair, group)
        if ends is None:
            continue
        missing_side, missing_end, _ = ends
        mx, my = missing_end
        span_lo, span_hi = min(group.start_x, group.end_x), max(group.start_x, group.end_x)
        if span_hi - span_lo <= BORDER_HORIZONTAL_TOL:
            continue
        claims = []
        for neighbour in _border_neighbours(missing_end, owner, borders[(pair.file_id, pair.sheet_id)],
                                            (span_lo, span_hi)):
            spacing = abs(neighbour.start_y - my)
            midline = (neighbour.start_y + my) / 2
            tol = BORDER_MIDLINE_TOL_FRACTION * spacing
            lo = max(span_lo, min(neighbour.start_x, neighbour.end_x))
            hi = min(span_hi, max(neighbour.start_x, neighbour.end_x))
            for sw, sw_ends, external in stubs:
                if sw.file_id != pair.file_id or sw.sheet_id != pair.sheet_id:
                    continue
                height = float(external.height or 0.0)
                if height <= 0:
                    continue
                matched = [(ex, ey) for ex, ey in sw_ends
                           if abs(ey - midline) <= tol and lo - tol <= ex <= hi + tol]
                if not matched:
                    continue
                corners = _text_outline(external) or _bbox_corners(external)
                distance = _outline_distance(missing_end, corners)
                if distance > BORDER_TEXT_TOL_HEIGHTS * height:
                    continue
                endpoint = min(matched, key=lambda e: abs(e[1] - midline))
                claims.append((abs(endpoint[1] - midline), sw, neighbour, endpoint, distance,
                               midline, tol, spacing, height))
        if not claims:
            continue
        # A border may see two SW rows (the row above and the row below): every qualifying row is
        # recorded, and the closest midline match is the one named in the evidence.
        sw_by_id = {}
        for claim in claims:
            sw_by_id.setdefault(claim[1].pair_id, claim[1])
        _, sw, neighbour, endpoint, distance, midline, tol, spacing, height = min(claims, key=lambda c: c[0])
        sw_ids = sorted(sw_by_id)
        evidence = copy.deepcopy(pair.evidence or {})
        evidence["table_border_row_duplicate"] = {
            "reason": TABLE_BORDER_REASON, "sw_pair_id": sw.pair_id, "sw_pair_ids": sw_ids,
            "border_line_group_id": pair.line_group_id, "missing_side": missing_side,
            "missing_end": [mx, my], "neighbour_handle": neighbour.handle,
            "neighbour_y": neighbour.start_y, "midline_y": midline, "midline_tolerance": round(tol, 4),
            "stub_endpoint": list(endpoint), "text_id": sw.evidence.get("external_endpoint_text_id"),
            "text_distance": round(distance, 4), "text_limit": round(BORDER_TEXT_TOL_HEIGHTS * height, 4)}
        new = replace(pair, status="discard", rationale=f"{TABLE_BORDER_REASON}: {', '.join(sw_ids)}",
                      evidence=evidence)
        result[index] = new
        ledger.append({"element_key": f"table_border_row:{pair.sheet_id}:{pair.pair_id}", "category": "H",
                       "reason": TABLE_BORDER_REASON, "old_pair": asdict(pair),
                       "new_pairs": [asdict(sw_by_id[sw_id]) for sw_id in sw_ids]})
    return result, ledger


# A table cell's horizontal edge (INSERT VIRTUAL lines between two column frames of the same block) can be
# read as a wire and leave one side of its pair empty.  With no SuperWORKS stub on the table, the cell row
# shows nothing outward of the missing end; a real wire would show a lead or a label there.
TABLE_CELL_REASON = "table_cell_edge_no_outward"
# Column-frame endpoint tolerance, relative to the edge span (the frame sits exactly on the edge end in
# the data; the tolerance only absorbs float noise and keeps the divider 5 units away from counting).
CELL_FRAME_X_TOL_FRACTION = 0.05
# A lead may touch the column frame only within this share of the row spacing on its inner side, and must
# reach beyond the frame by more than it; a straddling pin mark (about half its length on each side) fails.
LEAD_CONTACT_FRACTION = 0.05
# Parallel borders within this multiple of the nearest border's distance count as grid neighbours.
GRID_PITCH_RATIO = 2.0
# With a grid neighbour on one side only, the row pitch must be confirmed by the block's own ladder: this many
# consecutive parallel borders (same INSERT, same layer, any span) at equal spacing, within this share of pitch.
CELL_GRID_MIN_EQUAL_LINES = 3
CELL_GRID_PITCH_TOL_FRACTION = 0.10


def _insert_owner(line):
    """The INSERT handle a VIRTUAL line was expanded from, or None for a non-VIRTUAL line."""
    handle = str(line.handle or "")
    return handle.split(":VIRTUAL:", 1)[0] if ":VIRTUAL:" in handle else None


def _is_vertical_line(line):
    return abs(line.start_x - line.end_x) <= BORDER_HORIZONTAL_TOL and abs(line.start_y - line.end_y) > BORDER_HORIZONTAL_TOL


def _panel_owned(pair):
    """Pairs a whole-panel IGNORE decision has already taken out of the ordinary graph (see mark pass)."""
    evidence = pair.evidence or {}
    return bool(evidence.get("ignored_panel_family_id")) or evidence.get("ordinary_pair_eligible") is False


def _frame_covers(end, owner, verticals, x_tol, y_tol):
    """True when a column frame of `owner` sits at the edge end's x and its y range covers the edge."""
    ex, ey = end
    for line in verticals:
        if _insert_owner(line) != owner or abs(line.start_x - ex) > x_tol:
            continue
        lo, hi = sorted((line.start_y, line.end_y))
        if lo - y_tol <= ey <= hi + y_tol:
            return True
    return False


def _equal_spacing_confirms(block_ys, neighbour_y, pitch):
    """True when CELL_GRID_MIN_EQUAL_LINES consecutive parallel block borders at `pitch` include the neighbour.

    `block_ys` are the horizontal borders of the same INSERT on the same layer, whatever their span; coincident
    lines (one border drawn as several segments) count once.  Every gap of the window must match the pitch and
    each other within CELL_GRID_PITCH_TOL_FRACTION of the pitch.
    """
    ys = []
    for y in sorted(block_ys):
        if not ys or y - ys[-1] > BORDER_HORIZONTAL_TOL:
            ys.append(y)
    tol = CELL_GRID_PITCH_TOL_FRACTION * pitch
    width = CELL_GRID_MIN_EQUAL_LINES
    for start in range(len(ys) - width + 1):
        window = ys[start:start + width]
        if not any(abs(y - neighbour_y) <= BORDER_HORIZONTAL_TOL for y in window):
            continue
        gaps = [hi - lo for lo, hi in zip(window, window[1:])]
        if all(abs(gap - pitch) <= tol for gap in gaps) and max(gaps) - min(gaps) <= tol:
            return True
    return False


def _cell_row_probe(missing_end, outward, neighbour_y, owner, lines, texts, members, x_tol):
    """Outward probe at the row centre beside the missing end, one row high and one row long.

    Clear means no lead (see LEAD_CONTACT_FRACTION) reaches outward from the column frame through the
    probe rectangle, and no text on the outward side lies within 1.5 text heights of the missing end.
    """
    mx, my = missing_end
    spacing = abs(neighbour_y - my)
    centre_y = (my + neighbour_y) / 2
    tol = BORDER_MIDLINE_TOL_FRACTION * spacing
    contact = LEAD_CONTACT_FRACTION * spacing
    x_lo, x_hi = sorted((mx, mx + outward * spacing))
    y_lo, y_hi = centre_y - tol, centre_y + tol
    leads = []
    for line in lines:
        if line.line_id in members:
            continue
        if _is_vertical_line(line) and _insert_owner(line) == owner and abs(line.start_x - mx) <= x_tol:
            continue
        if not (line.bbox_min_x <= x_hi and line.bbox_max_x >= x_lo and line.bbox_min_y <= y_hi and line.bbox_max_y >= y_lo):
            continue
        # A lead starts on the column frame and runs outward. A symmetric VIRTUAL pin mark straddles the
        # frame (its ends lie on both sides of it) and is not a lead.
        ends = [(line.start_x, line.start_y), (line.end_x, line.end_y)]
        inward = max(0.0, max((mx - x) * outward for x, _ in ends))
        reach = max((x - mx) * outward for x, _ in ends)
        if inward <= contact and reach > contact:
            leads.append(line.handle)
    near = []
    for text in texts:
        corners = _text_outline(text) or _bbox_corners(text)
        height = float(text.height or 0.0)
        if height <= 0 or max((x - mx) * outward for x, _ in corners) < -BORDER_HORIZONTAL_TOL:
            continue
        if _outline_distance((mx, my), corners) <= BORDER_TEXT_TOL_HEIGHTS * height:
            near.append(text.text_id)
    return {"neighbour_y": neighbour_y, "centre_y": centre_y, "spacing": spacing, "tolerance": round(tol, 4),
            "leads": leads, "texts": near, "clear": not leads and not near}


def supersede_cell_edge_pairs(pairs, ledger, lines, line_groups, texts):
    """Retire one-sided legacy pairs whose line group is a table cell edge with nothing outward of it.

    Must run after mark_ignored_equipment_panel_ordinary_pairs.  A one-sided, non-SuperWORKS ordinary pair is
    retired only when all of these hold:
    - it is not already retired by another rule and not owned by a whole-panel IGNORE decision;
    - its line group is horizontal and every member is a VIRTUAL segment of one INSERT on one layer, with both
      endpoints on column frames of that INSERT whose y range covers the edge;
    - the row pitch is grid-confirmed: a horizontal border of the same INSERT and layer, sharing at least half
      the edge span, lies on each side of the edge (both within GRID_PITCH_RATIO of the nearest), or, with one
      side only, CELL_GRID_MIN_EQUAL_LINES borders of the block at equal spacing include that neighbour;
    - the cell band (between the edge and its row neighbours) has clear row-centre probes on both sides of the
      edge outward of the missing end: no lead leaves the frame and no text lies within 1.5 text heights of the
      missing end.
    Two-sided pairs, SuperWORKS rows and pairs already retired are never changed; no pair is removed.
    """
    group_by_id = {group.line_group_id: group for group in line_groups}
    line_by_id = {line.line_id: line for line in lines}
    lines_by_sheet = defaultdict(list)
    borders = defaultdict(list)
    verticals = defaultdict(list)
    for line in lines:
        key = (line.file_id, line.sheet_id)
        lines_by_sheet[key].append(line)
        if _is_virtual_horizontal_line(line):
            borders[key].append(line)
        elif _is_vertical_line(line) and _insert_owner(line) is not None:
            verticals[key].append(line)
    texts_by_sheet = defaultdict(list)
    for text in texts:
        texts_by_sheet[(text.file_id, text.sheet_id)].append(text)
    result = list(pairs)
    for index, pair in enumerate(pairs):
        if TABLE_BORDER_REASON in (pair.rationale or "") or "table_border_row_duplicate" in (pair.evidence or {}):
            continue
        if _panel_owned(pair):
            continue
        group = group_by_id.get(pair.line_group_id)
        if not _fillable_one_sided_pair(pair, group):
            continue
        members = [line_by_id.get(str(item)) for item in group.member_line_ids]
        if not members or any(m is None or not _is_virtual_horizontal_line(m) for m in members):
            continue
        owners = {_insert_owner(m) for m in members}
        if len(owners) != 1 or None in owners:
            continue
        (owner,) = owners
        layers = {str(m.layer) for m in members}
        if len(layers) != 1:
            continue
        (edge_layer,) = layers
        ends = _missing_end_points(pair, group)
        if ends is None:
            continue
        missing_side, missing_end, _ = ends
        mx, my = missing_end
        span_lo, span_hi = sorted((group.start_x, group.end_x))
        span_len = span_hi - span_lo
        if span_len <= BORDER_HORIZONTAL_TOL:
            continue
        key = (pair.file_id, pair.sheet_id)
        table = [line for line in borders[key]
                 if _insert_owner(line) == owner and str(line.layer) == edge_layer]
        neighbours = _border_neighbours(missing_end, owner, table, (span_lo, span_hi))
        if not neighbours:
            continue
        pitch = min(abs(n.start_y - my) for n in neighbours)
        # Grid rows only: a border more than GRID_PITCH_RATIO pitches away is not the next table row.
        neighbours = [n for n in neighbours if abs(n.start_y - my) <= GRID_PITCH_RATIO * pitch]
        sides = {(1 if n.start_y > my else -1): n for n in neighbours}
        if len(sides) == 2:
            basis = "both_sides"
        else:
            # A lone neighbour cannot define the row pitch by itself: the block's own ladder must confirm it.
            # Only row-length borders take part: 1-unit VIRTUAL pin dashes sit between rows and break the ladder.
            (only,) = sides.values()
            pitch = abs(only.start_y - my)
            ladder = [line.start_y for line in table
                      if abs(line.end_x - line.start_x) >= BORDER_NEIGHBOUR_MIN_SPAN_FRACTION * span_len]
            if not _equal_spacing_confirms(ladder, only.start_y, pitch):
                continue
            basis = "equal_spacing"
        y_tol = BORDER_MIDLINE_TOL_FRACTION * pitch
        x_tol = CELL_FRAME_X_TOL_FRACTION * span_len
        edge_y = (group.start_y + group.end_y) / 2
        if not all(_frame_covers(end, owner, verticals[key], x_tol, y_tol)
                   for end in ((group.start_x, edge_y), (group.end_x, edge_y))):
            continue
        outward = 1 if mx > (span_lo + span_hi) / 2 else -1
        members_ids = set(group.member_line_ids)
        probes = []
        # Both row centres (the cell band above and below the edge) are probed, never only one.
        for sign in (1, -1):
            neighbour = sides.get(sign)
            # A side without a neighbour is one pitch deep in an equal-spacing grid.
            neighbour_y = neighbour.start_y if neighbour is not None else my + sign * pitch
            probe = _cell_row_probe(missing_end, outward, neighbour_y, owner, lines_by_sheet[key],
                                    texts_by_sheet[key], members_ids, x_tol)
            probe["side"] = "higher_y" if sign > 0 else "lower_y"
            probe["neighbour_handle"] = None if neighbour is None else neighbour.handle
            probes.append(probe)
        if not all(probe["clear"] for probe in probes):
            continue
        evidence = copy.deepcopy(pair.evidence or {})
        evidence["table_cell_edge"] = {
            "reason": TABLE_CELL_REASON, "owner": owner, "border_line_group_id": pair.line_group_id,
            "missing_side": missing_side, "missing_end": [mx, my], "span": [span_lo, span_hi],
            "edge_layer": edge_layer, "grid_basis": basis, "outward": outward,
            "neighbour_handles": sorted(n.handle for n in sides.values()), "probes": probes}
        new = replace(pair, status="discard", rationale=f"{TABLE_CELL_REASON}: {owner}", evidence=evidence)
        result[index] = new
        ledger.append({"element_key": f"table_cell_edge:{pair.sheet_id}:{pair.pair_id}", "category": "H",
                       "reason": TABLE_CELL_REASON, "old_pair": asdict(pair), "new_pairs": []})
    return result, ledger


# Ledger category I: a pure legacy pair (V1 chain, no SuperWORKS evidence, not in the ledger) whose two
# endpoints name the same terminals as a SuperWORKS pass pair on the same sheet.  The SuperWORKS pair
# already carries that connection, so the legacy pair is a second derivation of it and is retired.
LEGACY_DUPLICATE_CATEGORY = "I"
LEGACY_DUPLICATE_REASON = "legacy_pair_duplicates_same_sheet_sw_pass"
SW_EVIDENCE_KEYS = ("superworks", "superworks_constraints", "sw_conflicts", "sw_dictionary_warnings")


def _is_sw_produced_pair(pair):
    return (pair.evidence or {}).get("source") == "superworks" or _is_sw_component_row(pair)


def _is_pure_legacy_pair(pair, ledger_ids):
    evidence = pair.evidence or {}
    if pair.pair_id in ledger_ids or evidence.get("source") == "superworks" or _is_sw_component_row(pair):
        return False
    return not any(key in evidence for key in SW_EVIDENCE_KEYS)


def _sw_end_aliases(sw, side):
    """Endpoint aliases SuperWORKS recorded for one side, only when they describe that side's own value."""
    end = ((sw.evidence or {}).get("superworks") or {}).get(side)
    if not isinstance(end, dict) or _is_blank_side(end.get("value")):
        return []
    if str(end.get("value")) != str(getattr(sw, f"{side}_value")):
        return []
    return list(end.get("endpoint_aliases") or [])


def _ends_equivalent(legacy_value, sw_value, sw_aliases=()):
    """One legacy endpoint names the same terminal as one SuperWORKS endpoint.

    Both values are cleaned with the SuperWORKS endpoint rule.  Two ways count:
    - mutual: each name names the other under the production identity rule (_identities_agree).
      Both directions are needed, so an end that is wider than the other (a range covering more
      terminals, a letter prefix on one side only) is a partial match and is left alone;
    - alias: the legacy text is one of the aliases SuperWORKS recorded for that end, which is the
      alias branch of _identities_agree on the SuperWORKS side.
    """
    if _is_blank_side(legacy_value) or _is_blank_side(sw_value):
        return False
    legacy_clean = _clean_sw_endpoint_value(legacy_value)
    sw_clean = _clean_sw_endpoint_value(sw_value)
    if not legacy_clean or not sw_clean:
        return False
    if _identities_agree(legacy_clean, sw_clean) and _identities_agree(sw_clean, legacy_clean):
        return True
    alias_keys = {_key(_clean_sw_endpoint_value(alias)) for alias in sw_aliases or [] if alias}
    return _key(legacy_clean) in alias_keys


def _pair_endpoints_equivalent(legacy, sw):
    """Unordered endpoint equivalence: left with left and right with right, or crossed."""
    left_aliases = _sw_end_aliases(sw, "left")
    right_aliases = _sw_end_aliases(sw, "right")
    if (_ends_equivalent(legacy.left_value, sw.left_value, left_aliases)
            and _ends_equivalent(legacy.right_value, sw.right_value, right_aliases)):
        return True
    return (_ends_equivalent(legacy.left_value, sw.right_value, right_aliases)
            and _ends_equivalent(legacy.right_value, sw.left_value, left_aliases))


def supersede_legacy_duplicates_of_sw(pairs, ledger):
    """Retire pure legacy pass/review pairs that a same-sheet SuperWORKS pass pair repeats (category I).

    The SuperWORKS side is any pass pair SuperWORKS produced (source superworks, or a connect-line port
    component row).  The legacy side must carry no SuperWORKS evidence (see SW_EVIDENCE_KEYS), must not be
    in the ledger, and must not be owned by an IGNORE panel.  A legacy pair is retired only when every
    endpoint is equivalent (_pair_endpoints_equivalent); a pair with an extra, missing or partial end is
    kept.  The SuperWORKS pairs are never changed.  Evidence of a retired pair records superseded_by (the
    first matching SuperWORKS pair id, sorted), superseded_by_all and supersession_category 'I'.
    """
    ledger_ids = set()
    for entry in ledger:
        ledger_ids.add((entry.get("old_pair") or {}).get("pair_id"))
        ledger_ids.update(item.get("pair_id") for item in entry.get("new_pairs") or [])
    sw_by_sheet = defaultdict(list)
    for pair in pairs:
        if pair.status == "pass" and _is_sw_produced_pair(pair):
            sw_by_sheet[(pair.file_id, pair.sheet_id)].append(pair)
    if not sw_by_sheet:
        return pairs, ledger
    result = list(pairs)
    for index, pair in enumerate(pairs):
        if pair.status not in ("pass", "review") or not _is_pure_legacy_pair(pair, ledger_ids):
            continue
        if (pair.evidence or {}).get("ignored_panel_family_id"):
            continue
        twins = sorted((sw for sw in sw_by_sheet.get((pair.file_id, pair.sheet_id), ())
                        if _pair_endpoints_equivalent(pair, sw)), key=lambda sw: sw.pair_id)
        if not twins:
            continue
        evidence = copy.deepcopy(pair.evidence or {})
        evidence["superseded_by"] = twins[0].pair_id
        evidence["superseded_by_all"] = [sw.pair_id for sw in twins]
        evidence["supersession_category"] = LEGACY_DUPLICATE_CATEGORY
        new = replace(pair, status="discard", rationale=f"{LEGACY_DUPLICATE_REASON}: {twins[0].pair_id}",
                      evidence=evidence)
        result[index] = new
        ledger.append({"element_key": f"legacy_duplicate:{pair.sheet_id}:{pair.pair_id}",
                       "category": LEGACY_DUPLICATE_CATEGORY, "reason": LEGACY_DUPLICATE_REASON,
                       "old_pair": asdict(pair), "new_pairs": [asdict(sw) for sw in twins]})
    return result, ledger


# P2-BACKPLATE: a backplate virtual-table pass pair names an external terminal R and a backplate
# row/device. A same-project SuperWORKS pass pair that also names R gives the backplate identity of
# the terminal; its last two digits are the row. Agreement is evidence only (status is unchanged).
# Disagreement is written as a candidate row for review; it changes no pair and raises no issue.
BACKPLATE_CORROBORATION_MATCH = "row+terminal+device"
BACKPLATE_CONTRADICTION_TYPES = ("same_sheet_row_conflict", "device_prefix_differs")
_BP_NUMERIC_IDENTITY = re.compile(r"^(\d+(?:-\d+)?n)([A-Z]*)(\d{3,})$")   # <dev><col digits><row:2>, e.g. 1n0503, 1nP103
_BP_ALPHA_IDENTITY = re.compile(r"^(\d+(?:-\d+)?n)([A-Z])(\d{2})$")        # <dev><letter><row:2>, e.g. 1-25nA24
_BP_BAY_PREFIX = re.compile(r"^\d+-")


def _bp_key(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return re.sub(r"[\s@\u3000]+", "", str(value)) or None


def _bp_identity(value):
    """Backplate identity of a SuperWORKS-style endpoint value, or None when it is not one."""
    key = _bp_key(value)
    if not key:
        return None
    match = _BP_NUMERIC_IDENTITY.match(key)
    if match:
        return {"device": match.group(1), "row": int(match.group(3)[-2:]), "form": "numeric"}
    match = _BP_ALPHA_IDENTITY.match(key)
    if match:
        return {"device": match.group(1), "row": int(match.group(3)), "form": "alpha"}
    return None


def _bp_device_matches(sw_device, v1_device):
    """Device label agreement after normalization.

    Trailing letters are dropped on the V1 side (1nP -> 1n). A bay prefix (the '1-' of 1-1n) that only
    one side writes is ignored; when both write it the bays must be equal.
    """
    v1_device = re.sub(r"[A-Z]+$", "", v1_device)
    if sw_device == v1_device:
        return True
    if _BP_BAY_PREFIX.match(sw_device) and _BP_BAY_PREFIX.match(v1_device):
        return False
    return _BP_BAY_PREFIX.sub("", sw_device) == _BP_BAY_PREFIX.sub("", v1_device)


def _backplate_pass_mapping(pair):
    if pair.status != "pass":
        return None
    mapping = (pair.evidence or {}).get("table_mapping") or {}
    return mapping if mapping.get("mapping_mode") == "backplate_virtual_table" else None


def corroborate_backplate_virtual_pairs(pairs):
    """Corroborate backplate virtual-table pass pairs by same-project SuperWORKS pass pairs on R (P2-BACKPLATE).

    Returns (pairs, contradictions). Only evidence is added to a pair that agrees (row, device and terminal R).
    A pair with no agreeing partner but a partner that disagrees (same-sheet row conflict, or same row with
    a different device label) yields one contradiction row per type. Statuses are never changed here.
    """
    sw_partners = defaultdict(list)
    for pair in pairs:
        if pair.status != "pass" or not _is_sw_produced_pair(pair):
            continue
        for mine, other in ((pair.left_value, pair.right_value), (pair.right_value, pair.left_value)):
            if _bp_key(mine) and _bp_key(other):
                sw_partners[_bp_key(mine)].append((pair, other))
    if not sw_partners:
        return pairs, []
    result = list(pairs)
    contradictions = []
    for index, pair in enumerate(pairs):
        mapping = _backplate_pass_mapping(pair)
        if mapping is None:
            continue
        terminal = _bp_key(pair.right_value)
        row = mapping.get("row_number")
        device = mapping.get("composite_device_instance")
        if not terminal or row is None or not device:
            continue
        matches, device_diff, row_diff = [], [], []
        for sw, other in sw_partners.get(terminal, ()):
            identity = _bp_identity(other)
            if identity is None or sw.pair_id == pair.pair_id:
                continue
            same_sheet = sw.file_id == pair.file_id and sw.sheet_id == pair.sheet_id
            row_ok = identity["row"] == int(row)
            device_ok = _bp_device_matches(identity["device"], str(device))
            item = {"sw_pair_id": sw.pair_id, "sw_identity": _bp_key(other), "sw_row": identity["row"],
                    "sw_device": identity["device"], "same_sheet": same_sheet}
            if row_ok and device_ok:
                matches.append(item)
            elif row_ok:
                device_diff.append(item)
            elif device_ok and same_sheet:
                row_diff.append(item)
        if matches:
            best = sorted(matches, key=lambda item: (not item["same_sheet"], item["sw_pair_id"]))[0]
            evidence = copy.deepcopy(pair.evidence or {})
            evidence["sw_backplate_corroboration"] = {
                "sw_pair_id": best["sw_pair_id"], "match": BACKPLATE_CORROBORATION_MATCH,
                "sw_identity": best["sw_identity"], "same_sheet": best["same_sheet"],
                "row_number": int(row), "device": str(device), "partner_count": len(matches)}
            result[index] = replace(pair, evidence=evidence)
            continue
        for kind, items in (("same_sheet_row_conflict", row_diff), ("device_prefix_differs", device_diff)):
            if not items:
                continue
            first = sorted(items, key=lambda item: (not item["same_sheet"], item["sw_pair_id"]))[0]
            contradictions.append({
                "candidate_id": f"BPC:{pair.pair_id}:{kind}", "contradiction_type": kind,
                "pair_id": pair.pair_id, "file_id": pair.file_id, "sheet_id": pair.sheet_id,
                "sheet_no": mapping.get("sheet_no"), "filename": mapping.get("filename") or (pair.evidence or {}).get("filename"),
                "left_value": pair.left_value, "right_value": pair.right_value,
                "v1_row": int(row), "v1_device": str(device), "v1_header_prefix": mapping.get("header_prefix"),
                "v1_header_text_id": mapping.get("header_text_id"), "v1_middle_text_id": mapping.get("middle_text_id"),
                "v1_right_text_id": pair.right_text_id, "v1_confidence": pair.confidence,
                "sw_pair_id": first["sw_pair_id"], "sw_identity": first["sw_identity"],
                "sw_row": first["sw_row"], "sw_device": first["sw_device"], "sw_same_sheet": first["same_sheet"],
                "sw_partner_count": len(items),
                "sw_partners": [{k: v for k, v in item.items()} for item in items],
            })
    return result, contradictions


# P2-BACKPLATE, supersession category J. A backplate virtual-table pass pair reads the row number beside its
# external terminal R wrongly (the V1 row cell is not the row cell), while a same-sheet SuperWORKS pass pair
# already states the right backplate identity for R. The judged population of this class is 32 of 32 V1 misreads
# (loop/P2-BACKPLATE/IMPL.md). The V1 pair is retired as superseded; no issue is raised (the drawing is consistent).
BACKPLATE_ROW_MISREAD_CATEGORY = "J"
BACKPLATE_ROW_MISREAD_REASON = "backplate_row_misread_superseded_by_same_sheet_sw"
BACKPLATE_ROW_MISREAD_TYPES = ("same_sheet_row_conflict",)


def supersede_backplate_row_misreads(pairs, ledger, contradictions):
    """Retire backplate pass pairs whose row number a same-sheet SuperWORKS pass pair contradicts (category J).

    Only candidates of an enabled type are retired, and only pass pairs. Evidence records superseded_by (the
    SuperWORKS pair), superseded_by_all, supersession_category 'J' and the conflict details. Each candidate row
    gets action 'superseded_category_J' or 'candidate_only'. A ledger entry is appended per retired pair.
    """
    retire = {}
    for item in contradictions:
        item["action"] = "candidate_only"
        if item["contradiction_type"] in BACKPLATE_ROW_MISREAD_TYPES:
            retire.setdefault(item["pair_id"], item)
    if not retire:
        return pairs, ledger
    result = list(pairs)
    ledger = list(ledger)
    for index, pair in enumerate(pairs):
        item = retire.get(pair.pair_id)
        if item is None or pair.status != "pass":
            continue
        evidence = copy.deepcopy(pair.evidence or {})
        sw_ids = sorted({item["sw_pair_id"]} | set(
            partner["sw_pair_id"] for partner in (item.get("sw_partners") or [])
            if partner.get("same_sheet") and partner.get("sw_pair_id")))
        evidence["superseded_by"] = sw_ids[0]
        evidence["superseded_by_all"] = sw_ids
        evidence["supersession_category"] = BACKPLATE_ROW_MISREAD_CATEGORY
        evidence["backplate_row_misread"] = {
            "sw_pair_id": item["sw_pair_id"], "sw_identity": item["sw_identity"], "sw_row": item["sw_row"],
            "v1_row": item["v1_row"], "contradiction_type": item["contradiction_type"]}
        new = replace(pair, status="discard", evidence=evidence,
                      rationale=f"{BACKPLATE_ROW_MISREAD_REASON}: {sw_ids[0]} (SW identity {item['sw_identity']}, "
                                f"row {item['sw_row']:02d}; V1 row {item['v1_row']:02d})")
        result[index] = new
        ledger.append({"element_key": f"backplate_row_misread:{pair.sheet_id}:{pair.pair_id}",
                       "category": BACKPLATE_ROW_MISREAD_CATEGORY, "reason": BACKPLATE_ROW_MISREAD_REASON,
                       "old_pair": asdict(pair), "new_pairs": [{"pair_id": sw_id} for sw_id in sw_ids]})
        item["action"] = "superseded_category_J"
    return result, ledger


def build_superworks_issues(context):
    grouped=defaultdict(list)
    for pair in context.pairs:
        evidence=pair.evidence or {}
        if evidence.get("discard_reason")==DEVICE_INTERNAL_DISCARD:
            # DEV-INT-DISCARD: a device-internal connection is silent, whatever conflict its pair carried.
            continue
        conflicts=_true_conflicts(evidence.get("sw_conflicts") or [])
        if not conflicts:
            continue
        sw=evidence.get("superworks") or {}
        endpoint_port_ids=sorted({port_id for side in ("left","right")
                                  for port_id in (sw.get(side) or {}).get("port_ids",[])})
        endpoint_symbols=sorted({str((sw.get(side) or {}).get("symbol_id")) for side in ("left","right")
                                 if (sw.get(side) or {}).get("symbol_id")})
        for reason in conflicts:
            if reason in {"invalid_strip_header_reference"}:
                object_id=sw.get("header_handle") or (sw.get("validation") or {}).get("header_handle") or "strip-header"
            elif reason in {"invalid_strip_connection_reference"}:
                object_id=sw.get("connection_handle") or sw.get("row_handle") or "strip-connection"
            elif reason in {"competing_physical_port_instances","competing_physical_port_identities"}:
                # One report per (symbol-instance pair, conflict type): the
                # conflict object is the pair of physically coincident instances.
                object_id=_competing_object_id(sw) or ",".join(endpoint_port_ids) or ",".join(endpoint_symbols) or pair.pair_id
            elif endpoint_port_ids:
                object_id=",".join(endpoint_port_ids)
            elif endpoint_symbols:
                object_id=",".join(endpoint_symbols)
            else:
                object_id=sw.get("connect_line_handle") or sw.get("row_id") or pair.line_group_id or pair.pair_id
            key=(pair.file_id,pair.sheet_id,str(object_id),reason)
            grouped[key].append(pair)
    issues=[]
    for (file_id,sheet_id,object_id,reason),pairs in sorted(grouped.items()):
        first=pairs[0]
        issues.append(context.issue_factory.build("R-SUPERWORKS-CONFLICT","review",first,
            f"SuperWORKS metadata conflict {reason} on {object_id}.",title="SuperWORKS 元数据关联冲突",
            explanation="只有悬空、过期、非双向引用或物理接点/身份竞争才归为元数据冲突；未解析端点和缺少接触只记录在覆盖证据中。",
            related_pairs=pairs if len(pairs)>1 else None,
            extra={"reason_codes":[reason],"conflict_object_id":object_id,"file_id":file_id,
                   "sheet_id":sheet_id,"source":"superworks"}))
    return issues
