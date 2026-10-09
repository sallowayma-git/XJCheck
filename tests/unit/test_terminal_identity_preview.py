from __future__ import annotations

import json
import math
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import ezdxf
import pandas as pd
import pytest

from dwg_audit.audit.candidates import build_terminal_candidates
from dwg_audit.audit.pairs import build_pairs
from dwg_audit.audit.page_extractors import extract_wire_pairs
from dwg_audit.audit.rules import build_issues
from dwg_audit.audit.symbol_port_proposal import propose_ports_from_block
from dwg_audit.desktop.preview import _build_svg, _make_view_transform, _resolve_focus_extent, build_preview_geometry_payloads, render_project_preview
from dwg_audit.desktop.state_store import DesktopStateStore
from dwg_audit.domain.models import LineGroup, ProjectScanResult, SheetRecord, SourceFileRecord, TextItem
from dwg_audit.extract.cad_extract import extract_cad_artifacts
from dwg_audit.extract.primitive_normalizer import normalize_document_primitives
from dwg_audit.extract.terminal_port_bindings import bind_labelled_terminal_ports
from dwg_audit.extract.text_geometry import cad_text_geometry
from dwg_audit.utils.config import DEFAULT_CONFIG


def _sheet():
    return SheetRecord("S1", "F1", "schematic.dwg", 1, "1", "Schematic", "二次原理图", "primary", "filename", True)


def _text(identity, value, x, y):
    return TextItem(identity, "S1", "F1", identity, "MTEXT", value, value, value.isdigit(), "TEXT", 0, 3, x, y, x, y-1, x+5, y+2)


def _group(start=(5., 0.), end=(17.5, 0.), orientation="horizontal"):
    return LineGroup("G1", "S1", "F1", *start, *end, math.dist(start, end), .7, orientation=orientation)


def _terminal_document(rotation=0., scale=1., mirror=1.):
    doc = ezdxf.new("R2018")
    for appid in ("LD_SYMB2_LABEL", "LD_SYMB2_SPECIAL"):
        doc.appids.add(appid)
    block = doc.blocks.new("UNSEEN_TERMINAL")
    block.add_circle((2.5, 0), 1.2)
    for a, b in [((0,0),(1.3,0)), ((3.7,0),(5,0)), ((2.5,-2.5),(2.5,-1.2)), ((2.5,2.5),(2.5,1.2)), ((1.071,-1.429),(3.953,1.453))]:
        block.add_line(a, b)
    for x, y in [(0,0),(5,0),(2.5,-2.5),(2.5,2.5)]:
        block.add_lwpolyline([(x-.5,y,1),(x+.5,y,1)], format="xyb", close=True, dxfattribs={"invisible": 1, "const_width": 2})
    insert = doc.modelspace().add_blockref(block.name, (30, 40), dxfattribs={"rotation": rotation, "xscale": scale*mirror, "yscale": scale})
    label = doc.modelspace().add_mtext("2YD7", dxfattribs={"insert": (41, 42.5), "char_height": 3, "attachment_point": 6})
    label.set_xdata("LD_SYMB2_LABEL", [(1005, insert.dxf.handle)])
    insert.set_xdata("LD_SYMB2_LABEL", [(1005, label.dxf.handle)])
    insert.set_xdata("LD_SYMB2_SPECIAL", [(1000, "端子")])
    text = replace(_text(label.dxf.handle, "2YD7", 41, 42.5), handle=label.dxf.handle)
    return doc, insert, label, text, propose_ports_from_block(block, definition_name=block.name)


@pytest.mark.parametrize("rotation,scale,mirror", [(0,1,1),(180,2,1),(0,1.5,-1),(90,2,1)])
def test_reciprocal_label_binds_transformed_outward_contact(rotation, scale, mirror):
    doc, insert, _, text, proposal = _terminal_document(rotation, scale, mirror)
    bind_labelled_terminal_ports(doc, [text], [proposal])
    ports = json.loads(text.physical_ports_json)
    assert len(ports) == 4
    port = ports[1]
    start = tuple(port["position"])
    direction = port["outward_direction"]
    end = (start[0]+12.5*direction[0], start[1]+12.5*direction[1])
    orientation = "vertical" if abs(direction[1]) > .9 else "horizontal"
    if orientation == "horizontal" and start[0] > end[0] or orientation == "vertical" and start[1] < end[1]:
        group = _group(end, start, orientation)
        side = "right" if orientation == "horizontal" else "bottom"
    else:
        group = _group(start, end, orientation)
        side = "left" if orientation == "horizontal" else "top"
    candidates = build_terminal_candidates([group], [text], DEFAULT_CONFIG, [_sheet()])
    bound = next(c for c in candidates if c.side == side)
    assert bound.status == "accepted"
    assert bound.physical_endpoint_evidence["insert_handle"] == insert.dxf.handle
    assert bound.distance_x == bound.distance_y == 0
    assert bound.physical_endpoint_evidence["electrical_union_eligible"] is False


@pytest.mark.parametrize("dx,dy", [(0,10),(12.5,0),(0,.5)])
def test_bound_label_cannot_be_borrowed_by_neighbor_wire(dx, dy):
    doc, _, _, text, proposal = _terminal_document()
    bind_labelled_terminal_ports(doc, [text], [proposal])
    group = _group((35+dx,40+dy),(47.5+dx,40+dy))
    candidates = build_terminal_candidates([group], [text], DEFAULT_CONFIG, [_sheet()])
    assert not any(c.status == "accepted" for c in candidates)


def test_broken_reciprocal_or_unrecognized_symbol_does_not_gain_port_authority():
    doc, insert, label, text, proposal = _terminal_document()
    label.set_xdata("LD_SYMB2_LABEL", [(1005, "FFFF")])
    bind_labelled_terminal_ports(doc, [text], [proposal])
    assert text.physical_ports_json == "[]"
    label.set_xdata("LD_SYMB2_LABEL", [(1005, insert.dxf.handle)])
    insert.set_xdata("LD_SYMB2_SPECIAL", [(1000, "装置端子")])
    bind_labelled_terminal_ports(doc, [text], [proposal])
    assert text.physical_ports_json == "[]"


def test_same_object_has_one_endpoint_but_equal_values_on_distinct_objects_are_valid():
    group = _group()
    candidates = build_terminal_candidates([group], [_text("A", "777", 17.8, .5)], DEFAULT_CONFIG, [_sheet()])
    _, pairs = build_pairs([group], candidates, [_sheet()], DEFAULT_CONFIG)
    assert pairs[0].left_text_id is None
    assert pairs[0].right_text_id == "A"
    assert pairs[0].status == "review"
    assert pairs[0].evidence["text_identity_decisions"]
    candidates = build_terminal_candidates([group], [_text("A", "777", 5, .5), _text("B", "777", 17.5, .5)], DEFAULT_CONFIG, [_sheet()])
    _, pairs = build_pairs([group], candidates, [_sheet()], DEFAULT_CONFIG)
    assert (pairs[0].left_text_id, pairs[0].right_text_id) == ("A", "B")
    assert pairs[0].left_value == pairs[0].right_value == "777"


def test_equidistant_single_label_stays_review_without_self_pair():
    group = _group()
    candidates = build_terminal_candidates([group], [_text("A", "777", 11.25, 0)], DEFAULT_CONFIG, [_sheet()])
    _, pairs = build_pairs([group], candidates, [_sheet()], DEFAULT_CONFIG)
    assert pairs[0].status == "review"
    assert pairs[0].left_text_id is pairs[0].right_text_id is None


def test_competing_independent_labels_keep_ambiguity():
    group = _group()
    candidates = build_terminal_candidates([group], [_text("A", "777", 5,0), _text("B", "778", 5,0), _text("C", "999",17.5,0)], DEFAULT_CONFIG, [_sheet()])
    _, pairs = build_pairs([group], candidates, [_sheet()], DEFAULT_CONFIG)
    assert pairs[0].status == "review"
    assert pairs[0].alternative_pair_candidate_ids


def test_mtext_right_middle_layout_and_rotated_text_geometry():
    doc = ezdxf.new()
    label = doc.modelspace().add_mtext("2YD7", dxfattribs={"insert": (11,2.5), "char_height": 3, "attachment_point": 6})
    geometry = cad_text_geometry(label)
    assert geometry["top_left"][0] < 11
    assert geometry["corners"][1][0] == 11
    label.dxf.rotation = 90
    assert cad_text_geometry(label)["rotation_deg"] == pytest.approx(90)


def test_unbounded_mtext_keeps_words_on_one_line():
    doc = ezdxf.new()
    label = doc.modelspace().add_mtext('Manual tripping',dxfattribs={'insert':(30,20),'char_height':2.5,'width':0,'attachment_point':7})
    geometry = cad_text_geometry(label)
    assert geometry['lines']==['Manual tripping']
    assert geometry['height']==pytest.approx(geometry['line_height'])
    assert geometry['width']==pytest.approx(geometry['line_widths'][0])
    assert geometry['top_left'][1]==pytest.approx(20+geometry['line_height'])


def test_wrapped_mtext_renders_each_line_at_its_own_width():
    doc = ezdxf.new()
    label = doc.modelspace().add_mtext('Long words then short\\PHi',dxfattribs={'insert':(0,0),'char_height':2.5,'width':15})
    geometry = cad_text_geometry(label)
    assert len(geometry['lines']) > 2
    assert geometry['lines'][-1]=='Hi'
    assert geometry['line_widths'][-1] < max(geometry['line_widths'])
    assert geometry['height']==pytest.approx(geometry['line_height']+geometry['line_spacing']*(len(geometry['lines'])-1))


def test_nested_scaled_circle_hatch_and_lines_render_without_placeholders():
    doc = ezdxf.new()
    inner = doc.blocks.new("INNER")
    inner.add_circle((1,1),1)
    hatch = inner.add_hatch(color=7)
    hatch.paths.add_polyline_path([(0,0),(2,0),(2,2),(0,2)], is_closed=True)
    inner.add_lwpolyline([(0,0),(4,0),(4,3)])
    inner.add_line((0,0),(1000,0),dxfattribs={"invisible":1})
    outer = doc.blocks.new("OUTER")
    outer.add_blockref("INNER",(1,0),dxfattribs={"rotation":90,"xscale":-1,"yscale":2})
    doc.modelspace().add_blockref("OUTER",(10,20),dxfattribs={"rotation":90})
    records = normalize_document_primitives(doc,sheet_id="S1",file_id="F1",reader_backend="ezdxf",reader_version="test")
    primitives = pd.DataFrame([asdict(r) for r in records])
    svg = _build_svg(pd.Series({"sheet_title":"Test"}),pd.DataFrame(),pd.DataFrame(),pd.DataFrame(),(0,0,30,40),highlight=None,issue_row=None,line_semantics=None,cropped=False,primitives=primitives)
    ET.fromstring(svg)
    assert 'data-kind="ELLIPSE"' in svg
    assert 'data-kind="HATCH"' in svg
    assert 'fill-rule="evenodd"' in svg
    assert 'BLOCK_GEOMETRY_UNAVAILABLE' not in svg
    assert len([r for r in records if r.primitive_kind=="LINE" and r.visible]) == 2


def test_invisible_contact_polyline_stays_invisible_after_expansion():
    doc, _, _, _, _ = _terminal_document()
    records = normalize_document_primitives(doc,sheet_id="S1",file_id="F1",reader_backend="ezdxf",reader_version="test")
    contacts = [r for r in records if r.source_entity_type=="LWPOLYLINE"]
    assert contacts and not any(r.visible for r in contacts)


def test_retained_primitives_survive_desktop_cleanup_without_entity_limits(tmp_path):
    doc, _, _, _, _ = _terminal_document()
    doc.modelspace().add_line((35,40),(47.5,40))
    records = normalize_document_primitives(doc,sheet_id="S1",file_id="F1",reader_backend="ezdxf",reader_version="test")
    frame = pd.DataFrame([asdict(r) for r in records]*3000)
    frames = {"primitive_segments": frame, "pages": pd.DataFrame([{**asdict(_sheet()),"frame_bbox": [20,30,60,60]}])}
    payload = build_preview_geometry_payloads(frames)[0]
    assert len(payload["primitive_segments"]) == len(frame)
    store = DesktopStateStore(tmp_path/"state.db")
    store.record_run(run_id="run",session_id="session",project_id="project",project_name="Project",input_root="input",artifact_dir=str(tmp_path/"deleted"),status="completed",sheet_count=1,pair_count=1,issue_count=0,metadata={})
    store.replace_preview_geometries("run",[payload])
    result = render_project_preview(project_id="project",sheet_id="S1",state_db_path=tmp_path/"state.db",output_dir=tmp_path/"preview")
    assert result["source"] == "sqlite_geometry"
    assert 'data-kind="CIRCLE"' in result["preview_svg"]
    assert '2YD7' in result["preview_svg"]


def test_real_dxf_target_uses_actual_extraction_and_pairing(tmp_path):
    source = Path(__file__).resolve().parents[2]/".tmp/tsb_full_replay/p044/cache/converted_dxf/F0010_635255ec.dxf"
    if not source.exists():
        pytest.skip("local real-project DXF unavailable")
    sheet = _sheet()
    scan = ProjectScanResult(SimpleNamespace(source_files=[]),[sheet],[],str(tmp_path))
    record = SourceFileRecord("F1",str(source),sheet.filename,".dwg","test",source.stat().st_size,1,"1","filename","Schematic","二次原理图",None,True,conversion_status="converted",dxf_path=str(source))
    logger = SimpleNamespace(info=lambda *a,**k:None)
    result = extract_cad_artifacts(scan,[record],DEFAULT_CONFIG,logger)
    group = _group((37.49487926599136,85),(49.99487926599136,85))
    candidates = build_terminal_candidates([group],result.texts,DEFAULT_CONFIG,[sheet])
    _, pairs = build_pairs([group],candidates,[sheet],DEFAULT_CONFIG)
    pair = pairs[0]
    assert (pair.left_value,pair.right_value)==("1XD2","323")
    assert pair.left_text_id != pair.right_text_id
    assert pair.evidence["selected_left_physical_endpoint"]["text_handle"]=="26F4E"
    assert pair.evidence["selected_left_physical_endpoint"]["electrical_union_eligible"] is False
    assert any(c.rejection_reason=="text_identity_owned_by_other_endpoint" for c in candidates)


@pytest.mark.parametrize("valid_body_reference", [True,False])
def test_actual_dxf_pipeline_separates_external_lead_from_device_interior(tmp_path, valid_body_reference):
    doc = ezdxf.new()
    for appid in ("LD_SYMB2_LABEL","LD_SYMB2_SPECIAL","LD_SYMB2_TERM_TEXT_1"):
        doc.appids.add(appid)
    terminal = doc.blocks.new("UNSEEN_ROUND_TERMINAL")
    terminal.add_arc((2.5,0),1.25,0,180)
    terminal.add_arc((2.5,0),1.25,180,360)
    for start,end in [((1.25,0),(0,0)),((3.75,0),(5,0))]:
        terminal.add_line(start,end)
        x,y=end
        terminal.add_lwpolyline([(x-.5,y,1),(x+.5,y,1)],format="xyb",close=True,dxfattribs={"invisible":1})
    pin_block = doc.blocks.new("UNSEEN_DEVICE_LABEL")
    pin_block.add_line((0,0),(2.5,0),dxfattribs={"layer":"校对"})
    space=doc.modelspace()
    space.add_lwpolyline([(0,0),(400,0),(400,300),(0,300)],close=True,dxfattribs={"layer":"BORDER"})
    space.add_lwpolyline([(145,185),(205,185),(205,215),(145,215)],close=True)
    body=space.add_text("7n",dxfattribs={"insert":(175,219.5),"height":2.5})
    space.add_text("ABC-123",dxfattribs={"insert":(165,215.7),"height":2.5})
    for number,y in ((611,200),(612,190)):
        insert=space.add_blockref(pin_block.name,(147.5,y))
        label=space.add_text(str(number),dxfattribs={"insert":(145.35,y+.66),"height":2.5})
        insert.set_xdata("LD_SYMB2_SPECIAL",[(1000,"装置端子")])
        insert.set_xdata("LD_SYMB2_TERM_TEXT_1",[(1005,label.dxf.handle)])
        label.set_xdata("LD_SYMB2_TERM_TEXT_1",[(1005,insert.dxf.handle)])
        insert.set_xdata("LD_SYMB2_LABEL",[(1005,body.dxf.handle if valid_body_reference else "FFFF")])
    insert=space.add_blockref(terminal.name,(127.5,190))
    label=space.add_mtext("WD5",dxfattribs={"insert":(132.5,187),"char_height":2.5})
    insert.set_xdata("LD_SYMB2_SPECIAL",[(1000,"端子")])
    insert.set_xdata("LD_SYMB2_LABEL",[(1005,label.dxf.handle)])
    label.set_xdata("LD_SYMB2_LABEL",[(1005,insert.dxf.handle)])
    space.add_line((132.5,190),(147.5,190),dxfattribs={"layer":"CONNECT"})
    space.add_line((150,190),(200,190))
    source=tmp_path/"device.dxf"
    doc.saveas(source)
    sheet=_sheet()
    scan=ProjectScanResult(SimpleNamespace(source_files=[]),[sheet],[],str(tmp_path))
    record=SourceFileRecord("F1",str(source),sheet.filename,".dwg","test",source.stat().st_size,1,"1","filename","Schematic","二次原理图",None,True,conversion_status="converted",dxf_path=str(source))
    cad=extract_cad_artifacts(scan,[record],DEFAULT_CONFIG,SimpleNamespace(info=lambda *a,**k:None))
    result=extract_wire_pairs([sheet],cad.texts,cad.lines,DEFAULT_CONFIG,blocks=cad.blocks)
    mapping=[p for p in result.pairs if p.left_value=="7n612" and p.right_value=="WD5"]
    issues=build_issues(result.pairs,result.line_groups,[sheet],DEFAULT_CONFIG,result.terminal_candidates)
    if valid_body_reference:
        assert len(mapping)==1 and mapping[0].status=="pass"
        assert mapping[0].left_text_id != mapping[0].right_text_id
        assert mapping[0].evidence["device_pin_label_context"]["complete_xrecord_binding"] is False
        assert not any(i.evidence.get("missing_side_classification")=="unresolved_physical_terminal_annotation" for i in issues)
    else:
        assert mapping==[]
        assert any(i.rule_id in {"R-PAIR-MISSING-SIDE","R-PAIR-LOW-CONFIDENCE"} for i in issues), [
            (p.pair_kind,p.left_value,p.right_value,p.status,p.evidence.get("component_submode")) for p in result.pairs]


def _three_contact_terminal_document():
    doc = ezdxf.new()
    for appid in ("LD_SYMB2_LABEL", "LD_SYMB2_SPECIAL"):
        doc.appids.add(appid)
    block = doc.blocks.new("UNSEEN_THREE_CONTACT")
    block.add_arc((0,0), 1.25, 0, 180)
    block.add_arc((0,0), 1.25, 180, 360)
    for inner, outer in [((0,-1.25),(0,-2.5)), ((0,1.25),(0,2.5)), ((1.25,0),(2.5,0))]:
        block.add_line(inner, outer)
        x, y = outer
        block.add_lwpolyline([(x-.5,y,1),(x+.5,y,1)], format="xyb", close=True, dxfattribs={"invisible":1})
    insert = doc.modelspace().add_blockref(block.name, (30,40))
    label = doc.modelspace().add_mtext("6YD8", dxfattribs={"insert":(41,42.5),"char_height":3,"attachment_point":6})
    label.set_xdata("LD_SYMB2_LABEL", [(1005,insert.dxf.handle)])
    insert.set_xdata("LD_SYMB2_LABEL", [(1005,label.dxf.handle)])
    insert.set_xdata("LD_SYMB2_SPECIAL", [(1000,"端子")])
    text = replace(_text(label.dxf.handle,"6YD8",41,42.5),handle=label.dxf.handle)
    return doc, block, insert, text


@pytest.mark.parametrize("rotation,scale,mirror", [(0,1,1),(90,2,-1)])
def test_three_contact_terminal_recovers_real_side_port(rotation, scale, mirror):
    doc, block, insert, text = _three_contact_terminal_document()
    insert.dxf.rotation = rotation
    insert.dxf.xscale = scale*mirror
    insert.dxf.yscale = scale
    proposal = propose_ports_from_block(block,definition_name=block.name)
    assert len(proposal.ports) == 2  # Principal-axis proposal omits the side.
    bind_labelled_terminal_ports(doc,[text],[proposal])
    ports = json.loads(text.physical_ports_json)
    assert len(ports) == 3
    matrix = insert.matrix44()
    expected = matrix.transform((2.5,0,0))
    port = next(p for p in ports if math.dist(p['position'],(expected.x,expected.y)) < .001)
    start = port['position']
    end = [start[i]+12.5*port['outward_direction'][i] for i in (0,1)]
    vertical = abs(end[1]-start[1]) > abs(end[0]-start[0])
    group = _group(tuple(start),tuple(end),'vertical' if vertical else 'horizontal')
    if not vertical and start[0]>end[0] or vertical and start[1]<end[1]:
        group = _group(tuple(end),tuple(start),group.orientation)
    candidates = build_terminal_candidates([group],[text],DEFAULT_CONFIG,[_sheet()])
    accepted = [c for c in candidates if c.status=='accepted']
    assert len(accepted) == 1
    assert accepted[0].physical_endpoint_evidence['family_rule']=='verified-three-radial-contact-terminal-v1'
    assert accepted[0].physical_endpoint_evidence['electrical_union_eligible'] is False


@pytest.mark.parametrize("damage", ['missing_contact','missing_lead','open_body','visible_contact','bent_lead'])
def test_three_contact_terminal_requires_complete_geometry(damage):
    doc, block, _, text = _three_contact_terminal_document()
    if damage=='missing_contact':
        block.delete_entity(list(block.query('LWPOLYLINE'))[-1])
    elif damage=='missing_lead':
        block.delete_entity(list(block.query('LINE'))[-1])
    elif damage=='open_body':
        list(block.query('ARC'))[-1].dxf.end_angle = 350
    elif damage=='visible_contact':
        list(block.query('LWPOLYLINE'))[-1].dxf.invisible = 0
    else:
        list(block.query('LINE'))[-1].dxf.start = (1.25,.5,0)
    bind_labelled_terminal_ports(doc,[text],[propose_ports_from_block(block,definition_name=block.name)])
    assert text.physical_ports_json=='[]'


@pytest.mark.parametrize("rotation,mirror", [(0,1),(90,-1),(180,1)])
def test_two_contact_terminal_accepts_cad_owned_alphanumeric_label(rotation, mirror):
    doc, block, insert, text = _three_contact_terminal_document()
    block.delete_entity(list(block.query('LINE'))[-1])
    block.delete_entity(list(block.query('LWPOLYLINE'))[-1])
    text.text = text.normalized_text = "WD5"
    insert.dxf.rotation = rotation
    insert.dxf.xscale = mirror
    bind_labelled_terminal_ports(doc, [text], [propose_ports_from_block(block, definition_name=block.name)])
    ports = json.loads(text.physical_ports_json)
    assert len(ports) == 2
    assert all(p['family_rule']=='verified-two-radial-contact-terminal-v1' for p in ports)
    start = ports[0]['position']
    end = [start[i]+12.5*ports[0]['outward_direction'][i] for i in (0,1)]
    vertical = abs(end[1]-start[1]) > abs(end[0]-start[0])
    if vertical and start[1] < end[1] or not vertical and start[0] > end[0]:
        start,end=end,start
    group = _group(tuple(start),tuple(end),'vertical' if vertical else 'horizontal')
    candidates = build_terminal_candidates([group],[text],DEFAULT_CONFIG,[_sheet()])
    accepted = [c for c in candidates if c.status=='accepted']
    assert len(accepted)==1 and accepted[0].value=='WD5'
    text.physical_ports_json='[]'
    assert not any(c.status=='accepted' and c.value=='WD5' for c in build_terminal_candidates([group],[text],DEFAULT_CONFIG,[_sheet()]))


@pytest.mark.parametrize('with_identity',[True,False])
def test_issue_crop_does_not_follow_repeated_labels_elsewhere(with_identity):
    texts = pd.DataFrame([
        {'text_id':'local','normalized_text':'777','insert_x':23,'insert_y':22,'text_geometry_json':json.dumps({'corners':[[15,24],[23,24],[23,20],[15,20]]})},
        {'text_id':'remote','normalized_text':'777','insert_x':900,'insert_y':900},
    ])
    issue = pd.Series({'left_value':'777','evidence':{'selected_left_text_id':'local'} if with_identity else {}})
    extent = _resolve_focus_extent(page_extent=(0,0,1000,1000),highlight={'start':(20,20),'end':(40,20)},issue_row=issue,texts=texts)
    assert extent[2] < 100 and extent[3] < 100
    assert extent[0] <= 15 and extent[3] >= 24


def test_issue_crop_keeps_selected_aligned_label_full_bounds():
    texts = pd.DataFrame([{'text_id':'label','normalized_text':'6YD8','insert_x':25,'insert_y':22,
                           'text_geometry_json':json.dumps({'corners':[[-10,25],[25,25],[25,20],[-10,20]]})}])
    issue = pd.Series({'left_value':'6YD8','evidence':{'selected_left_text_id':'label'}})
    extent = _resolve_focus_extent(page_extent=(-100,-100,200,200),highlight={'start':(20,20),'end':(40,20)},issue_row=issue,texts=texts)
    assert extent[0] < -10


def test_legacy_issue_crop_keeps_two_local_objects_with_same_value():
    texts = pd.DataFrame([
        {'text_id':'left','normalized_text':'777','insert_x':15,'insert_y':22,'text_geometry_json':json.dumps({'corners':[[-30,24],[15,24],[15,20],[-30,20]]})},
        {'text_id':'right','normalized_text':'777','insert_x':50,'insert_y':22,'text_geometry_json':json.dumps({'corners':[[50,24],[90,24],[90,20],[50,20]]})},
        {'text_id':'remote','normalized_text':'777','insert_x':900,'insert_y':900},
    ])
    issue = pd.Series({'left_value':'777','right_value':'777','evidence':{}})
    extent = _resolve_focus_extent(page_extent=(-100,-100,1000,1000),highlight={'start':(20,20),'end':(40,20)},issue_row=issue,texts=texts)
    assert extent[0] <= -30 and 90 <= extent[2] < 900


def test_hidden_layers_and_insert_attributes_remain_hidden():
    doc = ezdxf.new()
    doc.layers.new('OFF').off()
    doc.layers.new('FROZEN').freeze()
    inner = doc.blocks.new('INNER')
    inner.add_circle((0,0),1)  # Layer 0 inherits the outer insert's layer.
    inner.add_line((0,0),(5,0),dxfattribs={'layer':'FROZEN'})
    outer = doc.blocks.new('OUTER')
    outer.add_blockref('INNER',(0,0))
    hidden = doc.modelspace().add_blockref('OUTER',(20,20),dxfattribs={'layer':'OFF'})
    hidden.add_attrib('NAME','off-parent',(20,20))
    shown = doc.modelspace().add_blockref('INNER',(40,20))
    shown.add_attrib('ID','hidden-attribute',(40,20),dxfattribs={'flags':1})
    shown.add_attrib('ID2','visible-attribute',(42,20))
    records = normalize_document_primitives(doc,sheet_id='S1',file_id='F1',reader_backend='ezdxf',reader_version='test')
    circles = [r for r in records if r.primitive_kind=='CIRCLE']
    assert [r.visible for r in circles]==[False,True]
    assert not any(r.visible for r in records if r.primitive_kind=='LINE')
    attrs = {doc.entitydb[r.entity_handle].dxf.text:r.visible for r in records if r.primitive_kind=='ATTRIB'}
    assert attrs=={'off-parent':False,'hidden-attribute':False,'visible-attribute':True}


@pytest.mark.parametrize('xscale,yscale',[(-1,1),(1,-1),(-2,1)])
def test_mirrored_round_symbols_use_world_center_and_curve_direction(xscale, yscale):
    doc = ezdxf.new()
    block = doc.blocks.new('MIRRORED')
    block.add_circle((1,1),.5)
    block.add_arc((1,1),.5,0,90)
    insert = doc.modelspace().add_blockref(block.name,(10,20),dxfattribs={'xscale':xscale,'yscale':yscale,'rotation':30})
    virtual = list(insert.virtual_entities())
    records = normalize_document_primitives(doc,sheet_id='S1',file_id='F1',reader_backend='ezdxf',reader_version='test')
    frame = pd.DataFrame([asdict(r) for r in records])
    extent = (0,10,20,30)
    svg = _build_svg(pd.Series({'sheet_title':'Mirror'}),pd.DataFrame(),pd.DataFrame(),pd.DataFrame(),extent,highlight=None,issue_row=None,line_semantics=None,cropped=False,primitives=frame)
    root = ET.fromstring(svg)
    polyline = root.find('.//{http://www.w3.org/2000/svg}polyline')
    # The partial arc must follow its actual mirrored WCS endpoints. A full
    # ellipse can look right even when the direction of its quarter arc is wrong.
    if len(root.findall('.//{http://www.w3.org/2000/svg}polyline'))==2:
        polyline = root.findall('.//{http://www.w3.org/2000/svg}polyline')[-1]
    actual = [tuple(map(float,p.split(','))) for p in polyline.attrib['points'].split()]
    transform = _make_view_transform(extent)
    for point, expected in zip((actual[0],actual[-1]),(virtual[-1].start_point,virtual[-1].end_point)):
        assert point == pytest.approx((transform['tx'](expected.x),transform['ty'](expected.y)),abs=.02)
    if abs(xscale)==abs(yscale):
        circle = next(r for r in records if r.primitive_kind=='CIRCLE')
        center = insert.matrix44().transform((1,1,0))
        assert json.loads(circle.world_geometry_json)['center']==pytest.approx(list(center))
