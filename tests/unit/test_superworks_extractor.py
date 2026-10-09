from __future__ import annotations

from dataclasses import replace
import math

import ezdxf
import pytest

from dwg_audit.audit.superworks_extractor import extract_superworks_pairs
from dwg_audit.domain.models import Pair, SheetRecord, LineGroup, LineEntity, SwConnectDot
from dwg_audit.extract.superworks_semantics import SuperworksData
from test_superworks_semantics import symbol,extract,text_items,xdata


def page():
    return SheetRecord("S1","F1","test.dwg",1,"1","test","二次原理图","primary","filename",True,audit_disposition="audit")


def group():
    return LineGroup("GW1","S1","F1",0,0,20,0,20,1)


def pair():
    return Pair("PW1","GW1","S1","F1",None,"323","323",.7,"review","legacy",left_text_id="same",right_text_id="same")


def run(doc,data,old=None,groups=None,mappings=None):
    return extract_superworks_pairs(data,pages=[page()],texts=text_items(doc),lines=[],line_groups=groups or [group()],pairs=old or [pair()],table_mappings=mappings or [])


def test_metadata_replaces_wrong_pair_and_preserves_old_snapshot():
    doc=ezdxf.new()
    symbol(doc,"端子","1XD2")
    symbol(doc,"装置端子","2-1n",at=(20,0),pin_value="323")
    doc.modelspace().add_line((0,0),(20,0),dxfattribs={"layer":"CONNECT"})
    old=pair()
    result,_,ledger=run(doc,extract(doc),[old])
    new=result[0]
    assert (new.left_value,new.right_value,new.pair_kind,new.status)==("1XD2","2-1n323","wire_component_mapping","pass")
    assert new.evidence["source"]=="superworks"
    assert new.pair_id=="PW1"
    assert old.left_value=="323" and old.evidence=={}
    assert ledger[0]["category"]=="B"
    assert ledger[0]["old_pair"]["right_text_id"]=="same"


def test_partial_endpoint_keeps_legacy_values():
    doc=ezdxf.new()
    symbol(doc,"端子","1XD2")
    doc.modelspace().add_line((0,0),(20,0))
    old=pair()
    result,_,_=run(doc,extract(doc),[old])
    assert (result[0].left_value,result[0].right_value,result[0].status)==(old.left_value,old.right_value,old.status)
    assert result[0].evidence["superworks"]["partial"]


def test_uncovered_result_is_unchanged():
    doc=ezdxf.new()
    old=pair()
    result,_,ledger=run(doc,SuperworksData(),[old])
    assert result==[old] and result[0] is old and ledger==[]


def test_dangling_reference_is_review_and_auditable():
    doc=ezdxf.new()
    insert,_=symbol(doc,"端子","1XD2")
    symbol(doc,"装置端子","2-1n",at=(20,0),pin_value="323")
    xdata(insert,"LD_SYMB2_LABEL",[(1005,"FFFF")])
    result,_,ledger=run(doc,extract(doc))
    assert result[0].status=="review"
    assert "dangling_label_handle" in result[0].evidence["sw_conflicts"]
    assert ledger[0]["category"]=="D"
    from dwg_audit.audit.rules import build_issues
    issues=build_issues(result,[group()],[page()],{"rules":{"enable":[]}})
    assert any(i.rule_id=="R-SUPERWORKS-CONFLICT" for i in issues)


def test_physical_competition_is_review_separated_same_names_are_allowed():
    doc=ezdxf.new()
    symbol(doc,"端子","1XD2")
    symbol(doc,"端子","1XD2",at=(0,40))
    symbol(doc,"端子","TD10",at=(20,0))
    doc.modelspace().add_line((0,0),(20,0))
    result,_,_=run(doc,extract(doc))
    assert result[0].status=="pass"
    symbol(doc,"端子","TD11",at=(0,0))
    result,_,_=run(doc,extract(doc))
    assert result[0].status=="review"
    assert "competing_physical_port_identities" in result[0].evidence["sw_conflicts"]


def test_dictionary_unknown_does_not_demote_pair():
    doc=ezdxf.new()
    symbol(doc,"端子","1XD2")
    symbol(doc,"端子","TD10",at=(20,0))
    doc.modelspace().add_line((0,0),(20,0))
    data=extract(doc)
    data.dictionary={"names":["something_else"]}
    result,_,_=run(doc,data)
    assert result[0].status=="pass"
    assert result[0].evidence["sw_dictionary_warnings"]["effect"]=="warning_only"


def test_strip_parallel_branches_are_separate_production_mappings():
    from dwg_audit.domain.models import SwStripRow
    row=SwStripRow("ROW","S1","F1",row_handle="A",endpoint_identity="1XD2",
        header={"handle":"B","normalized":"1XD","text_id":"TH"},row={"handle":"A","normalized":"2","text_id":"TR"},
        connections=[{"value":v,"normalized":v,"handle":h,"text_id":"T"+h,"side":"left","branch":branch} for v,h,branch in [("2-1n323","C","_1"),("1DK-3","D","_2")]])
    data=SuperworksData(strip_rows=[row])
    old=replace(pair(),pair_kind="table_mapping",left_text_id="TR",right_text_id="TC",evidence={"table_mapping":{"middle_text_id":"TR","header_text_id":"TH"}})
    result,mappings,ledger=run(ezdxf.new(),data,[old])
    assert len(result)==2 and {p.right_value for p in result}=={"2-1n323","1DK-3"}
    assert all(p.status=="pass" for p in result)
    assert len(mappings[0]["mappings"])==2
    assert len(ledger[0]["new_pairs"])==2
    from dwg_audit.audit.rules import _high_confidence_source_eligible
    assert all(_high_confidence_source_eligible(p) for p in result)
    assert {(p.evidence["superworks"]["side"],p.evidence["superworks"]["branch"]) for p in result}=={("left","_1"),("left","_2")}
    from dwg_audit.domain.models import Pair
    from dwg_audit.audit.rules import build_issues
    from dwg_audit.utils.config import load_config
    ordinary=Pair("PSW-WIRE","GW1","S1","F1",None,"1XD2","2-1n323",.99,"pass","verified",
        confidence_bucket="high",pair_kind="ordinary_pair",evidence={"source":"superworks","ordinary_pair_eligible":True,
            "superworks":{"source":"superworks","left":{"value":"1XD2","category":"端子","port_ids":["P1"],"wire_touched":True},
                "right":{"value":"2-1n323","category":"装置端子","port_ids":["P2"],"wire_touched":True}}})
    issues=build_issues([*result,ordinary],[],[page()],load_config(None))
    assert not any(issue.rule_id=="R-TABLE-MAPPING-SOURCE-CONFLICT" for issue in issues)
    assert not any(issue.rule_id=="R-DUPLICATE-PAIR" for issue in issues)


def test_same_strip_terminal_link_uses_bridge_mapping_and_leaves_ordinary_index():
    from dwg_audit.domain.models import SwStripRow
    doc=ezdxf.new()
    symbol(doc,"端子","1ID1")
    symbol(doc,"端子","1ID2",at=(20,0))
    doc.modelspace().add_line((0,0),(20,0),dxfattribs={"layer":"CONNECT"})
    data=extract(doc)
    header={"handle":"H1","text_id":"TH1","normalized":"1ID","resolved":True}
    data.strip_rows=[SwStripRow("R1","S1","F1",row_handle="R1",header=header,row={"text_id":"TR1","normalized":"1"},endpoint_identity="1ID1",validation={"reciprocal_ok":True}),
        SwStripRow("R2","S1","F1",row_handle="R2",header=header,row={"text_id":"TR2","normalized":"2"},endpoint_identity="1ID2",validation={"reciprocal_ok":True})]
    output,_,_=run(doc,data)
    new=next(p for p in output if p.evidence.get("source")=="superworks")
    assert (new.pair_kind,new.status)==("bridge_mapping","pass")
    assert new.evidence["ordinary_pair_eligible"] is False
    assert new.evidence["bridge_mapping_kind"]=="superworks_terminal_strip_same_header"
    from dwg_audit.audit.rules import _ordinary_pair_eligible
    assert not _ordinary_pair_eligible(new)
    data.strip_rows[1].header={"handle":"H2","text_id":"TH2","normalized":"1ID","resolved":True}
    output,_,_=run(doc,data)
    cross_strip=next(p for p in output if p.evidence.get("source")=="superworks")
    assert cross_strip.pair_kind=="ordinary_pair" and cross_strip.status=="pass"


def test_unpaired_metadata_wire_is_coverage_only_without_production_pair():
    doc=ezdxf.new()
    symbol(doc,"端子","1XD2")
    entity=doc.modelspace().add_line((0,0),(20,0),dxfattribs={"layer":"CONNECT"})
    line=LineEntity("L1","S1","F1",entity.dxf.handle,"LINE","CONNECT",0,0,20,0,20,0,0,0,20,0)
    data=extract(doc)
    groups=[]
    output,_,ledger=extract_superworks_pairs(data,pages=[page()],texts=text_items(doc),lines=[line],
        line_groups=groups,pairs=[],table_mappings=[])
    assert output==[] and ledger==[]
    assert len(groups)==1 and groups[0].line_group_id.startswith("GWSW")
    assert any(item["line_group_origin"]=="metadata_wire_reference" and item["identity_resolved"]
        for item in data.coverage_observations)


def test_network_multi_endpoint_retains_all_alternatives_without_selecting_one():
    doc=ezdxf.new()
    symbol(doc,"端子","1XD2")
    symbol(doc,"端子","TD10",at=(20,0))
    symbol(doc,"端子","TD11",at=(5,20))
    raw=[]
    for index,(a,b) in enumerate([((0,0),(5,0)),((5,0),(20,0)),((5,0),(5,20))]):
        e=doc.modelspace().add_line(a,b,dxfattribs={"layer":"CONNECT"})
        raw.append(LineEntity(f"L{index}","S1","F1",e.dxf.handle,"LINE","CONNECT",*a,*b,
            length=math.hypot(b[0]-a[0],b[1]-a[1]),angle_deg=0,bbox_min_x=min(a[0],b[0]),bbox_min_y=min(a[1],b[1]),bbox_max_x=max(a[0],b[0]),bbox_max_y=max(a[1],b[1])))
    g=replace(group(),end_x=5,length=5,member_line_ids=["L0"])
    output,_,_=extract_superworks_pairs(extract(doc),pages=[page()],texts=text_items(doc),lines=raw,line_groups=[g],pairs=[pair()],table_mappings=[])
    original=next(p for p in output if p.line_group_id=="GW1")
    assert original.status=="review"
    assert original.right_value==pair().right_value
    assert original.evidence["superworks"]["right"]["candidate_values"]==["TD10","TD11"]


def test_metadata_touched_wire_omitted_by_legacy_gets_stable_reference():
    doc=ezdxf.new()
    symbol(doc,"端子","1XD2")
    symbol(doc,"装置端子","2-1n",at=(20,0),pin_value="323")
    e=doc.modelspace().add_line((0,0),(20,0),dxfattribs={"layer":"CONNECT"})
    line=LineEntity("L1","S1","F1",e.dxf.handle,"LINE","CONNECT",0,0,20,0,20,0,0,0,20,0)
    groups=[]
    result,_,ledger=extract_superworks_pairs(extract(doc),pages=[page()],texts=text_items(doc),lines=[line],line_groups=groups,pairs=[],table_mappings=[])
    assert len(groups)==1 and groups[0].member_line_ids==["L1"]
    assert result[0].status=="pass" and result[0].left_value=="1XD2" and result[0].right_value=="2-1n323"
    assert ledger[0]["old_pair"] is None and ledger[0]["category"]=="A"


def test_port_without_real_wire_cannot_promote_legacy_pair():
    doc=ezdxf.new()
    symbol(doc,"端子","1XD2")
    symbol(doc,"端子","TD10",at=(20,0))
    result,_,_=run(doc,extract(doc))
    assert result[0].status=="review"
    assert "port_not_touched_by_wire" in result[0].evidence["superworks"]["left"]["reason_codes"]
    assert not result[0].evidence.get("sw_conflicts")


def test_conflicted_strip_pair_cannot_become_high_confidence_audit_fact():
    from dwg_audit.audit.rules import _high_confidence_source_eligible
    conflict=replace(pair(),pair_kind="table_mapping",status="review",evidence={"source":"superworks","sw_conflicts":["invalid_strip_header_reference"]})
    assert _high_confidence_source_eligible(conflict) is False


def test_two_metadata_destinations_replacing_one_legacy_pair_have_unique_ids():
    from dwg_audit.domain.models import SwPartInstance,SwConnectLabel
    part=SwPartInstance("PART","S1","F1",insert_handle="A",label={"handle":"B","text_id":"TB"})
    connections=[SwConnectLabel(f"C{n}","S1","F1",text={"handle":f"H{n}","text_id":"DEST","value":value},
                    part_id="PART",port_number=str(n),endpoint_identity=f"1DK-{n}") for n,value in [(1,"ZD1"),(2,"ZD2")]]
    old=replace(pair(),pair_kind="component_mapping",right_text_id="DEST")
    output,_,ledger=run(ezdxf.new(),SuperworksData(part_instances=[part],connect_labels=connections),[old])
    assert len(output)==2 and len({p.pair_id for p in output})==2
    assert {p.left_value for p in output}=={"1DK-1","1DK-2"}
