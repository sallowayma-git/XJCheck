# Phase 98 人工裁决清单

生成时间：2026-07-08

数据来源：

- first findings：`.tmp/phase97_coverage_first_v2/WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA/findings`
- first audit：`.tmp/phase97_coverage_first_v2_audit`
- second findings：`.tmp/phase97_coverage_second_v2/2_2/findings`
- second audit：`.tmp/phase97_coverage_second_v2_audit`

本文件目的：只列需要人工裁决的结构边界。已明确可由现有规则解释的关系不要求逐条标注。

## 如何回复

请按 `Hxx` 编号回复。每个编号只需要给出业务裁决，不需要写代码方案。

推荐回复格式：

```text
H01: 这些行应按同一物理导线网络补全，裸数字不是独立端子；优先通过线网连通找对端。
H03: 逗号拆分后的多个 component_mapping 是正常分支，默认不应作为用户问题，只保留 internal review。
```

如果某一类你暂时不能裁决，可以回复“需要截图/局部预览”，我再为对应页生成坐标定位或截图任务。

## 总体结论

T0 coverage 已证明文本侧没有未解释队列：

- first：`unexplained_numeric_texts=0`，但 `unassigned_wire_segments=6868`、`unclassified_blocks=1034`。
- second：`unexplained_numeric_texts=0`，但 `unassigned_wire_segments=5305`、`unclassified_blocks=1126`。

因此下一步人工裁决重点不是“哪个数字没被 OCR/文本抽到”，而是：

- 断开的线段是否属于同一电气网络。
- 局部裸数字是否需要结合页面/区域/元件前缀生成完整端。
- 一对多/多对一是实际分支，还是抽取误配。
- 常见 `INSERT` 块族应该归为符号、端口、表格、图框或纯注释。

## 全页扫描状态

### first 项目

| 页 | 文件 | 当前关系/问题状态 | 是否需要人工 |
|---|---|---|---|
| S0005 | 04 交流回路图1.dwg | 6 条 ordinary missing-side，裸数字 `701/703/705/707/709/711` | 是，见 H01 |
| S0006 | 05 交流回路图2.dwg | 8 条 ordinary missing-side，裸数字 `701/703/705/707/709/719/720/721` | 是，见 H01 |
| S0007 | 06 直流回路图.dwg | 3 条 `101 -> ?`，4 条 `132 -> 132` low-confidence | 是，见 H02 |
| S0009 | 08 差动保护及信号回路.dwg | `14 -> ?`、`? -> 13` | 是，见 H01/H06 |
| S0010 | 09 高后备保护及信号回路.dwg | `125/124/14/13` 缺侧 | 是，见 H01/H06 |
| S0011 | 10 低后备保护及信号回路.dwg | `125/124/14/13` 缺侧 | 是，见 H01/H06 |
| S0012 | 11 非电量开入回路.dwg | `601/310/309/308/307/210/209/208/207` 缺侧，`601 -> 602` low-confidence | 是，见 H01 |
| S0015 | 14 高操作回路图.dwg | `224/222/206` 缺侧 | 是，见 H01 |
| S0016 | 15 低操作回路图.dwg | `224/222/206` 缺侧 | 是，见 H01 |
| S0018 | 17 差动保护背板图.dwg | backplate table 跨页冲突 review | 是，见 H04 |
| S0019 | 18 高后备保护背板图.dwg | backplate table 冲突/重复/共享端点 review | 是，见 H04 |
| S0021 | 20 非电量保护背板图.dwg | backplate table 一对多/多对一 review | 是，见 H04 |
| S0022 | 21 元件接线图1.dwg | `DK` 端口多对一 review | 是，见 H03 |
| S0023 | 22 元件接线图2.dwg | `KLP/ZLP` component_mapping 一对多/多对一 review | 是，见 H03 |
| S0024 | 23 元件接线图3.dwg | `KLP` 逗号拆分端点、component/table 共享端点 review | 是，见 H03 |
| S0025 | 24 左侧端子图1.dwg | terminal header table 多端点/共享端点 review | 是，见 H05 |
| S0026 | 25 左侧端子图2.dwg | 2 条 local `10 -> ?` | 是，见 H06 |
| S0027 | 26 右侧端子图1.dwg | terminal header table 多端点/共享端点 review，`710 -> 10` low-confidence | 是，见 H05/H06 |
| S0028 | 27 右侧端子图2.dwg | 2 条 `? -> 10` | 是，见 H06 |

first 其他页当前没有需要你立即裁决的 issue 簇，但仍会在后续 T1 shadow topology 中检查线段/块覆盖。

### second 项目

| 页 | 文件 | 当前关系/问题状态 | 是否需要人工 |
|---|---|---|---|
| S0006 | 06 直流回路图.dwg | `101/103/105` ordinary missing-side | 是，见 H02 |
| S0010 | 10 测控1控制回路图1.dwg | `? -> 507` missing-side | 是，见 H06 |
| S0014 | 14 测控2开入回路图3.dwg | `? -> 501` missing-side | 是，见 H06 |
| S0022 | 22 左侧端子图2.dwg | `3-21WD2` terminal header row 一对多 review | 是，见 H05 |
| S0023 | 23 右侧端子图1.dwg | `1-21GD* / 1-21QD1` terminal header row 一对多/共享端点 review | 是，见 H05 |
| S0024 | 24 右侧端子图2.dwg | `1-21CD10` terminal header row 一对多 review | 是，见 H05 |

second 其他页当前不需要人工优先裁决。

## 裁决项

### H01 普通回路图：断线/分段导致的裸数字 missing-side

涉及页：

- first `04 交流回路图1.dwg`：`? -> 711/709/707/705/703/701`
- first `05 交流回路图2.dwg`：`721/720/719 -> ?`，`? -> 709/707/705/703/701`
- first `08/09/10` 信号回路：`14 -> ?`、`? -> 13`、`125/124 -> ?`
- first `11 非电量开入回路.dwg`：`? -> 601/310/309/308/307/210/209/208/207`
- first `14/15 操作回路图`：`? -> 224/222/206`

当前系统表现：这些行作为 `ordinary_pair` 进入审计，但只有单侧数字，触发 `R-PAIR-MISSING-SIDE`。

需要你裁决：

- 这些裸数字行是否应通过同一物理导线网络找到另一端端子，而不是当成真实缺侧？
- 如果是，是否允许跨越符号块、文本 bbox 或小断口进行 wire network bridge？
- 是否存在某些值应被解释为语义/功能编号，而不是端子端点？

建议裁决选项：

- `H01-A`：全部按线网连通补全，当前 missing-side 属于抽取缺口。
- `H01-B`：其中某些页/数字是语义或说明，不应补全为 ordinary pair。
- `H01-C`：需要局部截图后逐页判断。

已收到的用户裁决（2026-07-08，部分）：

- 总原则：目标不是生成记忆性标注或样本记忆算法，而是把普通回路识别引擎改成更智能、更通用的结构化识别。
- first `04 交流回路图1.dwg`：
  - 当前问题不是单纯缺线，而是普通回路引擎没有识别左侧连接端子，也没有识别上方元器件/装置框带来的结构前缀。
  - 业务目标应是输出 `1ID* -> 1n70x` 这一类结构化关系，而不是把 `701/703/705/...` 当裸 ordinary endpoint 审计。
- first `05 交流回路图2.dwg`：
  - 用户确认 `719/720/721` 这一簇不是裸数字缺侧，而是 `3-2ZKK` 结构没有被识别。
  - 代表性对应关系按用户裁决记录为：`3-2ZKK-6 -> 721`、`3-2ZKK-4 -> 720`、`3-2ZKK-2 -> 719`。
- first `11 非电量开入回路.dwg`：
  - 用户在原图中未发现当前 issue 簇里的 `601/310/309/308/307/210/209/208/207` 这些裸数字，说明这批 issue 不能再当成可信的业务端点。
  - 用户给出的代表性真实关系是：`5FD25 -> 5n105`、`5FD26 -> 5n132`、`5KLP1-2 -> 5n207`。
  - 因此这页当前更像普通回路识别引擎的抽取失败/错绑，而不是“真实存在一批 missing-side 裸数字”。
- 本条裁决的算法含义：
  - ordinary circuit 不能再按“端点附近找裸数字”处理，而要同时具备：
    - 线网连通能力；
    - inline component / device-frame 结构识别；
    - scoped prefix 组合能力（如 `1n701`、`5n207`）；
    - 左右连接端子识别能力。
- 仍待后续继续确认的 H01 子项：
  - first `08/09/10` 的 `13/14/124/125`
  - first `14/15` 的 `224/222/206`

预审与代码审计收敛结果（2026-07-08）：

- H01 三页的共性已经比较明确，不再只是“个别页误配”：
  - page top / zone top 存在 scoped prefix：`1n`、`1-2n / 3-2n`、`5n`；
  - 当前报错的裸三位数落在设备框或组件结构内部的固定 local-number 列，不是外部端点列；
  - 真正的外部端点列是更外侧的结构化 token：如 `1ID*`、`1-2ID* / 3-2ID* / 1-2UD* / 3-2UD*`、`5FD* / 5KLP*`。
- 因此 H01 的通用裁决不是“继续补 ordinary pair 规则”，而是：
  - 先把 token 解析成 `prefix / family_code / ordinal / local_number` 结构；
  - 再按页面布局识别 `prefix-column / local-number column / external-endpoint column`；
  - 最后由结构化 mapping 产出关系，ordinary 裸数字链只做兜底，不再做主链。
- 现有代码之所以掉回 naked-number issue，主要有三条系统性限制：
  - 候选阶段只把极窄 family 认成 `wire_logic_endpoint`，大部分 external endpoint 直接被当成 `not_numeric` 拒掉；
  - `wire_components.py` 里已有的 `component_prefixed / input_matrix / first_prefixed / inline_klp` family 过窄，只覆盖少数命名族；
  - `first_prefixed_external_endpoint_mapping` 还要求“local text 已先在 ordinary 单侧 pair 里出现”，导致结构化补救无法全量运行。
- 这意味着 H01 的第一刀更适合做：
  - 通用 `endpoint parser`
  - 通用 `prefix-column / row-endpoint / local-number` 框架
  - 去掉 `first_prefixed_eligible_local_text_ids` 这类把结构化识别绑死在 ordinary 错误链上的 gate

### H02 直流回路图：`101/103/105/132` 的端点语义

涉及页：

- first `06 直流回路图.dwg`：`101 -> ?` 三条；`132 -> 132` 四条 low-confidence。
- second `06 直流回路图.dwg`：`101 -> ?`、`103 -> ?`、`? -> 105`。

当前系统表现：裸数字被当普通端点，但缺少稳定对端或被选成同值自配对。

需要你裁决：

- `101/103/105/132` 在直流回路图中是独立跨页端子号，还是应结合 DK/ZD/3-21n 等上下文生成完整逻辑端？
- `132 -> 132` 这类同值配对是否是合法的同名连接，还是明显误配？
- 这类页是否应优先依赖 wire network 连通，而不是端点邻近窗口？

建议裁决选项：

- `H02-A`：裸数字必须结合上下文补成完整端，裸数字不应直接跨页审计。
- `H02-B`：裸数字本身就是端子号，但必须通过线网找真实对端。
- `H02-C`：同值 `132 -> 132` 是合法连接。
- `H02-D`：同值 `132 -> 132` 是误配，应进入抽取缺口。

### H03 元件接线图：component_mapping 一对多/多对一是否正常

涉及页：

- first `21 元件接线图1.dwg`：`1DK-2 -> 1QD5`、`5DK-2 -> 5FD25`、`1-2DK-2 -> 1-2QD12` 等多对一 review。
- first `22 元件接线图2.dwg`：`3-2KLP1-1 -> 3-2QD2`、`1-2KLP4-1 -> 1-2KLP3-1` 等链式/共享端点 review。
- first `23 元件接线图3.dwg`：`5KLP5-1 -> 5KLP3-1`、`5KLP5-1 -> 5KLP2-1` 等逗号拆分文本形成多条 component_mapping。

当前系统表现：component_mapping 已经抽出，但跨页规则把共享端点、一对多、多对一仍列为 review。

需要你裁决：

- 元件接线图中逗号分隔的多个外部端是否表示正常并联/分支，应该默认 pass 或 internal review？
- 链式 `KLPx-1 -> KLPy-1` 是否是正常串接关系？
- `DK-2` 这类端口多次指向外部端，是否代表正常公共端/汇接，还是应报用户问题？

建议裁决选项：

- `H03-A`：component_mapping 抽取关系本身正确；一对多/多对一是正常结构，默认不进入用户问题。
- `H03-B`：component_mapping 抽取关系正确，但仍应作为用户 review 保留。
- `H03-C`：部分 component_mapping 方向或端口绑定可能错，需要逐页截图标注。

### H04 背板表格型图：backplate table 跨页冲突/重复/共享端点

涉及页：

- first `17 差动保护背板图.dwg`
- first `18 高后备保护背板图.dwg`
- first `20 非电量保护背板图.dwg`

典型当前关系：

- `NDY306A-3 -> 1QD1`
- `NDY306A-16 -> 1KLP1-2`
- `NCZ343A-1 -> 1-4CD5`
- `NKR308A-1 -> 5FD11`

当前系统表现：背板虚拟表/插件端子表抽取出 `table_mapping`，但项目级规则发现同一插件端口跨页映射到多个 scoped terminals，触发 conflict/duplicate/many-to-one review。

需要你裁决：

- 同一背板插件端口在不同页映射到多个端子，是正常“插件端口在不同上下文被复用/引用”，还是应算真实冲突？
- 背板表格型图是否只应做“结构关系证据”，默认不参与硬一致性冲突？
- 这类共享端点是否应按 `plugin_id + page/scope` 分组，而不是按裸端口名跨全项目分组？

建议裁决选项：

- `H04-A`：背板表共享/复用是正常结构，默认进入 internal review，不作为用户问题。
- `H04-B`：同一插件端口多映射是潜在真实冲突，用户必须看到。
- `H04-C`：需要按插件实例/页面/列角色增加 scope 后再判断。

### H05 端子图：terminal header table 一行多端点/共享端点

涉及页：

- first `24 左侧端子图1.dwg`
- first `26 右侧端子图1.dwg`
- second `22 左侧端子图2.dwg`
- second `23 右侧端子图1.dwg`
- second `24 右侧端子图2.dwg`

典型当前关系：

- first：`3-4QD7 -> 3-2n212`、`5FD1 -> 5n103`、`1-2ID3 -> 1-2n705`、`1-2QD6 -> 1-2n122 / 1-2n209`
- second：`3-21WD2 -> 3-21n608`、`1-21GD3 -> 3-21n108`、`1-21QD1 -> 1-21n116`、`1-21CD10 -> 1-21n403`

当前系统表现：terminal header table 抽取为 `table_mapping`，但行内存在多个端点或多个逻辑行共享同一端点，触发 one-to-many / many-to-one review。

需要你裁决：

- 端子表同一行出现多个端点时，是否代表正常桥接/并接/同排多连接？
- terminal header table 的一对多/多对一是否应默认视为正常结构，只保留证据？
- 哪些列角色应参与跨页一致性，哪些只是语义/说明/表头？

建议裁决选项：

- `H05-A`：这些 table_mapping 基本正确，一对多/多对一是端子表正常结构，默认 internal。
- `H05-B`：一对多/多对一仍应用户复核，但不应算 hard error。
- `H05-C`：需要标注列角色后才能决定。

### H06 局部小数字 `10/13/14/501/507/710` 是否端点

涉及页：

- first `25 左侧端子图2.dwg`：`10 -> ?`
- first `26 右侧端子图1.dwg`：`710 -> 10`
- first `27 右侧端子图2.dwg`：`? -> 10`
- second `10 测控1控制回路图1.dwg`：`? -> 507`
- second `14 测控2开入回路图3.dwg`：`? -> 501`
- first `08/09/10`：`13/14` 相关缺侧

当前系统表现：这些小数字/三位数被作为 ordinary endpoint，但 evidence 不足或缺侧。

需要你裁决：

- `10/13/14` 是局部端口序号、端子排行号、表格行号，还是跨页端子号？
- `501/507/710` 是本页真实端子，还是功能/通道/说明编号？
- 这些值是否应通过前缀或所属区域组合成完整逻辑端？

建议裁决选项：

- `H06-A`：局部小数字不是跨页端点，必须结合元件/表格/端子排上下文。
- `H06-B`：这些值可以是端点，但必须通过线网或行列上下文找对端。
- `H06-C`：需要逐页截图标注。

### H07 高频未分类块族的符号库归类

T0 coverage 显示 `unclassified_blocks` 很高。当前模型尚未有符号库，很多 `INSERT` 只是以块名保留。

两套高频块族：

| 块名 | first 计数 | second 计数 | 需要裁决 |
|---|---:|---:|---|
| SYMB2_M_PWF165 | 237 | 334 | 是 |
| SYMB2_M_PWF231 | 136 | 282 | 是 |
| SYMB2_M_PWF191 | 45 | 188 | 是 |
| SYMB2_M_PWF194 | 85 | 44 | 是 |
| SYMB2_M_PWF234 | 85 | 16 | 是 |
| FJL-25-2A_Mirror | 54 | 27 | 已部分识别，但需确认 family |
| SYMB2_M_PWF224 | 46 | 24 | 是 |
| SYMB2_M_PWF243 | 18 | 64 | 是 |
| KK2P | 7 | 5 | 已部分识别，但需确认 family |

需要你裁决：

- 这些高频块分别是导线连接符号、端口/端子符号、元件符号、表格/图框符号，还是纯注释？
- 哪些块内部文字/端口应该参与 endpoint 推断？
- 哪些块只应作为 wire network bridge，不生成 endpoint？

建议裁决选项：

- `H07-A`：先对 Top 10 高频块做截图/图例标注。
- `H07-B`：先不处理块族，T1 只做线网 shadow。
- `H07-C`：你提供企业符号表或块名含义，我按表落 `symbol_library.yml`。

## 我建议你优先裁决的 5 个问题

1. `H01`：普通回路 missing-side 是否都优先按 wire network 连通补全。
2. `H02`：直流页 `101/103/105/132` 裸数字是否需要上下文前缀。
3. `H03`：元件接线图 component_mapping 的一对多/多对一是否默认 internal。
4. `H05`：端子表 table_mapping 的一行多端点是否默认 internal。
5. `H07`：是否让我先生成 Top 10 块族截图给你标 family。

## 子代理预审后的收口结论

四个只读子代理已经按 [doc/任务书.md](/F:/workspace/XJToolkit/doc/任务书.md) 和代表性预览图做过一轮预审。它们的结论比较收敛：

- `H01`：应拆成两类。first `04`、`05` 的 `701/703/705/707/709/711`、`14/15` 的 `224/222/206` 更像同一物理导线网络没接上，属于 T1 shadow wire network 应承接的连通性缺口。`05` 的 `719/720/721`、first `08/09/10` 的 `13/14`、first `11` 的 `601/310/309/...` 更像局部端口号或 scoped local number 被错当 ordinary endpoint，不应继续裸跑 ordinary 审计。
- `H02`：基本不是“缺线”，而是 scoped suffix 被错当裸端点。`101/103/105/132` 应优先按 `H02-A` 处理，即结合 `*n`、`DK/GD/QD` 等区域前缀补成完整逻辑端；`132 -> 132` 更接近假自配，倾向 `H02-D`，不是合法同名连接。
- `H03`：当前 `component_mapping` 大体是抽对了，review 主要来自规则层把正常分支/逗号拆分/共享端点也当成用户问题。默认建议按 `H03-A` 落：转 internal，不继续逐条向用户暴露。
- `H04`：背板表的 shared endpoint / duplicate 目前更像缺少 `page-device instance`、`subtable`、`header_text_id/x-span` 之类 scope 后的误判，默认不建议 user-visible。
- `H05`：terminal header table 的一对多/多对一大多也是 scope 问题。真正像同一 header-row 左右双列的正常接线，默认 internal；只有相邻子表串味、缺少 `table_instance/endpoint_column_role` 的，再留作 scope-enhancement 队列。
- `H06`：`10/13/14` 更像行号、局部端口号、触点号；`710/501/507` 更像必须依赖完整前缀或局部结构才成立的端点，不应裸进 ordinary pair。
- `H07`：高频未分类块族已经可以先按两大类理解：`PWF165/PWF231/PWF191/PWF194` 更像 wire bridge family，`PWF224/PWF234/PWF243/FJL-25-2A_Mirror/KK2P` 更像 endpoint-bearing symbol family。

## 缩窄后的人工确认集

如果我们按“最小必要人工输入”推进，你不需要逐条审所有 issue。当前更建议你只确认下面几类业务裁决：

1. `H02` 抽查 2 个代表点：
   - first `PW0107`：`132 -> 132` 是否应视为 scope 丢失后的假自配。
   - second `PW0108`：`101 -> ?` 是否应补成带前缀的完整端，而不是 ordinary missing-side。
2. `H01/H06` 的局部数字边界：
   - `124/125` 是否和 `101/103/105/132` 一样，属于 scoped local number。
   - `601 -> 602` 是否是局部结构里的过配，而不是稳定 ordinary pair。
   - `10/13/14` 是否一律视为局部行号/触点号，不进 ordinary pair。
3. `H03/H04/H05` 的显示分层：
   - 是否接受“默认 internal，除非补足 scope 后仍有互斥多映射才 user-visible”。
4. `H07` 的最小符号定类任务：
   - `PWF165 + PWF231`：是否同一 bridge family，是否纯 pass-through、不生成 endpoint。
   - `PWF191 + PWF194`：是否语义行带 bridge family，只 bridge 导线。
   - `PWF224`：是否 inline component family，端口 `1/2` 顺序。
   - `PWF243`：是否 contact/relay carrier family，`13/14` 是否局部触点号。
   - `PWF234`：是 endpoint-bearing 还是 bridge。
   - `FJL-25-2A_Mirror`：是否 strip two-port family，确认 `1/2` 拓扑。
   - `KK2P`：是否 multi-port component family，确认 pin map。

## 当前推荐的人审顺序

按性价比，建议你先回下面 4 组裁决；这已经足够让我继续推进 T1/T2/T3，而不必等所有细节都标完：

1. `H02`：`101/103/105/132` 这类裸数字一律要不要补前缀；`132 -> 132` 是否一律视为误配。
2. `H01/H06`：`10/13/14/124/125/501/507/710` 这类局部数字是否默认不进 ordinary pair。
3. `H03/H04/H05`：是否接受“默认 internal，补 scope 后再决定是否 user-visible”。
4. `H07`：是否让我下一步直接生成这 7 个符号族的截图任务给你逐个标 family。

## 影子线网落地后的进一步收口（2026-07-08）

Phase 98 T1 已完成 fresh real-sample shadow 验证，且主链 pair/issue 零漂移：

- first `.tmp/phase98_topology_first/...`
  - `pair_count=1705`
  - `issue_count=102`
  - `topology_shadow_report`: `37` 条 ordinary missing/low-confidence 候选，`37/37 recoverable`
- second `.tmp/phase98_topology_second/2_2`
  - `pair_count=1597`
  - `issue_count=12`
  - `topology_shadow_report`: `6` 条候选，`4/6 recoverable`

这进一步说明：

- H01/H02 的主问题已经不是“要不要继续加 ordinary 窄规则”，而是：
  - 哪些局部数字一律先视为 scoped local number / body-port / contact number，不准裸进 ordinary；
  - 哪些剩余缺侧在 topology 灰度切换时应直接由 network open endpoint + connected text assignment 接管。
- 对 first 集来说，ordinary 剩余簇几乎全部已经能被 T1 解释；Phase 99 只需要你拍板“哪些数字默认不裸审 ordinary”，不需要你逐条标网络。

## 进一步缩窄后的最小人审输入

如果按当前证据继续推进，真正还需要你拍板的只剩这 4 条：

1. `H02`：
   - `101/103/105/132` 是否统一按“必须补前缀/作用域”的 scoped local number 处理；
   - `132 -> 132` 是否统一按误配。
2. `H01/H06`：
   - `124/125`
   - `10/13/14`
   - `501/507/710`
   这三簇是否统一按“局部号，不裸进 ordinary pair”。
3. `H03/H04/H05`：
   - 是否接受“默认 internal，只有补足 scope 后仍互斥，才 user-visible”。
4. `H07`：
   - 是否让我下一步直接出 `PWF224/PWF234/PWF243/KK2P` 的截图标 family/pin-map。

## 附属明细

机器可读明细已导出：

- `.tmp/phase98_human_review/first_issue_detail.csv`
- `.tmp/phase98_human_review/second_issue_detail.csv`
- `.tmp/phase98_human_review/first_block_name_counts.csv`
- `.tmp/phase98_human_review/second_block_name_counts.csv`

这些文件包含每条 issue 的 pair_id、line_group_id、坐标、rule_id、root_cause 和块名频次，可用于后续生成局部截图或 DXF 定位。

## T1 影子报告真值化复审（2026-07-08）

Phase 98 初版 shadow report 已经证明“线网层有信号”，但它对 `recoverable` 的判定过宽，不能直接拿来选 Phase 99 灰度页。

原因：

- 旧版逻辑只要看到 network 上存在 `extra_relevant_texts + bridged_gaps`，就会把 issue 判成 `topology recoverable`。
- 这会把很多其实属于：
  - `scoped local number`
  - `body-port / inline component`
  - `semantic local`
  的结构问题误写成 topology 缺口。

本轮已将 shadow 分类收紧为：

- `topology_recoverable_external_endpoint_present`
- `scoped_local_number_cluster`
- `body_port_cluster`
- `semantic_local_cluster`
- `no_additional_topology_signal`

真实样本 rerun 结果：

- first `.tmp/phase99_shadow_tight_first_audit`
  - `37/37 recoverable -> 6/37 recoverable`
  - 仅 `14 高操作回路图.dwg` 与 `15 低操作回路图.dwg` 仍属于真正的 topology recoverable
- second `.tmp/phase99_shadow_tight_second_audit`
  - `4/6 recoverable -> 0/6 recoverable`
  - `06/10/14` 都不再视为 topology gray 候选

因此，人工裁决的使用方式也要同步收紧：

- first `05/06/08/09/10/11/25/26/27`：
  - 当前不再需要你把它们当“是否靠 topology 补全”的问题来审
  - 它们应回到结构识别裁决：`scoped prefix / local-number / body-port / contact number`
- second `06/10/14`：
  - 同样不再进入 topology 灰度候选
  - 应继续按 H02 / H06 的结构边界裁决推进
- first `14/15`：
  - 这是当前唯一保留下来的 topology T2 首批灰度页
  - 如果后续要做主链 switchover，优先从这 6 条 residual issue 开始

## 更新后的最小人审输入

按 tightened shadow 之后的结论，下一轮真正还需要你拍板的最小集合是：

1. `H02`
   - `101/103/105/132` 是否统一按“必须补前缀/作用域”的 scoped local number 处理
   - `132 -> 132` 是否统一视为误配
2. `H01/H06`
   - `124/125`
   - `10/13/14`
   - `501/507/710`
   这三簇是否统一按“局部号，不裸进 ordinary pair”
3. `H03/H04/H05`
   - 是否接受“默认 internal，只有补足 scope 后仍互斥，才 user-visible”
4. `H07`
   - 是否让我继续只为 `PWF224 / PWF234 / PWF243 / KK2P` 出符号截图与 pin-map 裁决任务

## 用户补充裁决回填（2026-07-08，H01/H02）

- `H02` 用户已明确：
  - `GND` 在直流页里按语义/地处理，可忽略，不进入 ordinary endpoint 审计。
  - first `06 直流回路图.dwg` 的 `132` 应结合作用域和结构端点解释为 `1QD6 -> 1n132`、`1-2QD13 -> 1-2n132`；同簇 `101/103/105/132` 都不应裸审。
  - `132 -> 132` 统一视为误配/假自配，进入抽取缺口，不是合法同名连接。
- 与 fresh `text_assignments/pairs` 对照后，H01/H02 当前最稳的通用结论是：
  - `04/05/06/11` 这类页的主问题不是缺线，而是 `scoped prefix + structured external endpoint + local-number/body-port` 结构未完全进主链。
  - 能直接被 `visible scoped prefix` 解释的局部号，应优先产出 `wire_component_mapping`；裸 ordinary 只保留兜底。
  - 剩余 `05` 的 `719/720/721`、first `11` 的 `601/310/.../207`、first/second `06` 的 residual `101 -> ? / ? -> 105` 已更像 body-port/token-role 缺口，不应回退成“继续补 ordinary 邻近规则”。
- 按最新裁决，最小剩余人审输入再缩窄为：
  1. `H01/H06`：`124/125`、`10/13/14`、`501/507/710` 是否统一按局部号，不裸进 ordinary。
  2. `H03/H04/H05`：是否接受默认 `internal`，仅在补足 scope 后仍互斥时才 user-visible。
  3. `H07`：是否继续只为 `PWF224/PWF234/PWF243/KK2P` 出截图与 pin-map 裁决任务。
- 工程约束：
  - 后续实现必须继续沿“token role -> slot composition -> relation inference”推进。
  - 不允许以样本白名单、值白名单或 suppress/filter 方式消掉这批 H01/H02 残留。

## 自动闭合回填（2026-07-08，body-port 通用切片 fresh rerun）

本轮已把上一轮人审里最典型的 H01 body-port 残留回灌到主线，并做了两套真实样本 fresh verify。下面只保留“你还需要看”的内容；已经自动闭合的条目不再需要你逐条裁决。

### 已自动闭合，无需继续人审

- first `05 交流回路图2.dwg`
  - 原 `3` 条 `R-PAIR-MISSING-SIDE` 已全部消失
  - 新结构化关系：
    - `1-2ZKK-2 -> 719`
    - `1-2ZKK-4 -> 720`
    - `1-2ZKK-6 -> 721`
    - `3-2ZKK-2 -> 719`
    - `3-2ZKK-4 -> 720`
    - `3-2ZKK-6 -> 721`
- first `11 非电量开入回路.dwg`
  - 原 `10` 条 residual 下降到 `2`
  - 新结构化关系已稳定覆盖：
    - `5KLP1-2 -> 5n207`
    - `5KLP2-2 -> 5n208`
    - `5KLP3-2 -> 5n209`
    - `5KLP4-2 -> 5n210`
    - `5KLP5-2 -> 5n307`
    - `5KLP6-2 -> 5n308`
    - `5KLP7-2 -> 5n309`
    - `5KLP8-2 -> 5n310`
    - `5KLP10-2 -> 5n112`
  - 同页 `5FD25 -> 5n105`、`5FD26 -> 5n132` 等 first-prefixed 关系仍保持
- second `05 交流回路图2.dwg`
  - 通用 `ZKK` family 在 second-set 也自然触发，说明这刀不是 first-set 记忆规则
  - 新关系示例：
    - `3-21ZKK-1 -> 3-21UD1`
    - `3-21ZKK-2 -> 715`
    - `3-21ZKK-3 -> 3-21UD2`
    - `3-21ZKK-4 -> 717`
    - `3-21ZKK-5 -> 3-21UD3`
    - `3-21ZKK-6 -> 719`

### 仍需你裁决的最小残余

1. first `06 直流回路图.dwg`
   - 仅剩三条：
     - `PW0120 101 -> ?`
     - `PW0141 101 -> ?`
     - `PW0158 101 -> ?`
   - 这三条与您已给出的 H02 裁决一致，看起来就是 `GND` 语义簇；下一刀更像“generic semantic-ground ignore/internal layering”，不是几何 body-port 问题。
2. first `11 非电量开入回路.dwg`
   - 仅剩两条：
     - `PW0284 ? -> 601`
     - `PW0285 601 -> 602`
   - 这两条没有被本轮 `KLP/ZKK` 通用结构吃掉，建议你下一轮只需要判断：
     - 它们是否属于另一个结构 family；
     - 或者应退出默认 ordinary 用户问题列表。

### 反作弊说明

- first fresh：
  - `pair_count 1705 -> 1717`
  - `wire_component_mapping 175 -> 187`
  - `ordinary_pair 728 -> 728` 不变
  - `issue_count 102 -> 91`
- second fresh：
  - `pair_count 1597 -> 1615`
  - `wire_component_mapping 380 -> 398`
  - `ordinary_pair 561 -> 561` 不变
  - `issue_count 12 -> 12`

因此，本轮下降是结构补全后消费旧裸 ordinary，不是隐藏、删对或降级。
