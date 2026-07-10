# XJCheck 线网 V2 迁移检查表

## A. 环境与基线

- [ ] 安装并验证 ODA File Converter
- [ ] Reader 支持 Windows/Linux/AppImage
- [ ] 运行 27 项目 / 502 页 current-head baseline
- [ ] 保存 Git commit、config、backend version
- [ ] 生成每项目实体/Pair/Issue 指标
- [ ] 标记所有 incomplete extraction
- [ ] 冻结 legacy golden

## B. Reader Adapter

- [ ] `CadReader` 协议
- [ ] ODA reader
- [ ] DXF ezdxf reader
- [ ] RealDWG adapter stub
- [ ] LibreDWG adapter stub
- [ ] embedded preview reader
- [ ] capability/probe
- [ ] backend provenance
- [ ] cache key
- [ ] failure taxonomy

## C. Primitive Model

- [ ] LINE
- [ ] LWPOLYLINE
- [ ] POLYLINE
- [ ] ARC/CIRCLE
- [ ] INSERT/ATTRIB
- [ ] nested transform
- [ ] modelspace/paperspace
- [ ] entity handle lineage
- [ ] layer role candidate

## D. Geometry Graph

- [ ] endpoint index
- [ ] segment index
- [ ] endpoint-endpoint
- [ ] endpoint-on-segment
- [ ] segment intersection
- [ ] collinear overlap
- [ ] segment splitting
- [ ] dot detection
- [ ] jumper/bridge detection
- [ ] topology four states
- [ ] decision trace
- [ ] ASSERTED-only network builder

## E. Symbols

- [ ] block frequency report
- [ ] definition hash/fingerprint
- [ ] external entry clustering
- [ ] symbol schema
- [ ] symbol registry
- [ ] port transform
- [ ] internal connectivity
- [ ] text slots
- [ ] unknown symbol queue
- [ ] migrate all hard-coded block names

## F. Semantics

- [ ] token parser
- [ ] `.prj` project profile
- [ ] `LdDzbInfo.xml` terminal vocabulary
- [ ] text role
- [ ] scope resolver
- [ ] text-to-port candidates
- [ ] text-to-net candidates
- [ ] top-k alternatives
- [ ] confidence margin

## G. Constraint Resolver

- [ ] OR-Tools dependency
- [ ] port one-net constraint
- [ ] terminal token uniqueness
- [ ] symbol isolation constraint
- [ ] rejected edge constraint
- [ ] cross-page one-to-one/reciprocal
- [ ] soft score objective
- [ ] second-best/ambiguity
- [ ] decision export

## H. Cross-page and Audit

- [ ] EndpointIdentity canonicalization
- [ ] CrossPageEndpoint
- [ ] candidate generation
- [ ] reciprocal matching
- [ ] project graph
- [ ] conflict rules
- [ ] issue clustering
- [ ] witness path
- [ ] weakest evidence
- [ ] hard/review gate

## I. Page Strategies

- [ ] multi-label page capabilities
- [ ] backplate enters audit
- [ ] terminal table pipeline
- [ ] component symbol-first pipeline
- [ ] communication medium
- [ ] unknown page review path
- [ ] metadata-only pages

## J. Failure Loop

- [ ] full failure queue
- [ ] visual review tiles
- [ ] human labels
- [ ] label-to-symbol workflow
- [ ] label-to-topology fixture
- [ ] label-to-model dataset
- [ ] engine comparison
- [ ] per-project metrics

## K. Learning Gate

- [ ] project-held-out split locked
- [ ] deterministic baseline stable
- [ ] ranker baseline
- [ ] probability calibration
- [ ] shadow deployment
- [ ] no critical issue from model alone
- [ ] GNN only after proven gain

## L. Release Gate

- [ ] hard issue precision ≥99%
- [ ] zero critical from unresolved topology
- [ ] zero critical from unknown high-impact symbols
- [ ] 100% witness completeness
- [ ] held-out project report
- [ ] rollback to legacy verified
