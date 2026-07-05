# Progress Log

## Session: 2026-07-05

### Phase 1: Requirements & Discovery
- **Status:** complete
- **Started:** 2026-07-05 21:xx
- Actions taken:
  - 读取 `planning-with-files` 技能说明并执行 session catchup。
  - 重新核对当前 active goal、`doc/任务书.md` 与 `doc/findings.md`。
  - 核对工作区状态，确认桌面端结果页增强批次已全部 staged、尚未 commit。
  - 启动一个新的只读 explorer 子代理梳理 `M9` 剩余缺口，并复用现有子代理做 staged 改动风险审查。
- Files created/modified:
  - `task_plan.md` (created)
  - `progress.md` (created)

### Phase 2: Planning & Safe Integration
- **Status:** complete
- Actions taken:
  - 建立本地持久计划文件，记录本轮阶段、决策和已知环境问题。
  - 确认 `doc/findings.md` 保持为唯一权威发现文档。
- Files created/modified:
  - `task_plan.md` (updated)
  - `progress.md` (updated)

### Phase 3: Commit Pending Batch
- **Status:** complete
- Actions taken:
  - 复核已暂存的桌面端结果页增强批次范围。
  - 本地提交 `Enrich desktop result payloads and filters`，提交号 `c6fe180`。
- Files created/modified:
  - git history (`c6fe180`)

### Phase 4: M9 Native UX Implementation
- **Status:** in_progress
- Actions taken:
  - 给 `apps/desktop` 安装并接入 `@tauri-apps/plugin-dialog`。
  - 在 `desktopApi` 增加真实 `pickProjectDirectory()`。
  - 在 `App.tsx` 接入启动页原生文件夹选择、窗口级拖拽导入、拖拽状态提示与最小输入校验。
  - 在结果页修复两个交互风险：
    - 切换项目时重置旧筛选条件
    - 选中 issue 跟随 `filteredIssues`，并统一由 effect 刷新预览
  - 在 Rust 侧注册 `tauri-plugin-dialog`，并补 capability `dialog:allow-open`。
  - 同步更新 `apps/desktop/README.md`。
  - 在结果页新增 `Preview source` 切换，开始复用 `sheet_id / evidence_refs / sheet_ids` 切换相关页预览。
  - 在结果页把 `evidence_refs` 从 JSON 改成可点击列表，并新增 `Regenerate preview` 控件。
  - 给 `preview_src` 增加 cache-bust 查询参数，确保重复生成的 SVG 能被前端刷新到。
  - 把 `line_group_id` 穿到 `render-preview` 命令链，让 evidence ref 点击在带线组信息时能切换到对应高亮。
- Files created/modified:
  - `apps/desktop/package.json`
  - `apps/desktop/package-lock.json`
  - `apps/desktop/src/lib/desktopApi.ts`
  - `apps/desktop/src/App.tsx`
  - `apps/desktop/src/App.css`
  - `apps/desktop/src-tauri/Cargo.toml`
  - `apps/desktop/src-tauri/src/main.rs`
  - `apps/desktop/src-tauri/capabilities/default.json`
  - `apps/desktop/README.md`
  - `doc/findings.md`

### Phase 5: Verification & Next Push
- **Status:** in_progress
- Actions taken:
  - 两次运行 `npm run build`，确认前端类型检查与打包通过。
  - 第三次运行 `npm run build`，确认加入 `Preview source` 切换后仍可通过构建。
  - 第四次与第五次运行 `npm run build`，确认加入 `evidence refs` 点击入口、预览重生成与 cache-bust 后仍可通过构建。
  - 第六次运行 `npm run build`，确认 `line_group_id` 透传到预览链后仍可通过构建。
  - 运行 `python -m pytest -q tests/unit/test_sidecar.py tests/unit/test_cli.py`，17 个测试通过。
  - 收到两个子代理的只读审查结果，并把真实高优先级缺口与残余风险折回主线程实现或记录。
  - 本地提交 `Add native desktop import and preview switching`，提交号 `fb97b7d`。
  - 本地提交 `Highlight preview refs by line group`，提交号 `58442c9`。
  - 基于 `hero.png` 生成 `512x512` 透明底 `icon-source-square.png`，并用 `npx tauri icon ...` 重新生成 `src-tauri/icons/` 全套图标资源。
  - 通过 VS Build Tools 环境执行 `cargo check --manifest-path src-tauri\\Cargo.toml`，确认原生 Rust 工程编译通过。
  - 两次 `npm run tauri:build` 卡在 NSIS 资源下载阶段 `timeout: global`，确认阻塞已从应用代码收敛到 bundler 依赖下载。
  - 手动预热 `NSIS 3.11` 与 `nsis_tauri_utils.dll` 本机缓存后，再次执行 `npm run tauri:build` 成功，真实产出 `dwg_audit_desktop.exe` 与 NSIS 安装包。
  - 本地提交 `Close native Tauri build loop`，提交号 `ebd1fc9`。
- Files created/modified:
  - `doc/findings.md`
  - `task_plan.md`
  - `progress.md`
  - git history (`fb97b7d`)
  - git history (`58442c9`)

### Phase 6: Native Build Closure And DWG Follow-up
- **Status:** in_progress
- Actions taken:
  - 复用已有子代理并行启动两条非重叠任务：
    - `Euler`：负责 `src/dwg_audit/...` 候选/线组策略整改与测试
    - `Zeno`：负责第二套样本只读核验与验证页建议
  - 主线程完成 Tauri 原生构建链闭环，准备把后续精力切回 DWG findings / audit 质量整改。
  - 主线程调整页型默认策略：`屏端子图 / 元件接线图` 默认进入 `supplemental`，`背板接线图` 仍保持 `secondary`。
  - 更新 `project_scanner` 单元/集成测试，确认 supplemental 页会进入 downstream audit，而背板页仍需显式配置才会进入。
  - 对第二套样本执行新的真实链路验证：
    - `analyze-project` 输出到 `.tmp/phase6_supplemental_default_second/2_2`
    - `run-audit` 输出到对应 `audit/`
  - 验证结果显示：
    - `21-24` 端子页已进入主链并产生 `135/85/130/92` 个 pair
    - `19-20` 元件接线图虽然已是 supplemental，但仍为 `0 line_groups / 0 pairs`
  - 复核当前候选/线组代码，确认 `DIM/MARK` 单字符降权与 inline 数字断线重连并非空白实现，而是已有代码与单测，只是效果还没闭环到用户期望。
  - 针对 `二次原理图` 新增 `single_char_layer_filtered` 路径，把主回路页单字符 `DIM/MARK` 候选直接拒收，同时保留 `屏端子图` 的单字符候选能力。
  - 在抽取层为 `INSERT` 增加 `virtual_entities()` 展开，并通过 `extract.insert_virtual_entity_categories = ["元件接线图"]` 把它收口成页型专用能力，避免主回路页全局噪声放大。
  - 将 `inline_numeric_bridge_gap` 从 `12.0` 上调到 `13.0`，补齐略高于旧阈值的桥接单测。
  - 新增集成测试，固定两条行为：
    - `元件接线图` 页面会从 block 虚拟实体中抽到 line_group / pair
    - `二次原理图` 页面默认不会因为 block 虚拟实体而自动扩容主链
  - 对第二套样本再次实跑两版对照：
    - `phase6_primary_single_char_filter_second/2_2`
    - `phase6_component_insert_gap13_second_scoped/2_2`
  - 关键结果：
    - `primary` 页单字符一侧 pair 从 `56` 降到 `0`
    - `19 元件接线图1.dwg` 从 `0 line_groups / 0 pairs / 0 issues` 提升到 `39 / 39 / 12`
    - `20 元件接线图2.dwg` 仍为 `0 / 0 / 0`
    - `08/12` 的 issue 总量没有因 `gap 13.0` 出现显著改善，说明下一步要打互补链级别逻辑
- Files created/modified:
  - `apps/desktop/src-tauri/icons/`
  - `src/dwg_audit/audit/candidates.py`
  - `src/dwg_audit/extract/cad_extract.py`
  - `src/dwg_audit/utils/config.py`
  - `src/dwg_audit/ingest/project_scanner.py`
  - `tests/unit/test_project_scanner.py`
  - `tests/unit/test_terminal_candidates.py`
  - `tests/unit/test_line_groups.py`
  - `tests/integration/test_analyze_project.py`
  - `doc/findings.md`
  - `task_plan.md`
  - `progress.md`

### Phase 7: Component Orientation Follow-up
- **Status:** complete
- Actions taken:
  - 在 `src/dwg_audit/audit/line_groups.py` 增加方向感知分组：
    - `元件接线图` 支持 `line_group_orientation = auto`
    - 根据页内有效线段自动选择 `horizontal / vertical`
    - vertical 线组会以 `top -> bottom` 方式写入 `LineGroup`
  - 在 `src/dwg_audit/audit/candidates.py` 增加竖线端点候选：
    - vertical 线组使用 `top / bottom` side
    - side score 与 cross-axis 对齐改为纵向几何语义
  - 在 `src/dwg_audit/audit/pairs.py` 保持 `left_value / right_value` 兼容输出，同时将真实 side label 与 orientation 写入 evidence。
  - 在 `src/dwg_audit/audit/rules.py` 增加共享 text anchor 的互补半链聚合：
    - 同页 `? -> X` 与 `X -> ?`
    - 共享 `text_id`
    - 几何 gap 与 Y 偏差落在 inline bridge 护栏内
    - 聚合为一条“互补半链待复核” issue，而不改写 pair 本体
  - 新增/更新测试：
    - `tests/unit/test_line_groups.py`
    - `tests/unit/test_terminal_candidates.py`
    - `tests/unit/test_pairs_and_rules.py`
    - `tests/integration/test_analyze_project.py`
  - 对第二套样本执行新的真实实跑：
    - `analyze-project` 输出到 `.tmp/phase7_vertical_component_second/2_2`
    - `run-audit` 输出到对应 `audit/`
  - 关键结果：
    - `20 元件接线图2.dwg` 从 `0 / 0 / 0` 提升到 `55 line_groups / 55 pairs / 55 issues`
    - `20` 的 `line_groups.orientation` 全为 `vertical`
    - `08 测控1开入回路图1.dwg` issue 总量 `96 -> 49`，其中 `47` 条为“互补半链待复核”
    - `12 测控2开入回路图1.dwg` issue 总量 `89 -> 48`，其中 `41` 条为“互补半链待复核”
    - `primary` 页单字符一侧 pair 继续保持 `0`
  - 本地提交 `Add vertical component pairing and half-chain issue clustering`，提交号 `e4cfb3e`。
- Files created/modified:
  - `src/dwg_audit/audit/line_groups.py`
  - `src/dwg_audit/audit/candidates.py`
  - `src/dwg_audit/audit/pairs.py`
  - `src/dwg_audit/audit/rules.py`
  - `tests/unit/test_line_groups.py`
  - `tests/unit/test_terminal_candidates.py`
  - `tests/unit/test_pairs_and_rules.py`
  - `tests/integration/test_analyze_project.py`
  - `doc/findings.md`
  - `task_plan.md`
  - `progress.md`

### Phase 8: Vertical Candidate Dedupe Follow-up
- **Status:** in_progress
- Actions taken:
  - 结合两条只读子代理结论与主线程实查，确认 `20 元件接线图2.dwg` 的主噪声不是“候选过多竞争”，而是：
    - `54` 组 accepted `text_id` 被两根相邻竖线复用
    - 外加 `1` 根超长边框竖线产生的 `1 -> 1`
  - 在 `src/dwg_audit/audit/candidates.py` 增加 vertical component 页专用锚点去重：
    - 同页、同 side、同 `text_id`
    - 只保留距离端点最近的 accepted candidate
    - 其余改为 `shared_text_anchor_reused`
  - 在 `src/dwg_audit/audit/line_groups.py` 增加 `元件接线图 + vertical` 的超长线离群过滤：
    - 使用 vertical 候选长度中位数
    - 过滤 `> 3x median` 的极端长线
  - 新增/更新单测：
    - `tests/unit/test_terminal_candidates.py`
    - `tests/unit/test_line_groups.py`
  - 对第二套样本执行新的真实实跑：
    - `analyze-project` 输出到 `.tmp/phase8_vertical_dedupe_longline_second/2_2`
    - `run-audit` 输出到对应 `audit/`
  - 关键结果：
    - `20 元件接线图2.dwg` 从 `55 line_groups / 55 pairs / 55 issues` 收敛到 `54 / 54 / 27`
    - `shared_text_anchor_reused` 拒收 `54` 个复用候选
    - `1 -> 1` 长线离群 pair 被移除
    - 当前 `20` 剩余 `27` 条 `1 -> 2` 低置信 pair
    - `19` 维持 `39 / 39 / 12`
    - `08/12` 维持 `49 / 48` issue，不回退
- Files created/modified:
  - `src/dwg_audit/audit/candidates.py`
  - `src/dwg_audit/audit/line_groups.py`
  - `tests/unit/test_terminal_candidates.py`
  - `tests/unit/test_line_groups.py`
  - `doc/findings.md`
  - `task_plan.md`
  - `progress.md`

### Phase 8: Component Suffix Scoped Follow-up
- **Status:** complete
- Actions taken:
  - 在 `src/dwg_audit/utils/config.py` 为 `元件接线图` 增加受控 `numeric_suffix_patterns` 与 `derived_numeric_penalty`。
  - 在 `src/dwg_audit/audit/candidates.py` 增加 orientation-scoped profile：
    - `元件接线图 + horizontal` 不启用 suffix 派生
    - `元件接线图 + vertical` 若已命中派生值，则同侧单字符数值改为 `superseded_by_derived_numeric`
  - 为上面行为补齐单测与集成测试，覆盖：
    - suffix 数值提取
    - 派生值压过 `1/2`
    - horizontal component 页保持禁用
    - `20 元件接线图2.dwg` 风格页面集成
  - 重新执行第二套样本真实链路：
    - `analyze-project` 输出到 `.tmp/phase8_component_suffix_scoped_second_rerun/2_2`
    - `run-audit` 输出到对应 `audit/`
  - 并发启动两个子代理继续推进：
    - `Schrodinger`：只读调查 `20` 剩余 `3` 条 `1 -> 2`
    - `Wegener`：独立写范围评估 vertical 语义在报告/UI 层的显式透传
  - 关键结果：
    - `19 元件接线图1.dwg` 的 `12` 条非 discard pair 保持不变
    - `20 元件接线图2.dwg` 的 `27` 条 non-discard pair 中，`24` 条从泛化 `1 -> 2` 变成具体值
    - `20` 仅剩 `3` 条泛化 `1 -> 2`，对应 `G0706 / G0712 / G0718`
    - `08/12` 继续保持 `49 / 48` issue，不回退
  - 本地提交当前批次：`62c2dc3 Scope component suffix parsing to vertical pages`
- Files created/modified:
  - `src/dwg_audit/audit/candidates.py`
  - `src/dwg_audit/utils/config.py`
  - `tests/unit/test_terminal_candidates.py`
  - `tests/integration/test_analyze_project.py`
  - `doc/findings.md`
  - `task_plan.md`
  - `progress.md`

### Phase 9: Residual Virtual Pin And Semantics Follow-up
- **Status:** in_progress
- Actions taken:
  - 接入子代理 `Schrodinger` 的只读结论，确认 `20` 剩余 `3` 条 `1 -> 2` 来自 `FJL-25-2A_Mirror` 虚拟块内部固定引脚号。
  - 在 `src/dwg_audit/domain/models.py` 为 `TextItem` 增加 `source_block_name`。
  - 在 `src/dwg_audit/extract/cad_extract.py` 透传 `INSERT` 的父块名到 `ATTRIB/VIRTUAL` 文本。
  - 在 `src/dwg_audit/utils/config.py` 为 `元件接线图` 增加：
    - `virtual_single_char_reject_blocks = ["FJL-25-2A_Mirror"]`
    - `HD(?P<value>\\d{1,3})$` vertical-only suffix 派生
  - 在 `src/dwg_audit/audit/candidates.py` 增加 `block_internal_pin_number` 拒收路径，专门过滤 `FJL` 虚拟块内单字符 `1/2`。
  - 新增/更新测试：
    - `FJL` 虚拟引脚号拒收单测
    - `HD#` suffix 提取单测
    - `FJL-25-2A_Mirror` 集成测试
  - 并行接入子代理 `Wegener` 的展示层补丁：
    - report markdown 透传 orientation / side labels
    - Streamlit 详情和列表透传 orientation / side labels
    - desktop 结果页与 preview 透传 orientation / side labels，并在 preview 缺 evidence 时回退读取 `line_groups.orientation`
  - 对第二套样本再次实跑：
    - `.tmp/phase9_virtual_pin_filter_second/2_2`
    - `.tmp/phase9_virtual_pin_filter_hd_second/2_2`
  - 关键结果：
    - `20 元件接线图2.dwg` 从 `27` 条 non-discard 收敛到 `24`
    - 旧的 `3` 条 `FJL` 伪 `1 -> 2` 已消失
    - `HD6 -> 504`、`HD5 -> 502` 分别语义化为 `6 -> 504`、`5 -> 502`
    - `19` 维持 `12` 条 non-discard
    - `08/12` 维持 `49 / 48` issue
  - 本地提交当前批次：`d5f79f4 Filter virtual component pins and expose line semantics`
- Files created/modified:
  - `src/dwg_audit/domain/models.py`
  - `src/dwg_audit/extract/cad_extract.py`
  - `src/dwg_audit/audit/candidates.py`
  - `src/dwg_audit/utils/config.py`
  - `src/dwg_audit/report/artifacts.py`
  - `src/dwg_audit/ui/app.py`
  - `src/dwg_audit/desktop/preview.py`
  - `apps/desktop/src/App.tsx`
  - `apps/desktop/src/lib/mockData.ts`
  - `tests/unit/test_terminal_candidates.py`
  - `tests/integration/test_analyze_project.py`
  - `doc/findings.md`
  - `task_plan.md`
  - `progress.md`

### Phase 10: Page Findings Alignment
- **Status:** in_progress
- Actions taken:
  - 接入两个只读子代理审查：
    - `Pauli`：确认当前最大任务书缺口是“页级分类器 + 路由器 + 表格型图专用抽取链”仍未正式实现
    - `Darwin`：复核 `M9` 已完成项与剩余 sidecar / desktop 缺口
  - 在 `src/dwg_audit/report/artifacts.py` 补齐页级 findings 产物：
    - 新建 `findings/page_findings/`
    - 为每页输出 `<sheet_id>.json` 与 `<sheet_id>.md`
    - 在 `findings.json` 中新增 `page_findings_count` 与 `page_findings`
    - 每页包含 `page_type`、`page_type_confidence`、`layout_summary`、`structure_summary`、`recognition_strategy`、`number_matching_strategy`、`high_confidence_signals`、`open_questions`
  - 复用并发 worker `Mendel` 只改测试写集，补齐：
    - `tests/unit/test_report_artifacts.py`
    - `tests/integration/test_analyze_project.py`
  - 在第二套样本执行真实 `analyze-project`：
    - 输出到 `.tmp/phase10_page_findings_second/2_2`
    - 确认 `24` 页全部生成 `page_findings`，目录下有 `24` 个 `.json` 与 `24` 个 `.md`
- Files created/modified:
  - `src/dwg_audit/report/artifacts.py`
  - `tests/unit/test_report_artifacts.py`
  - `tests/integration/test_analyze_project.py`
  - `doc/findings.md`
  - `task_plan.md`
  - `progress.md`

### Phase 11: Internal Findings Runtime And Batch 1 Analyst Workflow
- **Status:** in_progress
- Actions taken:
  - 根据用户最新任务书修正重新对齐 5.1 / 5.1.1 / 6：
    - `findings` 改为内部运行态 SSoT
    - `page_findings` 改为内存 / SQLite / 按需落盘记录
    - 默认不再把页级文件当正式长期交付物
  - 在代码中把 `page_findings/*.md|json` 改为显式调试开关：
    - `runtime.persist_page_findings_files = false` 成为默认值
    - 默认仍保留项目级 `findings.md/json` 与 parquet，保证 CLI / regression 可继续使用
    - 只有显式开启时才写 `findings/page_findings/`
  - 保持并扩展回归覆盖：
    - 默认不写 `page_findings/` 目录
    - payload 仍包含 `page_findings_count` 与 `page_findings`
    - 显式开启调试持久化时，仍能写出每页 `md/json`
  - 启动 Batch 1 页级并发审图，并建立 [page_task_queue.md](/F:/workspace/XJToolkit/doc/page_task_queue.md)：
    - `S0008`
    - `S0009`
    - `S0012`
    - `S0013`
  - 已收到第一份 Sheet Analyst 交付：
    - [S0009.md](/F:/workspace/XJToolkit/doc/page_findings/batch1/S0009.md)
    - [S0009.json](/F:/workspace/XJToolkit/doc/page_findings/batch1/S0009.json)
    - 核心结论：这页不是纯表格页，而是 `grid-heavy wire diagram`
  - 收到补齐后的 `S0008` 页审交付，并更新 Batch 1 横向复核与脚本计划：
    - [S0008.md](/F:/workspace/XJToolkit/doc/page_findings/batch1/S0008.md)
    - [S0008.json](/F:/workspace/XJToolkit/doc/page_findings/batch1/S0008.json)
    - [type_review_wire_grid.md](/F:/workspace/XJToolkit/doc/page_findings/batch1/type_review_wire_grid.md)
    - [script_plan_wire_grid.md](/F:/workspace/XJToolkit/doc/page_findings/batch1/script_plan_wire_grid.md)
  - 把页级 findings 运行态语义继续收口到代码：
    - `report/artifacts.py` 默认不再落盘 `page_findings/`，但显式开启调试时仍支持导出
    - page findings payload 现在显式保留 `file_id`，并优先复用 `SheetRecord` 上已有的 `route_target / page_type_confidence`
    - sidecar / SQLite / desktop 类型层继续以 `page_findings` 作为内部运行态字段承载
  - 复用只读子代理 `Pascal` 审查未提交切片，确认 `line_groups/page_classifier/router` 当前不安全混提。
  - 仅按安全切片暂存并本地提交：
    - `e2532a2 Store page findings in desktop runtime state`
  - 提交后继续并发启动 Batch 2 页审子代理：
    - `S0019 / 元件接线图1`
    - `S0021 / 左侧端子图1`
  - 已收到 Batch 2 两个页审样本，并新增横向复核/脚本计划：
    - [S0019.md](/F:/workspace/XJToolkit/doc/page_findings/batch2/S0019.md)
    - [S0019.json](/F:/workspace/XJToolkit/doc/page_findings/batch2/S0019.json)
    - [S0021.md](/F:/workspace/XJToolkit/doc/page_findings/batch2/S0021.md)
    - [S0021.json](/F:/workspace/XJToolkit/doc/page_findings/batch2/S0021.json)
    - [type_review_component_terminal.md](/F:/workspace/XJToolkit/doc/page_findings/batch2/type_review_component_terminal.md)
    - [script_plan_component_terminal.md](/F:/workspace/XJToolkit/doc/page_findings/batch2/script_plan_component_terminal.md)
  - Batch 2 当前共识：
    - `S0019` 需要 `horizontal_component_block_pin`
    - `S0021` 需要 `terminal_strip_column_mode`
    - 两页都不该再被“统一大脚本 + 全局阈值”思路处理
  - 实现 `horizontal_component_block_pin` 的第一步：
    - `TerminalCandidate` 透传 `source_block_name`
    - `Pair.evidence` 透传两端 `selected_*_source_block_name`
    - horizontal component 页新增 `block_internal_pin_pair` / `self_pair_from_same_virtual_text` guard
    - `元件接线图` 不再落入 `grid` line-group 模式
  - 第二套真实样本复跑确认：
    - `S0019` 的 `line_groups.orientation` 从 `grid` 收回到 `horizontal`
    - `S0019` 的 39 条 pair 全部变为 discard：
      - `block_internal_pin_pair: 29`
      - `self_pair_from_same_virtual_text: 8`
      - `missing numeric candidates on both sides: 2`
    - `S0020` 保持 `vertical:54 / review:24 / discard:30`
  - 落地 `S0021` 的 `terminal_strip_column_mode` 第一刀，范围收窄在 `src/dwg_audit/audit/candidates.py`：
    - `屏端子图` 候选查询改为 `line-span query`
    - 新增 terminal 页专用打分，降低 x 方向惩罚、提高同 row 候选得分
    - 新增 `terminal_row_locked`、`terminal_strip_bypass_text`、`terminal_strip_column_filtered`
  - 新增/更新测试：
    - `tests/unit/test_terminal_candidates.py`
    - `tests/integration/test_analyze_project.py`
  - 第二套真实样本再次实跑：
    - `analyze-project` 输出到 `.tmp/phase13_terminal_strip_column_mode_second/2_2`
    - `run-audit` 输出到对应 `audit/`
  - 关键结果：
    - `S0021` 从 `discard:108 / review:27` 收敛到 `discard:18 / review:117`
    - 旧的 `ambiguous candidate ordering` 不再主导，标准端子行开始稳定产出 `21 -> 211`、`69 -> 318` 这类 review pair
    - `S0021` 当前 issue 分布变成 `R-PAIR-LOW-CONFIDENCE: 90`、`R-PAIR-MISSING-SIDE: 27`、`R-DUPLICATE-SAME-LINE: 9`
    - 第二套总体 issue `398 -> 597`，属于“把原先被 discard 吞掉的标准端子行显性化”为 review 的可解释副作用
  - 第一套回归实跑：
    - `analyze-project` 输出到 `.tmp/phase13_terminal_strip_column_mode_first/...`
    - `run-audit` 完成后总 issue 为 `446`，较 Phase 11 的 `461` 未回退
    - 残余端子页缺口已更清楚：`23 右侧端子图1.dwg` 仍是 `discard:130`，`24 右侧端子图2.dwg` 仍是 `review:55 / discard:37`
  - 落地 `右侧端子图` 的 mirrored terminal-strip gate：
    - `右侧端子图` 不再复用左侧页的 `start_x+23.5 / +31.0` 列偏移
    - 新增 `right_terminal` 布局模式，改为识别：
      - `start_x+24.5..28.5` 的派生端子列
      - `start_x+47.0..50.5` 的纯数字列
  - 新增/更新测试：
    - `tests/unit/test_terminal_candidates.py`
    - `tests/integration/test_analyze_project.py`
  - 第二套真实样本再次实跑：
    - `analyze-project` 输出到 `.tmp/phase14_right_terminal_mirror_second/2_2`
    - `run-audit` 输出到对应 `audit/`
  - 关键结果：
    - `S0023` 从 `discard:130` 收敛到 `review:114 / discard:16`
    - `S0024` 从“左右两侧常选到同一文本”收敛到 `review:54 / discard:38`
    - `S0023` 开始稳定产出 `132 -> 20`、`229 -> 45` 这类 mirrored pair
    - 第二套总体 issue `597 -> 654`，新增主要来自 `S0023/S0024` 被显性化后的 `R-PAIR-LOW-CONFIDENCE`
  - 第一套回归实跑：
    - `analyze-project` 输出到 `.tmp/phase14_right_terminal_mirror_first/...`
    - `run-audit` 完成后总 issue 为 `559`
    - `26 右侧端子图1.dwg` 变成 `review:110 / discard:52`
    - `27 右侧端子图2.dwg` 变成 `review:34 / discard:2`
    - 这说明 mirrored slice 已经把第一套右侧端子页从大量 discard 拉进主链，但也同步显性化了更多 low-confidence issue
- Files created/modified:
  - `src/dwg_audit/utils/config.py`
  - `src/dwg_audit/report/artifacts.py`
  - `src/dwg_audit/domain/models.py`
  - `src/dwg_audit/page_router.py`
  - `src/dwg_audit/ingest/project_scanner.py`
  - `tests/unit/test_report_artifacts.py`
  - `tests/integration/test_analyze_project.py`
  - `doc/page_task_queue.md`
  - `doc/page_findings/batch1/S0009.md`
  - `doc/page_findings/batch1/S0009.json`
  - `doc/findings.md`
  - `task_plan.md`
  - `progress.md`

### Phase 12: Terminal Short-Bridge Strip Cleanup
- **Status:** complete
- Actions taken:
  - 并发接入两个只读子代理，对 `S0021 / S0024 / S0027` 的 `310-385` 短桥接带做产物级复核。
  - 结论对齐为：这个区段不是普通双侧端子带，而是“延续列 / 局部序号列 / 单侧 continuation”的桥接小带状区。
  - 在 `src/dwg_audit/audit/candidates.py` 新增短桥接带候选层收口：
    - `terminal_short_bridge_role_filtered`
    - `terminal_short_bridge_single_column`
    - 按行内 numeric x 列聚类，把局部序号列从普通 pair 候选中剔出
    - 对单根 derived continuation 列按其视觉列序决定 left/right 单侧 continuation
  - 新增单测，覆盖：
    - `311 / 333.5 / 341` 三列桥接带的左右分侧
    - 单列 `359` bridge column 的单侧输出
    - 单根 derived continuation 列的左右侧判定
  - 重新执行 targeted pytest，并复跑两套真实样本：
    - `.tmp/phase15_terminal_short_bridge_second/2_2`
    - `.tmp/phase15_terminal_short_bridge_first/...`
  - 关键结果：
    - 第二套总 issue `654 -> 648`
    - 第一套总 issue `559 -> 518`
    - `S0021` 短桥接带从 `110->110 / 328->328` 收口为 `110->330 / 109->329 / ?->328..322`
    - `S0024` 短桥接带从 `10->10 .. 1->1` 收口为整列 `missing left candidate`
    - `S0027` 的大量 same-column 自配对转成单侧 continuation，但双延续列同值 `420->420 / 110->110` 仍在
- Files created/modified:
  - `src/dwg_audit/audit/candidates.py`
  - `tests/unit/test_terminal_candidates.py`
  - `tests/integration/test_analyze_project.py`
  - `doc/findings.md`
  - `task_plan.md`
  - `progress.md`

### Phase 16: Terminal Semantic-Row Guard
- **Status:** complete
- Actions taken:
  - 复用并发子代理 `Cicero` 做只读误杀复核，专门检查 `S0021 / S0024 / S0027` 上 `terminal_semantic_local_numeric` 是否误伤真实 ordinary pair。
  - 在 `src/dwg_audit/audit/candidates.py` 新增 `_TERMINAL_SEMANTIC_ROW_PATTERNS` 与 `_apply_terminal_semantic_row_local_numeric_filter(...)`。
  - 将该过滤挂在短桥接列带角色收口之后、候选 rank 赋值之前，只对 `屏端子图 + 普通端子带 + 单/双字符本地数字` 生效。
  - 在 `tests/unit/test_terminal_candidates.py` 补两条单测，固定：
    - `KLP` 语义行会把 `3 -> 108` 左侧小数字压成 `missing left candidate`
    - `AC230V / AK` 语义行会把 `602 -> 4` 右侧小数字压成 `missing right candidate`
  - 复跑 targeted pytest，并补跑两套真实样本 audit：
    - `.tmp/phase16_terminal_semantic_rows_second/2_2`
    - `.tmp/phase16_terminal_semantic_rows_first/...`
  - 关键结果：
    - 第二套总 issue `648 -> 697`
    - 第一套总 issue `518 -> 487`
    - 第二套构成从 `LOW-CONFIDENCE 267 -> 203`、`MISSING-SIDE 381 -> 494`
    - 第一套构成从 `LOW-CONFIDENCE 143 -> 84`、`MISSING-SIDE 374 -> 402`
    - 子代理复核结论偏正面：`421->44`、`105->10`、`214->2` 这类最像误杀的例子，仍更像语义行局部序号，而不像应保留的 ordinary terminal pair
- Files created/modified:
  - `src/dwg_audit/audit/candidates.py`
  - `tests/unit/test_terminal_candidates.py`
  - `doc/findings.md`
  - `task_plan.md`
  - `progress.md`

### Phase 17: Taskbook Audit And Component Route Closure
- **Status:** complete
- Actions taken:
  - 重新回到 [任务书.md](/F:/workspace/XJToolkit/doc/任务书.md) 做逐条完成度审计，只看当前代码、当前测试和当前 `.tmp` 真实样本产物。
  - 并发拉起两个只读子代理：
    - `Linnaeus`：核验页级分类器 / 路由器是否真的接管 `analyze-project`
    - `Hilbert`：核验 `TableExtractor` 是否已在真实样本中形成独立高置信信源
  - 主线程确认当前最短闭环切片是“元件接线图不再被误路由成 Wire/Table”，而不是继续扩展桌面端或继续堆全局候选阈值。
  - 在 `src/dwg_audit/page_classifier.py` 收紧元件页优先级：
    - `元件接线图` 现在优先保留 `ComponentDiagramExtractor`
    - 不再先被 `grid_heavy` 或 `table_like` 抢成 `WireDiagramExtractor` / `TableExtractor`
  - 在 `tests/unit/test_page_classifier.py` 新增两条单测，固定：
    - horizontal component 优先于 `grid_heavy`
    - component 页优先于 `table_like`
  - 复跑定向 pytest：
    - `tests/unit/test_page_classifier.py tests/unit/test_table_extractor.py tests/unit/test_line_groups.py tests/unit/test_pairs_and_rules.py`
    - `tests/integration/test_analyze_project.py -k "component or terminal or page_findings or supplemental"`
  - 对两套真实样本重新执行：
    - `.tmp/phase17_component_route_closure_second/2_2`
    - `.tmp/phase17_component_route_closure_first/...`
    - 并补跑两套 `run-audit`
  - 关键结果：
    - 第二套 `S0019/S0020` 已从 `WireDiagramExtractor` 回到 `ComponentDiagramExtractor`
    - 第一套 `S0022/S0023/S0024` 已从 `Wire/Table` 回到 `ComponentDiagramExtractor`
    - 第一套 `S0023` 不再是假 `TableExtractor`
    - 两套真实样本当前都没有稳定 `TableExtractor` 命中，`table_extraction_summary` 均为 `table_pages=0 / total_mappings=0`
    - 第二套总 issue 维持 `697`
    - 第一套总 issue `487 -> 517`，原因是 `S0023` 重新进入 component 审计链后新增 `30` 条 non-discard pair
- Files created/modified:
  - `src/dwg_audit/page_classifier.py`
  - `tests/unit/test_page_classifier.py`
  - `doc/findings.md`
  - `task_plan.md`
  - `progress.md`

## Test Results
| Test | Input | Expected | Actual | Status |
|------|-------|----------|--------|--------|
| Session catchup | `python ...session-catchup.py` | 输出 catchup 信息或安静结束 | 安静结束，无额外未同步提示 | ✓ |
| Git staged check | `git status --short` | 确认 staged 待提交批次 | 12 个已修改文件 + 1 个新增测试文件均为 staged | ✓ |
| Desktop build | `npm run build` | `apps/desktop` 类型检查与打包通过 | 通过 | ✓ |
| Desktop rebuild after filter/preview fix | `npm run build` | 启动页与结果页改动仍可通过构建 | 通过 | ✓ |
| Desktop rebuild after preview-source switch | `npm run build` | 新增多 sheet 预览切换后仍可通过构建 | 通过 | ✓ |
| Desktop rebuild after evidence-ref actions | `npm run build` | evidence refs 点击切换与重生成后仍可通过构建 | 通过 | ✓ |
| Desktop rebuild after preview cache-bust | `npm run build` | 重生成预览附加 cache-bust 后仍可通过构建 | 通过 | ✓ |
| Desktop rebuild after line-group highlight pass-through | `npm run build` | `line_group_id` 透传后仍可通过构建 | 通过 | ✓ |
| Preview CLI and sidecar regression | `python -m pytest -q tests/unit/test_sidecar.py tests/unit/test_cli.py` | 预览链与 CLI 回归通过 | `17 passed` | ✓ |
| Tauri icon regeneration | `npx tauri icon src-tauri/icons/icon-source-square.png --output src-tauri/icons` | 生成有效跨平台图标资源 | 成功生成 `icon.ico` / `icon.png` / appx / android / ios 资源 | ✓ |
| Native cargo check | `cargo check --manifest-path src-tauri\\Cargo.toml` | `src-tauri` 原生工程通过编译检查 | 通过 | ✓ |
| Tauri build first pass | `npm run tauri:build` | 完成桌面原生打包 | Rust release 编译通过，但 NSIS 下载阶段 `timeout: global` | ⚠ |
| Tauri build after NSIS cache warm | `npm run tauri:build` | 完成桌面原生打包 | 成功生成 `.exe` 与 NSIS 安装包 | ✓ |
| Project scanner + analyze integration | `python -m pytest -q tests/unit/test_project_scanner.py tests/integration/test_analyze_project.py` | 页型默认 supplemental 调整后测试仍通过 | `12 passed` | ✓ |
| Candidate + line-group regression | `python -m pytest -q tests/unit/test_terminal_candidates.py tests/unit/test_line_groups.py` | 当前 `DIM/MARK` 降权和 inline bridge 逻辑保持通过 | `8 passed` | ✓ |
| Second-set analyze rerun | `python -m dwg_audit.cli analyze-project --input ...变压器测控柜(2圈变，2台测控) --output .tmp/phase6_supplemental_default_second` | 第二套样本在新页型策略下完成 findings 实跑 | 通过，产物写入 `.tmp/phase6_supplemental_default_second/2_2` | ✓ |
| Second-set audit rerun | `python -m dwg_audit.cli run-audit --findings .tmp/phase6_supplemental_default_second/2_2/findings` | 第二套样本完成 audit 实跑 | 通过，生成 `544` 个 review issue | ✓ |
| Primary single-char + line-group unit regression | `python -m pytest -q tests/unit/test_terminal_candidates.py tests/unit/test_line_groups.py` | 主回路单字符过滤与 `gap 13.0` 单测通过 | `11 passed` | ✓ |
| Insert expansion + scanner integration | `python -m pytest -q tests/unit/test_project_scanner.py tests/integration/test_analyze_project.py` | `INSERT` 展开与页型 gating 集成通过 | `14 passed` | ✓ |
| Full pytest | `python -m pytest -q` | 仓库全量回归通过 | `92 passed` | ✓ |
| Second-set single-char filter rerun | `python -m dwg_audit.cli analyze-project --input ...第二套样本... --output .tmp/phase6_primary_single_char_filter_second` | 验证主回路单字符 pair 被压降 | 通过，`primary` 页单字符一侧 pair `56 -> 0` | ✓ |
| Second-set scoped insert+gap rerun | `python -m dwg_audit.cli analyze-project --input ...第二套样本... --output .tmp/phase6_component_insert_gap13_second_scoped` | 验证 `元件接线图` 专用 `INSERT` 展开与 `gap 13.0` 的 scoped 实跑 | 通过，`19` 提升到 `39 pair`，`20` 仍为 `0` | ✓ |
| Second-set scoped audit rerun | `python -m dwg_audit.cli run-audit --findings .tmp/phase6_component_insert_gap13_second_scoped/2_2/findings` | 生成 scoped 实跑后的 audit 结果 | 通过，`19` 新增 `12` 条 issue | ✓ |
| Phase 7 targeted pytest | `python -m pytest -q tests/unit/test_line_groups.py tests/unit/test_terminal_candidates.py tests/unit/test_pairs_and_rules.py tests/integration/test_analyze_project.py` | 纵向线组、top/bottom 候选与互补半链聚合通过 | `36 passed` | ✓ |
| Full pytest after Phase 7 | `python -m pytest -q` | 仓库全量回归通过 | `97 passed` | ✓ |
| Second-set vertical rerun | `python -m dwg_audit.cli analyze-project --input ...第二套样本... --output .tmp/phase7_vertical_component_second` | 验证 `20` 进入纵向主链 | 通过，`20` 提升到 `55 line_groups / 55 pairs` | ✓ |
| Second-set vertical audit rerun | `python -m dwg_audit.cli run-audit --findings .tmp/phase7_vertical_component_second/2_2/findings` | 验证互补半链聚合后的 issue 收敛 | 通过，`08: 96 -> 49`，`12: 89 -> 48` | ✓ |
| Phase 8 targeted pytest | `python -m pytest -q tests/unit/test_line_groups.py tests/unit/test_terminal_candidates.py tests/unit/test_pairs_and_rules.py tests/integration/test_analyze_project.py` | vertical 候选锚点去重与超长线过滤通过 | `38 passed` | ✓ |
| Full pytest after Phase 8 | `python -m pytest -q` | 仓库全量回归通过 | `99 passed` | ✓ |
| Second-set vertical dedupe rerun | `python -m dwg_audit.cli analyze-project --input ...第二套样本... --output .tmp/phase8_vertical_dedupe_longline_second` | 验证 `20` 的共享锚点去重与长线过滤 | 通过，`20` 收敛到 `54 line_groups / 54 pairs` | ✓ |
| Second-set vertical dedupe audit rerun | `python -m dwg_audit.cli run-audit --findings .tmp/phase8_vertical_dedupe_longline_second/2_2/findings` | 验证 `20` 的 low-confidence issue 进一步收敛 | 通过，`20: 55 -> 27` | ✓ |
| Full pytest after scoped suffix follow-up | `python -m pytest -q` | scoped suffix 派生与既有链路同时保持通过 | `103 passed` | ✓ |
| Second-set scoped suffix rerun | `python -m dwg_audit.cli analyze-project --input ...第二套样本... --output .tmp/phase8_component_suffix_scoped_second_rerun` | 验证 vertical-only suffix 派生的真实收益 | 通过，`20` 保持 `27` 条 non-discard，其中 `24` 条语义化 | ✓ |
| Second-set scoped suffix audit rerun | `python -m dwg_audit.cli run-audit --findings .tmp/phase8_component_suffix_scoped_second_rerun/2_2/findings` | 生成 scoped suffix 版本的审计产物 | 通过，`08/12` 维持 `49/48`，`20` 维持 `27` | ✓ |
| Phase 9 targeted pytest | `python -m pytest -q tests/unit/test_terminal_candidates.py tests/integration/test_analyze_project.py` | `FJL` 虚拟引脚过滤与 `HD#` 派生通过 | `24 passed` | ✓ |
| Full pytest after Phase 9 follow-up | `python -m pytest -q` | 算法层与展示层当前整合后仍通过 | `106 passed` | ✓ |
| Python compile check for semantics display | `python -m compileall src/dwg_audit/report/artifacts.py src/dwg_audit/ui/app.py src/dwg_audit/desktop/preview.py` | 展示层 Python 文件语法正确 | 通过 | ✓ |
| Desktop build after semantics display | `npm run build` | desktop 展示层 orientation 透传后仍可构建 | 通过 | ✓ |
| Second-set virtual pin filter rerun | `python -m dwg_audit.cli analyze-project --input ...第二套样本... --output .tmp/phase9_virtual_pin_filter_second` | 验证 `FJL` 虚拟引脚过滤可以移除残余 `1->2` | 通过，`20: 27 -> 24` | ✓ |
| Second-set virtual pin filter audit rerun | `python -m dwg_audit.cli run-audit --findings .tmp/phase9_virtual_pin_filter_second/2_2/findings` | 生成虚拟引脚过滤后的审计产物 | 通过，`20` 维持 `24` 条 issue | ✓ |
| Second-set virtual pin + HD rerun | `python -m dwg_audit.cli analyze-project --input ...第二套样本... --output .tmp/phase9_virtual_pin_filter_hd_second` | 验证 `HD#` 窄派生把两条 missing-left 语义化 | 通过，`20` 保持 `24` 条 issue，`HD6/HD5` 变成 `6/5` | ✓ |
| Second-set virtual pin + HD audit rerun | `python -m dwg_audit.cli run-audit --findings .tmp/phase9_virtual_pin_filter_hd_second/2_2/findings` | 生成 Phase 9 当前最佳审计产物 | 通过，`19/08/12` 不回退 | ✓ |
| Page findings targeted pytest | `python -m pytest -q tests/unit/test_report_artifacts.py tests/integration/test_analyze_project.py` | `page_findings` payload 与落盘目录通过回归 | `16 passed` | ✓ |
| Full pytest after page findings | `python -m pytest -q` | `page_findings` 与既有主链整合后全量回归通过 | `106 passed` | ✓ |
| Second-set page findings rerun | `python -m dwg_audit.cli analyze-project --input ...第二套样本... --output .tmp/phase10_page_findings_second` | 真实样本产出页级 findings | 通过，`24` 页全部生成 `page_findings` | ✓ |
| Internal page-findings runtime targeted pytest | `python -m pytest -q tests/unit/test_report_artifacts.py tests/unit/test_project_scanner.py tests/integration/test_analyze_project.py` | 默认不落盘 `page_findings/` 且显式调试开关仍可工作 | `25 passed` | ✓ |
| Full pytest after internal findings runtime change | `python -m pytest -q` | `page_findings` 默认内存态改造后全量回归通过 | `107 passed` | ✓ |
| Safe-slice targeted pytest after commit prep | `python -m pytest -q tests/unit/test_sidecar.py tests/unit/test_report_artifacts.py tests/integration/test_analyze_project.py -k "includes_supplemental_pages_in_downstream_audit or analyze_session_emits_events_and_stores_project_result or write_project_artifacts"` | 验证 runtime/state 安全切片在当前脏树下仍通过 | `7 passed, 15 deselected` | ✓ |
| Desktop build after runtime-state commit prep | `npm run build` | desktop 类型层携带 `page_findings` 后仍可构建 | 通过 | ✓ |
| Horizontal component targeted pytest | `python -m pytest -q tests/unit/test_pairs_and_rules.py tests/integration/test_analyze_project.py -k "horizontal_component_internal_pin_pairs or same_virtual_text_stub or same_block_single_digit_internal_pin_pair or same_block_multi_digit_component_pair or extracts_line_groups_from_insert_virtual_entities_on_component_page or extracts_vertical_component_pairs_on_component_page or prefers_component_suffix_values_on_vertical_component_page or rejects_virtual_fjl_internal_pin_numbers_on_component_page"` | 验证 `horizontal_component_block_pin` 护栏不破坏 component 链 | `8 passed, 24 deselected` | ✓ |
| Line-group / router support pytest | `python -m pytest -q tests/unit/test_page_classifier.py tests/unit/test_table_extractor.py tests/unit/test_line_groups.py` | 验证元件页不再误入 grid，且 grid/table 其余链路保持通过 | `17 passed` | ✓ |
| Second-set rerun for horizontal component guards | `python -m dwg_audit.cli analyze-project --input test\\变压器测控柜(2圈变，2台测控) --output .tmp\\phase12_horizontal_component_guard_second_v2` | 验证 `S0019` 真实页从 `grid` 回到 `horizontal`，并把块内伪 pair 收口为 discard | 通过，`S0019: 39 discard`，`S0020: vertical 54 / review 24` | ✓ |
| Second-set audit rerun after horizontal component guards | `python -m dwg_audit.cli run-audit --findings F:\\workspace\\XJToolkit\\.tmp\\phase12_horizontal_component_guard_second_v2\\2_2\\findings` | 验证 `S0019` 不再输出伪 issue 且 `S0020/S0021` 主链仍可审计 | 通过，`S0019 issue_count = 0` | ✓ |
| Phase 11 full pytest | `python -m pytest -q` | PageClassifier + grid-aware + TableExtractor + R-SHEET-PAGE-MISMATCH 整合后全量回归通过 | `122 passed` | ✓ |
| Second-set phase11 grid-aware analyze | `python -m dwg_audit.cli analyze-project --input ...第二套样本... --output .tmp/phase11_grid_aware_second_v2` | 验证 grid-aware 子模式真实生效 | 通过，S0008/S0009/S0012/S0013 全部判为 grid_heavy_wire_diagram，658 个 line_group 走 grid 链 | ✓ |
| Second-set phase11 grid-aware audit | `python -m dwg_audit.cli run-audit --findings .tmp/phase11_grid_aware_second_v2/2_2/findings` | 验证 grid-aware 后的 audit 产物 | 通过，406→400 issues，R-PAIR-LOW-CONFIDENCE 37→27 | ✓ |
| First-set phase11 grid-aware analyze+audit | `python -m dwg_audit.cli analyze-project + run-audit` | 验证第一套样本不回退 | 通过，461 issues，无 R-SHEET-PAGE-MISMATCH 触发（页码一致） | ✓ |
| Phase 13 targeted terminal pytest | `python -m pytest -q tests/unit/test_terminal_candidates.py tests/integration/test_analyze_project.py -k "terminal"` | 验证 terminal-strip 首刀与回归链路 | `19 passed, 9 deselected` | ✓ |
| Phase 13 support pytest | `python -m pytest -q tests/unit/test_pairs_and_rules.py tests/unit/test_line_groups.py tests/unit/test_page_classifier.py tests/unit/test_table_extractor.py` | 验证 component / grid / table 支撑链未被误伤 | `40 passed` | ✓ |
| Phase 13 analyze-project integration subset | `python -m pytest -q tests/integration/test_analyze_project.py -k "component or terminal or supplemental or page_findings"` | 验证 analyze-project 关键页型子集仍通过 | `9 passed, 2 deselected` | ✓ |
| Second-set phase13 terminal-strip analyze | `python -m dwg_audit.cli analyze-project --input ...第二套样本... --output .tmp/phase13_terminal_strip_column_mode_second` | 验证 `S0021` 的 terminal-strip 候选层首刀 | 通过，`S0021: discard 108 -> 18, review 27 -> 117` | ✓ |
| Second-set phase13 terminal-strip audit | `python -m dwg_audit.cli run-audit --findings .tmp/phase13_terminal_strip_column_mode_second/2_2/findings` | 验证 `S0021` 新 review pair 是否进入审计主链 | 通过，`S0021 issues = 126`，其中 `R-PAIR-LOW-CONFIDENCE = 90` | ✓ |
| First-set phase13 terminal-strip analyze+audit | `python -m dwg_audit.cli analyze-project + run-audit` | 验证 terminal-strip 首刀不会让第一套样本回退 | 通过，第一套总 issue `446`，优于 Phase 11 的 `461` | ✓ |
| Phase 14 mirrored terminal unit pytest | `python -m pytest -q tests/unit/test_terminal_candidates.py -k "terminal_strip or mirrored_right_terminal"` | 验证 mirrored right-terminal 列带选择 | `3 passed, 15 deselected` | ✓ |
| Phase 14 mirrored terminal integration pytest | `python -m pytest -q tests/integration/test_analyze_project.py -k "row_locks_terminal_strip_candidates or mirrored_right_terminal_strip_candidates or terminal_page_numeric_suffix_override"` | 验证 mirrored 右侧端子图 analyze-project 闭环 | `3 passed, 9 deselected` | ✓ |
| Phase 14 support pytest | `python -m pytest -q tests/unit/test_pairs_and_rules.py tests/unit/test_line_groups.py tests/unit/test_page_classifier.py tests/unit/test_table_extractor.py` | 验证 mirrored slice 不误伤 component / grid / table 支撑链 | `40 passed` | ✓ |
| Second-set phase14 mirrored analyze | `python -m dwg_audit.cli analyze-project --input ...第二套样本... --output .tmp/phase14_right_terminal_mirror_second` | 验证 `S0023/S0024` mirrored terminal gate | 通过，`S0023: discard 130 -> 16` | ✓ |
| Second-set phase14 mirrored audit | `python -m dwg_audit.cli run-audit --findings .tmp/phase14_right_terminal_mirror_second/2_2/findings` | 验证右侧端子页进入审计主链后的真实结果 | 通过，第二套总 issue `654`，`S0023 issues = 114` | ✓ |
| First-set phase14 mirrored analyze+audit | `python -m dwg_audit.cli analyze-project + run-audit` | 验证 mirrored slice 在第一套样本的真实行为 | 通过，第一套总 issue `559`，`26/27` 右侧端子页大幅显性化 | ✓ |
| Phase 15 short-bridge terminal unit pytest | `python -m pytest -q tests/unit/test_terminal_candidates.py -k "short_bridge or mirrored_right_terminal or row_locks_terminal_strip"` | 验证短桥接列带的列角色收口 | `4 passed, 17 deselected` | ✓ |
| Phase 15 terminal integration subset | `python -m pytest -q tests/integration/test_analyze_project.py -k "mirrored_right_terminal_strip_candidates or row_locks_terminal_strip_candidates"` | 验证 mirrored / row-lock 关键 analyze 链未被短桥接切片误伤 | `2 passed, 10 deselected` | ✓ |
| Phase 15 support pytest | `python -m pytest -q tests/unit/test_pairs_and_rules.py tests/unit/test_line_groups.py tests/unit/test_page_classifier.py tests/unit/test_table_extractor.py` | 验证短桥接候选切片不误伤 pairs / grid / table 支撑链 | `40 passed` | ✓ |
| Second-set phase15 short-bridge analyze | `python -m dwg_audit.cli analyze-project --input test\\变压器测控柜(2圈变，2台测控) --output .tmp\\phase15_terminal_short_bridge_second` | 验证第二套短桥接带从 `X->X` 收口为 continuation / bridge pair | 通过，`S0021` 改为 `110->330 / 109->329 / ?->328..322`，`S0024` 改为整列 `missing left candidate` | ✓ |
| Second-set phase15 short-bridge audit | `python -m dwg_audit.cli run-audit --findings .tmp\\phase15_terminal_short_bridge_second\\2_2\\findings` | 验证第二套短桥接切片对总体审计的真实影响 | 通过，第二套总 issue `654 -> 648` | ✓ |
| First-set phase15 short-bridge analyze | `python -m dwg_audit.cli analyze-project --input test\\110kV变压器保护柜 --output .tmp\\phase15_terminal_short_bridge_first` | 验证第一套右侧端子短桥接带同步收口 | 通过，`S0027` 大量 `628/427/216 -> same-value self-pair` 转为单侧 continuation | ✓ |
| First-set phase15 short-bridge audit | `python -m dwg_audit.cli run-audit --findings .tmp\\phase15_terminal_short_bridge_first\\WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA\\findings` | 验证第一套短桥接切片对总体审计的真实影响 | 通过，第一套总 issue `559 -> 518` | ✓ |
| Phase 16 semantic-row candidate unit pytest | `python -m pytest -q tests/unit/test_terminal_candidates.py -k "semantic or short_bridge or mirrored_right_terminal or row_locks_terminal_strip"` | 验证语义行小数字抑制与既有端子页护栏同时保持通过 | `6 passed, 17 deselected` | ✓ |
| Phase 16 terminal integration subset | `python -m pytest -q tests/integration/test_analyze_project.py -k "mirrored_right_terminal_strip_candidates or row_locks_terminal_strip_candidates"` | 验证 mirrored / row-lock analyze 链未被语义行护栏误伤 | `2 passed, 10 deselected` | ✓ |
| Phase 16 support pytest | `python -m pytest -q tests/unit/test_pairs_and_rules.py tests/unit/test_line_groups.py tests/unit/test_page_classifier.py tests/unit/test_table_extractor.py` | 验证语义行候选切片不误伤 pairs / grid / table 支撑链 | `40 passed` | ✓ |
| Second-set phase16 semantic-row audit | `python -m dwg_audit.cli run-audit --findings .tmp\\phase16_terminal_semantic_rows_second\\2_2\\findings` | 验证第二套语义行护栏对真实审计的影响 | 通过，第二套总 issue `648 -> 697`，`LOW-CONFIDENCE 267 -> 203` | ✓ |
| First-set phase16 semantic-row audit | `python -m dwg_audit.cli run-audit --findings .tmp\\phase16_terminal_semantic_rows_first\\WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA\\findings` | 验证第一套语义行护栏对真实审计的影响 | 通过，第一套总 issue `518 -> 487`，`LOW-CONFIDENCE 143 -> 84` | ✓ |
| Phase 17 classifier + route support pytest | `python -m pytest -q tests/unit/test_page_classifier.py tests/unit/test_table_extractor.py tests/unit/test_line_groups.py tests/unit/test_pairs_and_rules.py` | 验证 component 优先级收口不误伤 table / grid / pair / rule 支撑链 | `42 passed` | ✓ |
| Phase 17 analyze-project integration subset | `python -m pytest -q tests/integration/test_analyze_project.py -k "component or terminal or page_findings or supplemental"` | 验证 component / terminal / page_findings 关键集成链仍通过 | `10 passed, 2 deselected` | ✓ |
| Second-set phase17 component route analyze | `python -m dwg_audit.cli analyze-project --input test\\变压器测控柜(2圈变，2台测控) --output .tmp\\phase17_component_route_closure_second` | 证明第二套元件页回到 `ComponentDiagramExtractor` | 通过，`S0019/S0020` 已回到 component 路由，且 `table_pages=0` | ✓ |
| Second-set phase17 component route audit | `python -m dwg_audit.cli run-audit --findings .tmp\\phase17_component_route_closure_second\\2_2\\findings` | 验证第二套 route 修正不打断下游审计 | 通过，总 issue 保持 `697` | ✓ |
| First-set phase17 component route analyze | `python -m dwg_audit.cli analyze-project --input test\\110kV变压器保护柜 --output .tmp\\phase17_component_route_closure_first` | 证明第一套元件页不再被误判成 `Wire/Table` | 通过，`S0022/S0023/S0024` 已回到 component 路由，`table_pages=0` | ✓ |
| First-set phase17 component route audit | `python -m dwg_audit.cli run-audit --findings .tmp\\phase17_component_route_closure_first\\WBH-812E-E1SA_WBH-813E-E1SH_WBH-813E-E1SH_WBH-814E-E1SA\\findings` | 验证第一套 route 修正后的真实审计结果 | 通过，总 issue `487 -> 517`，原因是 `S0023` 重新进入 component 审计链 | ✓ |

## Error Log
| Timestamp | Error | Attempt | Resolution |
|-----------|-------|---------|------------|
| 2026-07-05 21:xx | `rg.exe` 启动失败（拒绝访问） | 1 | 改用 PowerShell 文件枚举 |
| 2026-07-05 21:xx | `spawn_agent` + `fork_context=true` 角色冲突 | 1 | 改为无历史分叉 explorer |
| 2026-07-05 21:xx | 子代理并发名额已满 | 1 | 复用现有子代理 `Parfit` |
| 2026-07-05 18:xx | `tauri build` 下载 NSIS 资源时报 `timeout: global` | 1 | 先手动预热 NSIS 缓存，再重跑构建 |
| 2026-07-05 23:xx | `spawn_agent` 在 `fork_context=true` 下再次拒绝显式 `agent_type` | 1 | 改为 `fork_context=false` 的独立 worker，并限制写集到 `tests/` |

## 5-Question Reboot Check
| Question | Answer |
|----------|--------|
| Where am I? | Phase 11: Page Classification + Router + grid-aware + TableExtractor + R-SHEET-PAGE-MISMATCH 已落地 |
| Where am I going? | 继续校准置信度公式（6项加权）、完善 TableExtractor 任意列数支持、推进 sidecar/desktop 剩余硬缺口 |
| What's the goal? | 按任务书推进桌面端与审计主链，同时把 findings 运行态和页级并发审图工作流对齐到最新要求 |
| What have I learned? | grid-aware 行带聚类能让被 inline 数字切断的线重新合并；元件接线图的 grid_heavy 特征来自端子桩而非导线，需让 vertical_component 优先 |
| What have I done? | 新增 PageClassifier/TableExtractor 模块，让 Page Router 真正参与执行路由，grid-aware 子模式救开入回路页，补齐 R-SHEET-PAGE-MISMATCH 规则，122 测试全绿 |

---
*Update after completing each phase or encountering errors*
