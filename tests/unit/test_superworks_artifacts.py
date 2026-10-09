import json
from dataclasses import asdict

import ezdxf
import pandas as pd

from dwg_audit.desktop.preview import _build_svg,build_preview_geometry_payloads
from dwg_audit.report.superworks_artifacts import write_superworks_artifacts
from dwg_audit.domain.models import ProjectArtifacts,ProjectScanResult
from test_superworks_extractor import page,group,run
from test_superworks_semantics import symbol,extract


def test_empty_sw_tables_have_declared_columns(tmp_path):
    from dwg_audit.extract.superworks_semantics import SuperworksData
    from types import SimpleNamespace
    artifacts=SimpleNamespace(superworks=SuperworksData(),superworks_supersession=[],scan=SimpleNamespace(manifest=SimpleNamespace(project_id="P1"),pages=[]),pairs=[])
    write_superworks_artifacts(artifacts,tmp_path)
    assert pd.read_parquet(tmp_path/'sw_ports.parquet').empty
    assert 'record_id' in pd.read_parquet(tmp_path/'sw_ports.parquet').columns
    assert json.loads((tmp_path/'superworks_summary.json').read_text())['port_coverage']['ratio'] is None


def test_unknown_identity_cannot_be_consumed_by_matching_empty_values(tmp_path):
    from types import SimpleNamespace
    from dwg_audit.domain.models import SwPort
    from dwg_audit.extract.superworks_semantics import SuperworksData
    port=SwPort('P','S1','F1',category='装置端子',label={'resolved':True},wire_contacts=[{'wire_handle':'A'}])
    pair=SimpleNamespace(pair_id='PAIR',status='review',left_value=None,right_value=None,pair_kind='wire_component_mapping',
        evidence={'source':'superworks','superworks':{'left':{'port_ids':['P'],'value':None}}})
    artifacts=SimpleNamespace(superworks=SuperworksData(ports=[port]),superworks_supersession=[],
        scan=SimpleNamespace(manifest=SimpleNamespace(project_id='P1'),pages=[page()]),pairs=[pair])
    write_superworks_artifacts(artifacts,tmp_path)
    summary=json.loads((tmp_path/'superworks_summary.json').read_text(encoding='utf-8'))
    assert summary['port_coverage']['eligible']==1
    assert summary['port_coverage']['consumed']==0
    assert 'unresolved_endpoint_identity' in summary['port_coverage']['unconsumed'][0]['reason_codes']


def test_real_pair_and_port_proofs_survive_artifact_and_preview(tmp_path):
    from types import SimpleNamespace
    doc=ezdxf.new()
    symbol(doc,"端子","1XD2")
    symbol(doc,"装置端子","2-1n",at=(20,0),pin_value="323")
    doc.modelspace().add_line((0,0),(20,0))
    data=extract(doc)
    pairs,mappings,ledger=run(doc,data)
    artifacts=SimpleNamespace(superworks=data,superworks_supersession=ledger,scan=SimpleNamespace(manifest=SimpleNamespace(project_id="P1"),pages=[page()]),pairs=pairs)
    write_superworks_artifacts(artifacts,tmp_path)
    ports=pd.read_parquet(tmp_path/'sw_ports.parquet')
    payload=build_preview_geometry_payloads({'sw_ports':ports})[0]
    assert len(payload['sw_ports'])==2
    summary=json.loads((tmp_path/'superworks_summary.json').read_text(encoding='utf-8'))
    assert summary['port_coverage']['ratio']==1
    issue=pd.Series({'left_value':pairs[0].left_value,'right_value':pairs[0].right_value,'evidence':{'pair_evidence':pairs[0].evidence}})
    svg=_build_svg(pd.Series({'sheet_no':'1'}),pd.DataFrame(),pd.DataFrame(),pd.DataFrame(),(-5,-5,25,10),
        highlight={'start':(0,0),'end':(20,0)},issue_row=issue,line_semantics=None,cropped=True)
    assert 'superworks-ports' in svg and 'data-sw-port=' in svg
    from dwg_audit.desktop.state_store import DesktopStateStore
    from dwg_audit.desktop.preview import render_project_preview
    store=DesktopStateStore(tmp_path/'state.db')
    store.record_run(run_id='RUN',session_id='RUN',project_id='P1',project_name='test',input_root='source',artifact_dir=str(tmp_path),
                     status='completed',sheet_count=1,pair_count=1,issue_count=0,metadata={})
    frames={'pages':pd.DataFrame([asdict(page())]),'line_groups':pd.DataFrame([asdict(group())]),
            'pairs':pd.DataFrame([asdict(pairs[0])]),'sw_ports':ports}
    store.replace_preview_geometries('RUN',build_preview_geometry_payloads(frames))
    result=render_project_preview(project_id='P1',sheet_id='S1',line_group_id='GW1',state_db_path=tmp_path/'state.db',output_dir=tmp_path/'preview')
    assert 'superworks-ports' in result['preview_svg']
    assert '2-1n323' in result['preview_svg']
    # Component pins are retained in their part facts, not the schematic sw_ports table.
    from dwg_audit.domain.models import SwPartInstance
    part=SwPartInstance('PART','S1','F1',ports=[{'record_id':'PART-PIN','port_number':'3',
        'start_x':-.5,'start_y':0,'end_x':.5,'end_y':0}])
    pairs[0].evidence={'source':'superworks','superworks':{'part_id':'PART','port_number':'3'}}
    frames['pairs']=pd.DataFrame([asdict(pairs[0])])
    frames['sw_part_instances']=pd.DataFrame([asdict(part)])
    store.replace_preview_geometries('RUN',build_preview_geometry_payloads(frames))
    result=render_project_preview(project_id='P1',sheet_id='S1',line_group_id='GW1',state_db_path=tmp_path/'state.db',output_dir=tmp_path/'preview')
    assert 'data-sw-port="PART-PIN"' in result['preview_svg']
