"""Metadata-owned recognition over the existing producers' wires and table rows."""
from __future__ import annotations

import copy
import hashlib
import math
import re
import time
from collections import defaultdict, deque
from dataclasses import asdict, replace

from dwg_audit.domain.models import Pair, SwPort, LineGroup
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
            header = (row.header or {}).get("normalized")
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


def extract_superworks_pairs(data: SuperworksData, *, pages, texts, lines, line_groups, pairs, table_mappings):
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
    strip_rows_by_endpoint = _strip_scope_index(data)
    xml_ranks = {_key(item.get("name", "")): item.get("rank")
                 for item in data.dictionary.get("strip_order", []) if item.get("name")}
    contacts={(p.sheet_id,c["wire_handle"]) for p in data.ports for c in p.wire_contacts}
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
        index=indices.get(group.sheet_id)
        if index is None:
            continue
        endpoints=[]
        for x,y in ((group.start_x,group.start_y),(group.end_x,group.end_y)):
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
            continue
        reasons=sorted({r for endpoint in endpoints if endpoint for r in endpoint["reason_codes"]})
        conflicts=_true_conflicts(reasons)
        self_reason=_self_connection_reason(left,right)
        if self_reason:
            # F1: both ends resolve to one logical identity.  No production pair
            # is emitted and no cross-page / duplicate / cardinality rule sees
            # it; the group is recorded in the SW diagnostics instead.
            spans=_spans_one_symbol(left,right)
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
        if left["category"]==right["category"]=="端子" and strip_relation:
            kind="bridge_mapping"
            bridge_kind="superworks_terminal_strip_same_header"
        else:
            kind="ordinary_pair" if left["category"]==right["category"]=="端子" else "wire_component_mapping"
            bridge_kind=None
        evidence={"source":"superworks","superworks":{"source":"superworks","left":left,"right":right},
                  "sw_conflicts":conflicts,"ordinary_pair_eligible":kind=="ordinary_pair",
                  "electrical_union_eligible":False,"internal_connectivity_inferred":False,
                  "pair_kind":kind,"sheet_order":page_map[group.sheet_id].sheet_order,
                  "selected_left_raw_text":left["value"],"selected_right_raw_text":right["value"],
                  "semantic_marker_texts":[left["value"],right["value"]]}
        evidence["superworks"]["line_group_origin"]=origin
        page=page_map.get(group.sheet_id)
        evidence["view_scope"]=_view_scope(_view_for_page(page),
            file_id=group.file_id,sheet_id=group.sheet_id,
            view_key=f"{group.file_id}:{group.sheet_id}:schematic",
            scope_key=f"{group.file_id}:{group.sheet_id}:{group.line_group_id}",
            record_id=group.line_group_id,page=page)
        if strip_relation:
            evidence["superworks"]["strip_relation"]=strip_relation
        if bridge_kind:
            evidence.update(semantic_kind="terminal_bridge_mapping",bridge_mapping_kind=bridge_kind)
        new=Pair(pair_id=_id(f"wire:{group.sheet_id}:{group.line_group_id}"),line_group_id=group.line_group_id,
            sheet_id=group.sheet_id,file_id=group.file_id,selected_pair_candidate_id=None,
            left_value=left["value"],right_value=right["value"],confidence=.99 if not conflicts else .5,
            status="pass" if not conflicts else "review",rationale="SuperWORKS identity verified against existing wire endpoints" if not conflicts else ";".join(conflicts),
            confidence_bucket="high" if not conflicts else "review",evidence=evidence,
            left_text_id=left["text_id"],right_text_id=right["text_id"],left_coord_x=group.start_x,left_coord_y=group.start_y,
            right_coord_x=group.end_x,right_coord_y=group.end_y,pair_key=f'{left["value"]}->{right["value"]}',pair_kind=kind)
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
    for row in data.strip_rows:
        if row.sheet_id not in audit_ids:
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
                    "header_prefix":row.header.get("normalized"),"header_text_id":header_id,
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
        item["mappings"]=[m for m in item.get("mappings",[]) if (item.get("sheet_id") or m.get("sheet_id"),m.get("header_text_id"),m.get("middle_text_id")) not in replaced_row_keys]
    for sid,rows in sw_mappings.items():
        mappings.append({"sheet_id":sid,"source":"superworks","mappings":rows})

    group_by_id={group.line_group_id:group for group in line_groups}
    for label in data.connect_labels:
        if label.sheet_id not in audit_ids:
            continue
        old=[p for p in pairs if p.sheet_id==label.sheet_id and p.pair_kind=="component_mapping"
             and label.text.get("text_id") in (p.left_text_id,p.right_text_id)]
        true_conflicts=_true_conflicts(label.reason_codes)
        if not label.endpoint_identity or label.reason_codes:
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
        line_id_by_handle={line.handle:line.line_id for line in lines}
        support_line_id=line_id_by_handle.get(label.line_handle)
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


def build_superworks_issues(context):
    grouped=defaultdict(list)
    for pair in context.pairs:
        evidence=pair.evidence or {}
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
