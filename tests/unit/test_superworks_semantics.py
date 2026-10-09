from __future__ import annotations

import math
from types import SimpleNamespace
from pathlib import Path

import ezdxf
import pytest
from ezdxf.math import Matrix44

from dwg_audit.domain.models import TextItem
from dwg_audit.extract.superworks_semantics import extract_superworks_semantics, bind_text_ids, read_project_dictionary


def xdata(entity, app, values):
    if app not in entity.doc.appids:
        entity.doc.appids.new(app)
    entity.set_xdata(app, values)


def symbol(doc, category, label_value, at=(0,0), pin_value=None, contacts=1, name=None, **kwargs):
    name=name or f"B{len(doc.blocks)}"
    block=doc.blocks.new(name)
    for number in range(1,contacts+1):
        marker=block.add_lwpolyline([(-.5+(number-1)*5,0),(.5+(number-1)*5,0)])
        xdata(marker,"LD_SYMB1LIB_TERMPOINT",[(1000,str(number))])
    insert=doc.modelspace().add_blockref(name,at,dxfattribs=kwargs)
    label=doc.modelspace().add_text(label_value,dxfattribs={"insert":(at[0],at[1]+3),"height":2})
    xdata(insert,"LD_SYMB2_SPECIAL",[(1000,category)])
    xdata(insert,"LD_SYMB2_LABEL",[(1005,label.dxf.handle)])
    xdata(label,"LD_SYMB2_LABEL",[(1005,insert.dxf.handle)])
    if pin_value is not None:
        pin=doc.modelspace().add_text(pin_value,dxfattribs={"insert":(at[0],at[1]+1),"height":2})
        for number in range(1,contacts+1):
            app=f"LD_SYMB2_TERM_TEXT_{number}"
            xdata(insert,app,[(1000,str(number)),(1005,pin.dxf.handle)])
            xdata(pin,app,[(1005,insert.dxf.handle)])
    return insert,label


def text_items(doc):
    return [TextItem(text_id="T"+e.dxf.handle,sheet_id="S1",file_id="F1",handle=e.dxf.handle,
        entity_type=e.dxftype(),text=e.dxf.text,normalized_text=e.dxf.text,is_numeric_candidate=True,
        layer=e.dxf.layer,rotation_deg=0,height=e.dxf.height,insert_x=e.dxf.insert.x,insert_y=e.dxf.insert.y,
        bbox_min_x=e.dxf.insert.x,bbox_min_y=e.dxf.insert.y,bbox_max_x=e.dxf.insert.x+3,bbox_max_y=e.dxf.insert.y+2)
        for e in doc.modelspace().query("TEXT")]


def extract(doc):
    data=extract_superworks_semantics(doc,sheet_id="S1",file_id="F1")
    bind_text_ids(data,text_items(doc))
    return data


@pytest.mark.parametrize("rotation,xscale,yscale",[(0,1,1),(90,1,1),(30,-2,.5),(180,3,2)])
def test_port_world_transform(rotation,xscale,yscale):
    doc=ezdxf.new()
    ins,_=symbol(doc,"端子","1XD2",at=(10,20),rotation=rotation,xscale=xscale,yscale=yscale)
    port=extract(doc).ports[0]
    a,b=ins.matrix44().transform_vertices([(-.5,0,0),(.5,0,0)])
    assert (port.start_x,port.start_y)==pytest.approx((a.x,a.y))
    assert (port.end_x,port.end_y)==pytest.approx((b.x,b.y))
    assert port.tolerance==pytest.approx(.6*math.hypot(b.x-a.x,b.y-a.y))


def test_shared_device_pin_is_one_identity_with_distinct_contacts():
    doc=ezdxf.new()
    symbol(doc,"装置端子","2-1n",pin_value="323",contacts=2)
    doc.modelspace().add_line((0,0),(5,0),dxfattribs={"layer":"CONNECT"})
    data=extract(doc)
    assert {p.endpoint_identity for p in data.ports}=={"2-1n323"}
    assert len({p.record_id for p in data.ports})==2
    assert all(p.validation["port_touched_by_wire"] for p in data.ports)
    assert not any(p.reason_codes for p in data.ports)


def test_nested_instance_paths_do_not_alias_definition_handles():
    doc=ezdxf.new()
    inner=doc.blocks.new("inner")
    marker=inner.add_lwpolyline([(-.5,0),(.5,0)])
    xdata(marker,"LD_SYMB1LIB_TERMPOINT",[(1000,"1")])
    block=doc.blocks.new("outer")
    nested=block.add_blockref("inner",(4,2),dxfattribs={"rotation":90})
    for pos in [(10,20),(30,20)]:
        ins=doc.modelspace().add_blockref("outer",pos,dxfattribs={"xscale":-2,"yscale":.5})
        label=doc.modelspace().add_text("TD10",dxfattribs={"insert":pos})
        xdata(ins,"LD_SYMB2_SPECIAL",[(1000,"端子")])
        xdata(ins,"LD_SYMB2_LABEL",[(1005,label.dxf.handle)])
        xdata(label,"LD_SYMB2_LABEL",[(1005,ins.dxf.handle)])
    data=extract(doc)
    assert len(data.ports)==2
    assert len({p.record_id for p in data.ports})==2
    assert len({p.marker_handle for p in data.ports})==1
    expected=(nested.matrix44() @ list(doc.modelspace().query("INSERT"))[0].matrix44()).transform((-.5,0,0))
    assert (data.ports[0].start_x,data.ports[0].start_y)==pytest.approx((expected.x,expected.y))


def test_dangling_stale_and_unattached_are_observable():
    doc=ezdxf.new()
    ins,label=symbol(doc,"端子","TD10")
    label.dxf.insert=(100,100,0)
    assert "stale_label_reference" in extract(doc).ports[0].reason_codes
    xdata(ins,"LD_SYMB2_LABEL",[(1005,"FFFF")])
    port=extract(doc).ports[0]
    assert "dangling_label_handle" in port.reason_codes
    assert port.validation["port_touched_by_wire"] is False


def test_contact_tolerance_rejects_adjacent_row_wire():
    doc=ezdxf.new()
    symbol(doc,"端子","TD10",at=(0,0))
    symbol(doc,"端子","TD11",at=(0,2))
    wire=doc.modelspace().add_line((0,0),(20,0))
    data=extract(doc)
    by_identity={p.endpoint_identity:p for p in data.ports}
    assert by_identity['TD10'].wire_contacts[0]['residual']==pytest.approx(.5)
    assert by_identity['TD10'].tolerance==pytest.approx(.6)
    assert by_identity['TD11'].wire_contacts==[]
    wire.dxf.start=(0,1,0)
    assert all(not p.wire_contacts for p in extract(doc).ports)


def test_dictionary_ranges_and_parse_failures(tmp_path):
    (tmp_path/"LdInfo.xml").write_text('<SuperWORKS><BOMITEM Label="3KLP1~3KLP3"/></SuperWORKS>',encoding="utf-8")
    (tmp_path/"LdDzbInfo.xml").write_text('<bad>',encoding="utf-8")
    result=read_project_dictionary(tmp_path)
    assert {"3KLP1","3KLP2","3KLP3"}.issubset(result["names"])
    assert result["files"]["LdDzbInfo.xml"].startswith("parse_failed")
    assert result["purpose"]=="warning_only"


def test_strip_second_branch_and_reciprocal_ownership():
    doc=ezdxf.new()
    msp=doc.modelspace()
    head=msp.add_text("1XD")
    row=msp.add_text("2")
    one=msp.add_text("2-1n323")
    two=msp.add_text("1DK-3")
    xdata(head,"LD_DZPHEAD_NOHANDLE",[(1005,row.dxf.handle)])
    xdata(row,"LD_DZPNO_HEADHANDLE",[(1005,head.dxf.handle)])
    for app,text in [("LDDZ_LEFTTEXT_HANDLE",one),("LDDZ_LEFTTEXT_HANDLE_2",two)]:
        xdata(row,app,[(1005,text.dxf.handle)])
        xdata(text,"LD_DZPTEXT_NOHANDLE",[(1005,row.dxf.handle)])
    data=extract(doc)
    assert data.strip_rows[0].endpoint_identity=="1XD2"
    assert len(data.strip_rows[0].connections)==2
    assert not data.strip_rows[0].reason_codes
    assert all(c['text_id'] for c in data.strip_rows[0].connections)


def test_internal_definition_ordinal_requires_strip_corroboration():
    from dwg_audit.domain.models import SwStripRow
    from dwg_audit.extract.superworks_semantics import corroborate_internal_pin_identities
    doc=ezdxf.new()
    symbol(doc,"内部元件","1DK")
    data=extract(doc)
    assert data.ports[0].endpoint_identity is None
    data.strip_rows.append(SwStripRow('R','S1','F1',row_handle='R',header={'resolved':True},
        validation={'reciprocal_ok':True},connections=[{'value':'1DK-1','style':'端子排内接元件','resolved':True,'reciprocal_ok':True,
        'handle':'C1','text_id':'TC','side':'right','branch':'_1'}]))
    corroborate_internal_pin_identities(data)
    assert data.ports[0].endpoint_identity=='1DK-1'
    assert data.ports[0].pin['resolution_method']=='strip_reverse_corroboration'
    assert data.ports[0].pin['corroborating_strip_text_ids']==['TC']
    assert data.pin_resolution_counts['strip_reverse_corroboration']==1


def test_internal_instance_term_text_is_first_resolution_method():
    from dwg_audit.extract.superworks_semantics import corroborate_internal_pin_identities
    doc=ezdxf.new()
    symbol(doc,"内部元件","1DK",pin_value="A1")
    data=extract(doc)
    corroborate_internal_pin_identities(data)
    assert data.ports[0].endpoint_identity=="1DK-A1"
    assert data.ports[0].pin["resolution_method"]=="instance_term_text"
    assert data.pin_resolution_counts["instance_term_text"]==1


def test_internal_definition_nearest_text_uses_world_transform_and_unique_nearest():
    from dwg_audit.extract.superworks_semantics import corroborate_internal_pin_identities
    doc=ezdxf.new()
    block=doc.blocks.new("PINPART")
    marker=block.add_lwpolyline([(-.5,0),(.5,0)])
    xdata(marker,"LD_SYMB1LIB_TERMPOINT",[(1000,"1")])
    pin_text=block.add_text("A1",dxfattribs={"insert":(.5,.6),"height":1})
    insert=doc.modelspace().add_blockref("PINPART",(10,20),dxfattribs={"rotation":90,"xscale":-2,"yscale":.5})
    xdata(insert,"LDPARTLAYT_PART",[(1000,"1")])
    label=doc.modelspace().add_text("1K",dxfattribs={"insert":(10,25),"height":2})
    xdata(insert,"LDPARTLAYT_PARTLABEL_HANDLE",[(1005,label.dxf.handle)])
    xdata(label,"LDPARTLAYT_PART_HANDLE",[(1005,insert.dxf.handle)])
    data=extract_superworks_semantics(doc,sheet_id="S1",file_id="F1")
    bind_text_ids(data,[SimpleNamespace(sheet_id="S1",file_id="F1",handle=pin_text.dxf.handle,
        insert_x=10.0,insert_y=18.8,text_id="TDEF")])
    corroborate_internal_pin_identities(data)
    port=data.part_instances[0].ports[0]
    expected=insert.matrix44().transform((.5,.6,0))
    assert port["endpoint_identity"]=="1K-A1"
    assert port["pin"]["resolution_method"]=="definition_text_nearest"
    assert (port["pin"]["x"],port["pin"]["y"])==pytest.approx((expected.x,expected.y))
    assert port["pin"]["text_id"]=="TDEF"
    assert data.pin_resolution_counts["definition_text_nearest"]==1


def test_component_handle_adjacency_is_not_geometric_proof():
    doc=ezdxf.new()
    msp=doc.modelspace()
    far=msp.add_line((0,4),(20,4))
    label=msp.add_text('TD10',dxfattribs={'insert':(20,0),'height':2})
    msp.add_line((100,100),(110,100))
    near=msp.add_line((0,0),(20,0))
    for entity in (far,label,near):
        xdata(entity,'LD_ConnectLine',[(1000,'1')])
    result=extract(doc).connect_labels[0]
    assert result.line_handle==far.dxf.handle
    assert 'connect_line_geometry_not_unique' in result.reason_codes


@pytest.mark.parametrize("fixture",["schematic","strip","component"])
def test_real_fixture_metadata_is_retained(fixture):
    path=Path(__file__).parents[1]/"fixtures/superworks"/f"{fixture}.dxf"
    doc=ezdxf.readfile(path)
    data=extract_superworks_semantics(doc,sheet_id="S1",file_id="F1")
    if fixture=="schematic":
        assert any(p.endpoint_identity=="2-1n323" for p in data.ports)
        assert any(p.endpoint_identity=="1XD2" and p.wire_contacts for p in data.ports)
    elif fixture=="strip":
        assert any(r.endpoint_identity=="1XD2" for r in data.strip_rows)
    else:
        assert data.part_instances and data.connect_labels
