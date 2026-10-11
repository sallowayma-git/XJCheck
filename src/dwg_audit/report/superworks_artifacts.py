"""Production semantic facts and physical-port consumption accounting."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, fields

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from dwg_audit.audit.superworks_cross_page import build_cross_page_links, short_bridge_pairs
from dwg_audit.domain.models import SwSymbolInstance, SwPort, SwStripRow, SwPartInstance, SwConnectLabel, SwConnectDot


def write_superworks_artifacts(artifacts, findings_dir):
    data=artifacts.superworks
    if data is None:
        return
    specs=(("sw_symbols","symbols",SwSymbolInstance),("sw_ports","ports",SwPort),
           ("sw_strip_rows","strip_rows",SwStripRow),("sw_part_instances","part_instances",SwPartInstance),
           ("sw_connect_labels","connect_labels",SwConnectLabel),("sw_connect_dots","connect_dots",SwConnectDot))
    for filename,attr,cls in specs:
        rows=[]
        for item in getattr(data,attr):
            row=asdict(item)
            row["project_id"]=artifacts.scan.manifest.project_id
            for key,value in row.items():
                if isinstance(value,(list,dict,tuple)):
                    row[key]=json.dumps(value,ensure_ascii=False)
            rows.append(row)
        columns=["project_id",*[f.name for f in fields(cls)]]
        float_fields={"start_x","start_y","end_x","end_y","insert_x","insert_y","x","y","tolerance"}
        schema=pa.schema([(name,pa.float64() if name in float_fields else pa.string()) for name in columns])
        pq.write_table(pa.Table.from_pandas(pd.DataFrame(rows,columns=columns),schema=schema,preserve_index=False),findings_dir/f"{filename}.parquet")
    ledger=[]
    for row in artifacts.superworks_supersession:
        ledger.append({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in row.items()})
    ledger_columns=["element_key","category","reason","old_pair","new_pairs"]
    pq.write_table(pa.Table.from_pandas(pd.DataFrame(ledger,columns=ledger_columns),schema=pa.schema([(name,pa.string()) for name in ledger_columns]),preserve_index=False),findings_dir/"superworks_supersession.parquet")

    # F1: same-identity wire groups are diagnostics only.  They never become
    # production pairs, so they are reported here instead of in the pair table.
    diagnostics=[item for item in data.conflict_observations if item.get("kind")=="self_connection"]
    diagnostic_columns=["kind","reason_code","detail","identity","file_id","sheet_id","line_group_id","line_group_origin",
        "left_symbol_id","right_symbol_id","left_port_ids","right_port_ids","left_port_number","right_port_number",
        "left_coord","right_coord","split_at_port","split_result","member_line_ids"]
    diagnostic_rows=[{key:(json.dumps(value,ensure_ascii=False) if isinstance(value,(list,dict,tuple))
                      else value if isinstance(value,str) else ("" if value is None else str(value)))
                      for key,value in item.items()} for item in diagnostics]
    pq.write_table(pa.Table.from_pandas(pd.DataFrame(diagnostic_rows,columns=diagnostic_columns),
        schema=pa.schema([(name,pa.string()) for name in diagnostic_columns]),preserve_index=False),
        findings_dir/"sw_diagnostics.parquet")

    consumption=defaultdict(list)
    bindings=defaultdict(list)
    coverage_observations=defaultdict(list)
    for observation in data.coverage_observations:
        coverage_observations[observation.get("port_id")].append(observation)
    two_endpoint_ports=set()
    observed_groups=defaultdict(lambda:{"left":False,"right":False,"ports":set()})
    for observation in data.coverage_observations:
        group=(observation.get("file_id"),observation.get("sheet_id"),observation.get("line_group_id"))
        item=observed_groups[group]
        if observation.get("identity_resolved"):
            item[observation.get("endpoint_side")]=True
            item["ports"].add(observation.get("port_id"))
    for item in observed_groups.values():
        if item["left"] and item["right"]:
            two_endpoint_ports.update(item["ports"])
    sw_consumption=defaultdict(list)
    for pair in artifacts.pairs:
        sw=pair.evidence.get("superworks") or {}
        is_sw=pair.evidence.get("source")=="superworks" or sw.get("source")=="superworks"
        for side in ("left","right"):
            endpoint=sw.get(side) or {}
            for port_id in endpoint.get("port_ids",[]):
                binding={"pair_id":pair.pair_id,"side":side,"status":pair.status,
                    "value_matches":bool(endpoint.get("value")) and str(getattr(pair,f"{side}_value") or "").casefold()==str(endpoint.get("value") or "").casefold(),
                    "source":"superworks" if is_sw else pair.evidence.get("source")}
                bindings[port_id].append(binding)
                if pair.status!="discard":
                    consumption[port_id].append(binding)
                    if is_sw:
                        sw_consumption[port_id].append(binding)
    pages={p.sheet_id:p for p in artifacts.scan.pages}
    rows=[]
    for port in data.ports:
        if port.category not in ("端子","装置端子"):
            continue
        page=pages.get(port.sheet_id)
        eligible=bool(port.wire_contacts and port.label.get("resolved"))
        used=consumption.get(port.record_id,[])
        used=[u for u in used if u["value_matches"]]
        sw_used=[u for u in sw_consumption.get(port.record_id,[]) if u["value_matches"]]
        observations=coverage_observations.get(port.record_id,[])
        reasons=list(port.reason_codes)
        if not used:
            if not port.wire_contacts:
                reasons.append("no_wire_contact")
            elif page and (page.audit_disposition in ("skip_stable","classify_only") or page.audit_role=="skip"):
                reasons.append("page_not_in_pair_audit")
            elif not port.endpoint_identity:
                reasons.append("unresolved_endpoint_identity")
            elif not (port.label if port.category=="端子" else port.pin).get("text_id"):
                reasons.append("endpoint_text_not_extracted")
            else:
                reasons.append("no_matching_production_pair")
        rows.append({"port_id":port.record_id,"sheet_id":port.sheet_id,"file_id":port.file_id,"category":port.category,
            "page_type":page.page_type if page else None,"endpoint_identity":port.endpoint_identity,
            "eligible":eligible,"consumed":bool(used),"pass":any(u["status"]=="pass" for u in used),
            "production_pairs":used,"sw_production_pair_consumed":bool(sw_used),
            "sw_production_pairs":sw_used,"main_two_end_eligible":port.record_id in two_endpoint_ports,
            "main_two_end_consumed":port.record_id in two_endpoint_ports and bool(sw_used),
            "wire_group_observations":observations,"reason_codes":sorted(set(reasons))})
    # X2 continuity: a target port that is the far end of a connection the terminal-strip page already
    # records. It is counted as a second, additive coverage figure; `consumed` (pairs only) is unchanged.
    cross_page=_cross_page_continuity(artifacts,data)
    for row in rows:
        link_ids=cross_page["covered"].get(row["port_id"],[])
        row["continuity_link_ids"]=link_ids
        row["consumed_with_continuity"]=bool(row["consumed"] or (row["eligible"] and link_ids))
    eligible=[r for r in rows if r["eligible"]]
    by_page=[]
    for sid in sorted({r["sheet_id"] for r in rows}):
        items=[r for r in eligible if r["sheet_id"]==sid]
        by_page.append({"sheet_id":sid,"page_type":pages[sid].page_type,"eligible":len(items),
                        "consumed":sum(r["consumed"] for r in items),"pass":sum(r["pass"] for r in items)})
    # Comparison denominator distinguishes absent strip rows from actual disagreement.
    strip_lookup=defaultdict(list)
    for row in data.strip_rows:
        if row.endpoint_identity:
            for connection in row.connections:
                values={value.strip().strip("&").casefold()
                        for value in connection.get("normalized",connection.get("value","")).replace("，",",").split(",")
                        if value.strip().strip("&")}
                strip_lookup[row.endpoint_identity.casefold()].append({"row":row,"connection":connection,"values":values})
    port_category_by_id={port.record_id:port.category for port in data.ports}
    category_by_identity=defaultdict(set)
    for port in data.ports:
        if port.endpoint_identity:
            category_by_identity[port.endpoint_identity.casefold()].add(port.category)
    for label in data.connect_labels:
        if label.endpoint_identity:
            category_by_identity[label.endpoint_identity.casefold()].add("内部元件")
    comparisons=[]
    for pair in artifacts.pairs:
        sw=pair.evidence.get("superworks") or {}
        if (pair.evidence.get("source")!="superworks" and sw.get("source")!="superworks") or pair.pair_kind not in ("ordinary_pair","bridge_mapping","wire_component_mapping"):
            continue
        for side,other in (("left","right"),("right","left")):
            endpoint=sw.get(side) or {}
            if endpoint.get("category")!="端子":
                continue
            terminal=getattr(pair,f"{side}_value")
            target=getattr(pair,f"{other}_value")
            owner_rows=strip_lookup.get((terminal or "").casefold(),[])
            target_categories={port_category_by_id.get(port_id) for port_id in (sw.get(other) or {}).get("port_ids",[])}
            target_categories.update(category_by_identity.get((target or "").casefold(),set()))
            if target_categories & {"内部元件","线圈","接插件"}:
                expected_side="right"
            elif target_categories & {"端子","装置端子"}:
                expected_side="left"
            else:
                expected_side=None
            slots=[item for item in owner_rows if item["connection"].get("side")==expected_side] if expected_side else []
            by_slot=defaultdict(list)
            for item in slots:
                connection=item["connection"]
                by_slot[(item["row"].record_id,connection.get("side"),connection.get("branch"))].append(item)
            if not owner_rows:
                comparisons.append({"pair_id":pair.pair_id,"sheet_id":pair.sheet_id,"terminal":terminal,"target":target,
                    "status":"missing_row","strip_side":expected_side,"strip_branch":None,"row_scope":None,"strip_destinations":[]})
                continue
            if not target or not expected_side or not by_slot:
                comparisons.append({"pair_id":pair.pair_id,"sheet_id":pair.sheet_id,"terminal":terminal,"target":target,
                    "status":"uncomparable","strip_side":expected_side,"strip_branch":None,"row_scope":None,
                    "strip_destinations":sorted({v for item in owner_rows for v in item["values"]})})
                continue
            parallel_slots=len(by_slot)>1
            for (row_id,slot_side,branch),items in sorted(by_slot.items()):
                values=set().union(*(item["values"] for item in items))
                match=(target or "").casefold() in values
                status="agree" if match else "uncomparable" if parallel_slots else "disagree"
                row=items[0]["row"]
                comparisons.append({"pair_id":pair.pair_id,"sheet_id":pair.sheet_id,"terminal":terminal,"target":target,
                    "status":status,"strip_side":slot_side,"strip_branch":branch,"row_scope":f"{row.file_id}:{row.row_handle}",
                    "strip_destinations":sorted(values),"target_categories":sorted(str(v) for v in target_categories if v)})
    coverage_columns=["port_id","sheet_id","file_id","category","page_type","endpoint_identity","eligible","consumed","pass",
        "production_pairs","sw_production_pair_consumed","sw_production_pairs","main_two_end_eligible","main_two_end_consumed",
        "wire_group_observations","reason_codes","continuity_link_ids","consumed_with_continuity"]
    pd.DataFrame(rows,columns=coverage_columns).assign(
        production_pairs=lambda f:f.production_pairs.map(lambda v:json.dumps(v,ensure_ascii=False)),
        sw_production_pairs=lambda f:f.sw_production_pairs.map(lambda v:json.dumps(v,ensure_ascii=False)),
        wire_group_observations=lambda f:f.wire_group_observations.map(lambda v:json.dumps(v,ensure_ascii=False)),
        reason_codes=lambda f:f.reason_codes.map(lambda v:json.dumps(v,ensure_ascii=False)),
        continuity_link_ids=lambda f:f.continuity_link_ids.map(lambda v:json.dumps(v,ensure_ascii=False))).to_parquet(findings_dir/"sw_port_coverage.parquet",index=False)
    _write_cross_page_tables(findings_dir,cross_page)
    main_eligible=[r for r in rows if r["main_two_end_eligible"]]
    summary={"schema_version":2,"project_id":artifacts.scan.manifest.project_id,
        "counts":{attr:len(getattr(data,attr)) for _,attr,_ in specs},
        "port_coverage":{"eligible":len(eligible),"consumed":sum(r["consumed"] for r in eligible),"pass":sum(r["pass"] for r in eligible),
                         "bound_in_evidence":sum(bool(bindings[r["port_id"]]) for r in eligible),
                         "binding_status_counts":dict(Counter(b["status"] for r in eligible for b in bindings[r["port_id"]])),
                         "ratio":sum(r["consumed"] for r in eligible)/len(eligible) if eligible else None,"by_page":by_page,
                         "unconsumed":[r for r in eligible if not r["consumed"]],
                         "main_two_end":{"eligible":len(main_eligible),"consumed_by_superworks":sum(r["main_two_end_consumed"] for r in main_eligible),
                             "ratio":sum(r["main_two_end_consumed"] for r in main_eligible)/len(main_eligible) if main_eligible else None,
                             "by_page_type":_coverage_by_page(main_eligible,pages)}},
        "port_coverage_with_continuity":_continuity_coverage(eligible),
        "cross_page":{"stats":cross_page["stats"],"link_count":len(cross_page["links"]),
            "candidate_counts":dict(Counter(c["candidate"] for c in cross_page["candidates"])),
            "note":"continuity links count as coverage in port_coverage_with_continuity only; they create no pairs"},
        "strip_agreement":{"counts":dict(Counter(r["status"] for r in comparisons)),"by_side_branch":_agreement_by_slot(comparisons),"comparisons":comparisons},
        "dictionary":data.dictionary,"timing":{"extraction_seconds":data.extraction_seconds,"recognition_seconds":data.recognition_seconds},
        "pin_resolution_counts":data.pin_resolution_counts,
        "self_connection_diagnostics":{
            "total":len(diagnostics),
            "by_reason_code":dict(Counter(item.get("reason_code") for item in diagnostics)),
            "by_detail":dict(Counter(item.get("detail") for item in diagnostics)),
            "split_at_port":sum(1 for item in diagnostics if item.get("split_at_port")),
            "note":"same-identity wire groups are diagnostics only and produce no production pair"},
        "supersession_categories":dict(Counter(r["category"] for r in artifacts.superworks_supersession))}
    (findings_dir/"superworks_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")


def _coverage_by_page(rows,pages):
    output={}
    for row in rows:
        page=pages.get(row["sheet_id"])
        key=f"{page.page_type if page else 'unknown'}"
        item=output.setdefault(key,{"eligible":0,"consumed":0})
        item["eligible"]+=1
        item["consumed"]+=int(row["main_two_end_consumed"])
    for item in output.values():
        item["ratio"]=item["consumed"]/item["eligible"] if item["eligible"] else None
    return output


def _agreement_by_slot(comparisons):
    grouped=defaultdict(Counter)
    for item in comparisons:
        key=(item.get("strip_side") or "unknown",item.get("strip_branch") or "unknown")
        grouped[key][item["status"]]+=1
    return {f"{side}:{branch}":dict(counts) for (side,branch),counts in sorted(grouped.items())}


def _cross_page_continuity(artifacts,data):
    """Continuity links of the terminal-strip cross-page references (see audit/superworks_cross_page.py)."""
    pages=getattr(getattr(artifacts,"scan",None),"pages",[]) or []
    strips=[{"record_id":r.record_id,"sheet_id":r.sheet_id,"file_id":r.file_id,"endpoint_identity":r.endpoint_identity,
        "connections":r.connections,"cross_page_refs":r.cross_page_refs} for r in getattr(data,"strip_rows",[]) or []]
    ports=[{"record_id":p.record_id,"file_id":p.file_id,"sheet_id":p.sheet_id,"insert_handle":p.insert_handle,
        "port_number":p.port_number,"endpoint_identity":p.endpoint_identity,"category":p.category,
        "has_wire_contact":bool(p.wire_contacts)} for p in getattr(data,"ports",[]) or []]
    pairs=[]
    for pair in artifacts.pairs:
        sw=(getattr(pair,"evidence",None) or {}).get("superworks") or {}
        pairs.append({"pair_id":pair.pair_id,"status":getattr(pair,"status",None),"sheet_id":getattr(pair,"sheet_id",None),
            "left_value":getattr(pair,"left_value",None),"right_value":getattr(pair,"right_value",None),
            "left_text_id":getattr(pair,"left_text_id",None),"right_text_id":getattr(pair,"right_text_id",None),
            "left_port_ids":list((sw.get("left") or {}).get("port_ids") or []),"right_port_ids":list((sw.get("right") or {}).get("port_ids") or [])})
    page_rows=[{"file_id":p.file_id,"sheet_no":p.sheet_no} for p in pages]
    # XPAGE-2: rows joined by a short bridge drawn on their strip page are electrically equivalent.
    bridge_rows=[{"record_id":r.record_id,"file_id":r.file_id,"group":(r.header or {}).get("handle"),
        "x":(r.row or {}).get("x"),"y":(r.row or {}).get("y")} for r in getattr(data,"strip_rows",[]) or []]
    bridge_lines=[{"file_id":l.file_id,"x0":l.start_x,"y0":l.start_y,"x1":l.end_x,"y1":l.end_y}
        for l in getattr(artifacts,"lines",[]) or []]
    bridges=short_bridge_pairs(bridge_rows,bridge_lines)
    return build_cross_page_links(strips,ports,pairs,page_rows,bridges=bridges)


def _write_cross_page_tables(findings_dir,cross_page):
    for name,records in (("sw_cross_page_links",cross_page["links"]),("sw_cross_page_candidates",cross_page["candidates"])):
        rows=[{key:(json.dumps(value,ensure_ascii=False) if isinstance(value,(list,dict)) else value) for key,value in record.items()} for record in records]
        frame=pd.DataFrame(rows) if rows else pd.DataFrame(columns=["link_id"])
        frame.to_parquet(findings_dir/f"{name}.parquet",index=False)


def _continuity_coverage(eligible):
    """Coverage of eligible terminal ports with pairs and continuity links (the additive figure)."""
    consumed=sum(r["consumed_with_continuity"] for r in eligible)
    return {"eligible":len(eligible),"consumed":consumed,"pairs_only_consumed":sum(r["consumed"] for r in eligible),
        "added_by_continuity":consumed-sum(r["consumed"] for r in eligible),
        "ratio":consumed/len(eligible) if eligible else None}
