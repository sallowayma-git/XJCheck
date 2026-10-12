# P2-BACKPLATE：背板虚拟端子表的 SW 身份与佐证调研

分支 `superworks-loop`。只读调研：未修改 `src/`、`tests/`，未执行 git，未删除任何 `.tmp` 目录。数据为第二十三轮全量回放 `.tmp/superworks_round23_full`（77 个项目），未读取 `round24_full`。冻结 DXF 经 `corpus_manifest.json` 只读访问。控制台 `PYTHONIOENCODING=utf-8`。

## 0. 结论摘要

1. **SW 并非对这些行完全盲区。** LEGACY-CENSUS 的 D3 背板行（非重复、无 SW 同值配对）中，5,571 条里有 **4,986 条（89.5%）在同一页上已有 SW pass 配对连着同一个外部端子 R**，且 SW 给出的背板端口身份行号与 V1 行号一致。两者只是左端文字写法不同（V1 `1-1n/NR1181C-3` 对 SW `1n0503`，外部端子都是 `TD9`）。LEGACY-CENSUS 用“值对完全相等”判重，漏掉了这一类。随机置换对照的偶然一致率只有 2.6%。
2. **可以用 SW 行号佐证的合计 5,156 条（92.5%）**：同页 4,986、他页或端子排去向 132、背板内部链路 38。
3. **真正矛盾的候选 310 条（5.6%）**：同页行号冲突 32 条（集中在 GJ-76 与 N2604 的背板几何表），行号一致但设备前缀不同 278 条（集中在 N2604，多数页面上的设备标签与 SW 一致、与 V1 复合设备名不一致）。抽样 10 例中 **3 例倾向判为 V1 错误**（J4、J5、J6），**2 例无法在当前分辨率下判定**（J7、J8），其余 5 例与 SW 一致或仅有 V1 行对齐（J1–J3、J9、J10）。
4. **仍只靠 V1 的 105 条（1.9%）**：90 条在 SW 中完全无对应（GJ-80 占 69 条，GJ-73 占 19 条，外部端子多为 KLP/CLP 类），另 15 条 SW 只给出非背板的对端。
5. **建议**：把“外部端子 R + 行号 + 设备前缀”作为一种 SW 佐证键，先做**只加证据、不改 pass** 的升级（方案 A）；矛盾候选（方案 B）进入 review，不直接降级；纯 V1 行（方案 C）保持现状。不建议直接把 5,544 条降为 review，那会丢掉约 5,000 条已经被 SW 同端子覆盖的连接身份，也会误伤行号一致的正确行。

## 1. 背板虚拟表的结构（渲染核对）

渲染了 10 个页面，覆盖 N2604、GJ-73、GJ-75、GJ-76、GJ-80 五个家族（PAC-885 与变压器测控柜未渲染，仅通过统计覆盖）。图形见 `png/P2BP_judge_1..3.png`。

- 表格由背板 INSERT 块（如 `PCS-931SA-G`、`NKR302`、`NJL307`）拼成，每个块有页眉文字（功能码或信号名，如 `NR1181C`、`NKR302`、`BI2`）和列内行号（`01`、`03`…）。
- 行号列的左侧是装置内部的端子/信号名，右侧是外部端子去向（如 `TD9`、`1KLP8-2`、`7U1D68`）。外部端子文字在页面外侧，行号与外部端子按水平线对齐。
- V1 的映射是：复合设备名（`composite_device_instance`，如 `1-1n`）+ 页眉前缀（`NR1181C`）+ 行号 → 逻辑端 `1-1n/NR1181C-3`，与外部端子 R 配对。`table_extractor.py::_build_backplate_virtual_mappings`（约 1541 行起）即此路径。
- 几何表（`backplate_geometric_table`）同样是行对齐，但行号可能竖排成两个文字，例如 `32` 被读成 `02`（见 J6）。

**列含义（外部端子 R 侧）：** 外部端子 R 是本页外侧的端子标号，同时在端子排页上以 `TERMINAL STRIP` 行身份出现，其“去向”文字 `connections` 给出 SW 对背板端口的身份。这是本调研的关键元数据（见 §2）。

## 2. 元数据可用性

| 元数据 | 本轮是否核验 | 结论 |
|---|---|---|
| SW 背板端口身份（`sw_ports`，同页 `endpoint_identity`，形如 `1n0503`、`3-21n532`） | 是 | 背板页本身有 SW 端口与 `PCS-931SA-G` 类部件实例（`sw_part_instances`），同页 SW pass 配对可直接取到 |
| SW 端子排行（`sw_strip_rows`，`endpoint_identity` + 去向 `connections`） | 是 | 如 p073 中 `TD9` 行去向为 `1n0503`，与背板端口一致。该去向覆盖外部端子 R |
| 跨页引用（`cross_page_refs`，`LD_SYMB2_TERM` 类） | 是 | 只用于定位，未作为佐证键 |
| `LD_PARTCONNECTLINE`（背板表格页 18,584 条） | 否，仅引用 ATTR-CENSUS | 可能给出逻辑端与线号，本轮未关联，列为后续核验 |
| 装置前缀（`composite_device_instance`） | 是 | 它是 V1 自己推的，它在 278 条行中与 SW 设备前缀不一致，是 V1 身份错误的主要来源候选 |

结论：背板页与端子排页之间存在“外部端子 R”这一共同键。这一键在 SW 中是可靠的（端子排行身份经 reciprocal 校验）。不需要新的 XDATA 解析即可用。

## 3. 连接关系判定方法（离线，可复现）

对每条背板 pass 配对（`table_mapping`，`mapping_mode=backplate_virtual_table`，共 15,402 条），以 R 为键取三类 SW 证据：

- E1：同页 SW pass 配对中一端等于 R，另一端为 SW 端口身份；
- E2：他页 SW pass 配对中一端等于 R；
- E3：端子排行 `endpoint_identity == R` 的去向文字。

行号判定：SW 背板身份取后两位为行号（数字式 `<dev><列><行>`，或字母式 `<dev>n<字母><行>`）；设备前缀去掉 `N-` 与尾部字母后比较（`1-1n` 与 `1nP` 视为同设备）。

分类：`AGREE_SAME_SHEET`、`AGREE_OTHER_SHEET`、`ROW_AGREE_DEV_DIFF`、`CONFLICT_SAME_SHEET`、`PARTNER_NONBP_ONLY`、`NO_SW_PARTNER`，以及 R 本身是背板身份时的 `INTERNAL_*`。

## 4. 离线评估（D3 类子集，5,571 条）

| 类别 | 条数 | 占比 | 处理建议 |
|---|---:|---:|---|
| AGREE_SAME_SHEET（同页 SW 同端子、行号一致） | 4,986 | 89.5% | 方案 A：保留 pass，加 SW 佐证证据 |
| AGREE_OTHER_SHEET（他页/去向，行号一致） | 132 | 2.4% | 方案 A（证据较弱，标注来源） |
| INTERNAL_AGREE（R 为背板身份，行号一致） | 38 | 0.7% | 方案 A |
| ROW_AGREE_DEV_DIFF（行号一致、设备前缀不同） | 225 | 4.0% | 方案 B：矛盾候选，需判定是 V1 设备错还是 SW 设备错 |
| INTERNAL_ROW_AGREE_DEV_DIFF | 53 | 1.0% | 方案 B |
| CONFLICT_SAME_SHEET（同页 SW 行号不同） | 32 | 0.6% | 方案 B，优先复核 |
| PARTNER_NONBP_ONLY + INTERNAL 对应 | 15 | 0.3% | 方案 C |
| NO_SW_PARTNER | 90 | 1.6% | 方案 C，保持 V1 |

各家族分布见 `details.json` 的 `classes_by_family`。ROW_AGREE_DEV_DIFF 集中在 N2604（225 条，主要在 p057、p067、p072 三个项目，各约 75 条），属于同一批复制页的同一种设备前缀问题；CONFLICT_SAME_SHEET 主要在 GJ-76 几何表（22 条）与 N2604（10 条）。

**对照。** 同页行号一致率：真实 89.5%，置换对照 2.6%。他页/去向的限制子集：真实 26.8%（157/585），置换对照 1.1%。行号规则在统计上显著，但它只检验行号与设备前缀，不检验列（`col`），所以它是“行号佐证”而非完整身份佐证。

**与 LEGACY-CENSUS 的差异。** 该普查把 D3 背板行描述为 SW 盲区（“96% 无 SW 对应”）。本调研用外部端子 R 连接后，这个说法只对约 90 条成立（NO_SW_PARTNER）；绝大多数是左端文字写法不同。这需要在 LEGACY-CENSUS 的 README 中更正，但本次只写在本目录，不改那边的文件。

## 5. 抽样判定（10 例，目视）

| 编号 | 项目/配对 | 类别 | 判定 |
|---|---|---|---|
| J1 | p007 P0073 | AGREE_SAME_SHEET | 一致 |
| J2 | p065 P0001 | AGREE_SAME_SHEET | 一致 |
| J3 | p001 P0073 | AGREE_OTHER_SHEET | 一致（弱） |
| J4 | p057 P0003 | ROW_AGREE_DEV_DIFF | 倾向 V1 设备前缀错误：页上 `7n601`、`7n` 标签与 SW `7n205` 一致，V1 复合设备 `1-1n` 不符 |
| J5 | p072 P0082 | ROW_AGREE_DEV_DIFF | 倾向 V1 设备前缀错误（页上 `4n1101`、`4n1103`）；分辨率低，中等把握 |
| J6 | p023 P0105 | CONFLICT_SAME_SHEET | 倾向 V1 行号误读：R 旁印的是 `32`，V1 取了 `02`；SW `832` 与页面一致 |
| J7 | p063 P0061 | CONFLICT_SAME_SHEET | 无法判定，需放大 |
| J8 | p058 P0073 | CONFLICT_SAME_SHEET | 无法判定（17 与 18 差一行），需放大 |
| J9 | p039 | PARTNER_NONBP_ONLY | V1 行对齐看起来一致；SW 只给出非背板对端，不能佐证 |
| J10 | p001 P0007 | NO_SW_PARTNER | V1 行对齐看起来一致；无 SW 对应，保持 V1 |

截图：`png/P2BP_judge_1.png`（J1–J4）、`png/P2BP_judge_2.png`（J5–J8）、`png/P2BP_judge_3.png`（J9–J10）。判定是人工目视，不是电气验证。

## 6. 泛化：新图纸如何识别

- **身份格式。** SW 背板身份的后两位即行号，在 N2604、GJ-73、GJ-75、GJ-76、GJ-80 中都成立。已见两种变体：字母式（`1-25nA24`）和带 `P` 的设备名（`1nP103`）。未知格式不应被当作佐证，而应列为 unknown。当前实现对未知格式返回 `nonbp`，即不佐证也不矛盾。
- **跨页对齐。** 对齐键是外部端子 R 的文字，而不是页序或页面位置。R 在端子排页上以 `endpoint_identity` 出现，这一点对所有家族都成立，因为端子排是 SW 的 reciprocal 结构。
- **表格结构。** 识别依赖 `source_block_name` 的虚拟 INSERT、页眉文字与行号文字。几何表（`backplate_geometric_table`）与虚拟表是两个子类型，新图纸若两者都不匹配，应标记为 unknown 表格而不是硬套。
- **设备前缀。** 这是最不稳的一环。页面上的设备标签（`7n601`、`4n1101`）应优先于 V1 的复合推断。若页面上不存在可读的设备标签，应退回到 SW 行号一致即可，不以前缀为准。

## 7. 实施建议

1. **方案 A（先做）**：在 SW 回放后、供给层之前，对每条 `backplate_virtual_table` pass 配对，按 R 查同页 SW pass 与端子排去向，行号（及可用的设备前缀）一致时，给配对加 `sw_corroborated_by_external_endpoint` 证据，保持 pass。改动位置：`superworks_semantics.py` 中背板端口身份与端子排去向索引（约 467、483 行附近），以及 `rules.py` 的背板 scope 检查（约 2007–2023、3326 行附近）。预计影响 5,156 条证据，不改 pass 数。
2. **方案 B（复核）**：ROW_AGREE_DEV_DIFF 与 CONFLICT_SAME_SHEET 生成 review 级 issue（建议 `R-BACKPLATE-IDENTITY-CONFLICT`），附 SW 身份与 V1 身份。在 `table_extractor.py::_resolve_backplate_device_instance` 处排查设备前缀推断，N2604 的复制页是首要回归样本（p057、p067、p072）。
3. **方案 C（保持）**：NO_SW_PARTNER 与 PARTNER_NONBP_ONLY 保持 V1，不因本调研降级。
4. **不建议**：仅凭行号一致就把 V1 行降为 review；也不建议以 `1n0503` 对 `1-1n/NR1181C-3` 的字面相等做去重，因为二者字面不同，必须经行号+R 的键。

## 8. 风险

- 行号只比较后两位，列（`col`）未比较。同一行号若对应不同列，会被误判为一致。
- 同一外部端子可能合法地连接多个背板端口（例如 `1YD` 类端子），他页的“行号不一致”不一定是矛盾。方案 B 必须只用同页证据或设备前缀也冲突的情况。
- 行号文字可能竖排或被误读（J6），V1 与 SW 任一方都可能错。判定矛盾前需要放大核对。
- 样本只覆盖 10 例，J7、J8 未定，因此矛盾候选的精度尚未确定。若要给出精度，需对 CONFLICT_SAME_SHEET 全量（32 条）与 ROW_AGREE_DEV_DIFF 分层抽样复核。
- 方案 A 的收益依赖 SW 同页 pass 本身正确。若 SW 的配对错，V1 的行映射会被误背书。

## 9. 文件与复现

- `details.json`：分类汇总、家族分布、对照、方案离线数字、10 例判定。
- `png/P2BP_judge_1..3.png`：10 例目视面板（≤20 张的上限内，共 3 张）。
- `tools/`：`load_common.py`（路径与解析）、`classify.py`（连接与分类，产出 `bp_class.csv`）、`control.py`（置换对照）、`cases.py`（抽样）、`render_cases.py` 与 `make_figs.py`（渲染）、`fam.py`（家族映射）。复现顺序：`fam` → `classify` → `control` → `make_figs judge`。
- 中间表（可删）：`.tmp/p2bp_work/`，含 `bp_class.csv`、`bp_join.csv`、`cases.json`、`fam.json`、`summary.json`。
