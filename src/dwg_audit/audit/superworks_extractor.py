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
from dwg_audit.extract.superworks_semantics import SuperworksData, normalize

_TRUE_CONFLICTS = {
    "dangling_label_handle", "stale_label_reference", "label_owner_mismatch",
    "nonreciprocal_label", "nonreciprocal_pin", "dangling_pin_handle",
    "stale_pin_reference", "invalid_strip_header_reference",
    "invalid_strip_connection_reference", "competing_physical_port_instances",
    "competing_physical_port_identities", "same_physical_port_at_both_ends",
}


def _id(key):
    return "PSW" + hashlib.sha256(key.encode()).hexdigest()[:16]


def _key(value):
    return re.sub(r"\s+", "", normalize(value or "")).casefold()


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
    conflicts=sorted({reason for p in ports for reason in p.reason_codes})
    if len(identities)>1:
        conflicts.append("competing_physical_port_identities")
    elif len({p.symbol_id for p in ports})>1:
        conflicts.append("competing_physical_port_instances")
    if not ports:
        return None
    selected=ports[0]
    text=selected.label if selected.category=="端子" else selected.pin
    if not selected.endpoint_identity:
        conflicts.append("unresolved_endpoint_identity")
    if any(not p.validation.get("port_touched_by_wire") for p in ports):
        conflicts.append("port_not_touched_by_wire")
    return {"value": selected.endpoint_identity if len(identities)<=1 else None, "candidate_values":sorted({p.endpoint_identity for p in ports if p.endpoint_identity}), "category":selected.category, "text_id":text.get("text_id"),
            "label_text_id":selected.label.get("text_id"), "pin_text_id":selected.pin.get("text_id"),
            "label_handle":selected.label.get("handle"),"pin_handle":selected.pin.get("handle"),
            "symbol_handle":selected.insert_handle,"symbol_id":selected.symbol_id,
            "port_number":selected.port_number, "port_ids":sorted(p.record_id for p in ports),
            "ports":[{"port_id":p.record_id,"port_number":p.port_number,"start":[p.start_x,p.start_y],"end":[p.end_x,p.end_y],"validation":p.validation} for p in ports],
            "validation":selected.validation,"network_line_ids":path or [],
            "wire_touched":all(p.validation.get("port_touched_by_wire") for p in ports),
            "reason_codes":sorted(set(conflicts))}


def _true_conflicts(reasons):
    return sorted(set(reasons) & _TRUE_CONFLICTS)


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
        if not left or not right or not left.get("value") or not right.get("value"):
            for before in old:
                evidence=copy.deepcopy(before.evidence)
                evidence["superworks"]={"source":"superworks","left":left,"right":right,
                    "partial":True,"line_group_origin":origin}
                if conflicts:
                    evidence["sw_conflicts"]=sorted(set(evidence.get("sw_conflicts", [])) | set(conflicts))
                replace_claims([before],[replace(before,evidence=evidence)],f"wire:{group.sheet_id}:{group.line_group_id}")
            continue
        if set(left["port_ids"]) & set(right["port_ids"]):
            # Network evidence on both sides cannot manufacture two distinct endpoints.
            conflicts.append("same_physical_port_at_both_ends")
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
            values=[normalize(v.strip().strip("&")) for v in re.split(r"[,，]",value) if v.strip().strip("&")]
            for destination in values:
                row_number=int(row.row.get("normalized")) if row.row.get("normalized", "").isdigit() else None
                mapping={"mapping_mode":"terminal_header_table","sheet_id":row.sheet_id,"file_id":row.file_id,
                    "header_prefix":row.header.get("normalized"),"header_text_id":header_id,
                    "header_handle":row.header.get("handle"),"header_coord":[row.header.get("x"),row.header.get("y")],"row_number":row_number,
                    "middle_value":row.row.get("normalized"),"middle_text_id":row_id,"middle_coord":[row.row.get("x"),row.row.get("y")],
                    "logical_endpoint":row.endpoint_identity,"row_number_sequence_valid":True,
                    "endpoint_column_authority":"superworks_reciprocal_row_reference","sw_row_id":row.record_id,
                    "left_value":None,"left_text_id":None,"right_value":destination,
                    "right_text_id":connection.get("text_id"),"has_shuoming_column":False,
                    "shuoming_text_id":None,"column_roles":{"left":"empty","middle":"row_number",
                    "right":"terminal_endpoint","description":"empty"},
                    "sw_branch":connection["branch"],"sw_side":connection["side"],
                    "endpoint_style":connection.get("style"),
                    "scope_key":f"{row.file_id}:{row.header.get('handle') or header_id}"}
                side=connection["side"]
                mapping.update({f"{side}_value":destination,f"{side}_text_id":connection.get("text_id"),f"{side}_coord":[connection.get("x"),connection.get("y")]})
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
                              "superworks":{"source":"superworks","row_id":row.record_id,
                                  "header_handle":row.header.get("handle"),"header_text_id":header_id,
                                  "row_handle":row.row_handle,"row_text_id":row_id,
                                  "connection_handle":connection.get("handle"),"connection_text_id":connection.get("text_id"),
                                  "side":side,"branch":connection["branch"],"endpoint_style":connection.get("style"),
                                  "validation":row.validation},
                              "ordinary_pair_eligible":False,"electrical_union_eligible":False}))
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
        values=[normalize(v.strip().strip("&")) for v in re.split(r"[,，]",label.text.get("value","")) if v.strip().strip("&")]
        part=next(p for p in data.part_instances if p.record_id==label.part_id)
        part_ports=[port for port in part.ports if str(port.get("port_number"))==str(label.port_number)
                    and port.get("endpoint_identity")==label.endpoint_identity]
        port=part_ports[0] if len(part_ports)==1 else {}
        line_id_by_handle={line.handle:line.line_id for line in lines}
        support_line_id=line_id_by_handle.get(label.line_handle)
        producer_groups=[g for g in groups_by_member.get(support_line_id,[]) if support_line_id] if support_line_id else []
        line_group_id=producer_groups[0].line_group_id if len(producer_groups)==1 else (old[0].line_group_id if old else None)
        new=[]
        for destination in values:
            evidence=copy.deepcopy(old[0].evidence) if old else {}
            evidence.update(structured_source="component_mapping",
                component_submode="superworks_connect_line_port",logical_endpoint=label.endpoint_identity,
                external_endpoint=destination,external_endpoint_raw=label.text.get("value"),
                external_endpoint_split=destination,external_endpoint_text_id=label.text.get("text_id"),
                component_body=part.block_name,component_body_text_id=part.label.get("text_id"),
                component_port=label.port_number,component_port_text_id=(port.get("pin") or {}).get("text_id"),
                component_block_name=part.block_name,line_group_id=line_group_id,
                supporting_line_ids=[support_line_id] if support_line_id else [],
                ordinary_pair_eligible=False,electrical_union_eligible=False,
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
    data.recognition_seconds=time.perf_counter()-started
    return output,mappings,ledger


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
