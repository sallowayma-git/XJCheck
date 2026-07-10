# Findings V2 字段与版本策略

## 1. 原则

- 原始事实与推理结论分离；
- 所有决策可追溯；
- 不确定性一等公民；
- 规则重跑不重新读图；
- 版本升级可迁移；
- 任何最终 Issue 能反查原始 DWG handle。

## 2. 核心对象

### PrimitiveSegment

```text
segment_id, sheet_id, entity_handle, parent_handle, entity_type,
start, end, curve_type, layer, linetype, block_path,
source_space, provenance, bbox
```

### TopologyDecision

```text
decision_id, sheet_id, relation_type, object_a, object_b,
state, rule_score, symbol_score, model_score,
final_confidence, reason_codes, evidence_ids, run_id
```

### SymbolPort

```text
port_id, symbol_instance_id, family_id, local_coord, world_coord,
direction, electrical_role, internal_group, confidence
```

### ElectricalNetwork

```text
network_id, sheet_id, member_edges, junctions, symbol_ports,
open_endpoints, possible_boundaries, total_length, bbox,
network_confidence, weakest_evidence
```

### SemanticAttachment

```text
attachment_id, token_id, target_type, target_id, role,
score, selected, alternatives, reason_codes
```

### CrossPageMatch

```text
match_id, source_endpoint, target_endpoint, identity,
direction, reciprocal, score, selected, alternatives
```

## 3. Schema version

```text
findings_schema_version: 2.0.0
reader_contract_version: 1.0.0
topology_contract_version: 1.0.0
symbol_library_version: yyyy.mm.patch
rule_scheme_version: project/version
```

MAJOR：字段语义不兼容；  
MINOR：新增可选字段；  
PATCH：不改变 schema 的算法修复。

## 4. Cache key

```text
reader_cache = sha256(file) + reader_backend + reader_version + reader_options
geometry_cache = reader_cache + topology_config_version
symbol_cache = geometry_cache + symbol_library_version
semantic_cache = symbol_cache + project_profile_version
rule_cache = semantic_cache + rule_scheme_version
```

## 5. 决策日志

所有自动选择保存：

- 候选集合；
- selected；
- rejected；
- hard constraint；
- score breakdown；
- second-best；
- algorithm/version。
