# DWG Audit Desktop

Tauri 2 + React + TypeScript 本地离线校验客户端。

## 能力

- 启动：最近项目、目录选择、拖放导入、开始校验
- 过程：阶段进度、实时问题、引擎事件日志
- 结果：问题清单、筛选、证据字段、预览定位、状态写回
- 后端接入：Tauri command → Python sidecar（analyze-session / list-recent-projects / load-result / render-preview / set-issue-status）

## 前端

```bash
npm install
npm run dev      # 浏览器 mock，不连 sidecar
npm run build
npm run check
```

顶栏会显示运行态：

- 引擎：本地 sidecar — 桌面壳已连接原生命令
- 引擎：浏览器 mock — 仅界面预览，数据为本地 mock

## 原生运行

```bash
npm run tauri:dev
npm run tauri:build
```

Sidecar 解析顺序：

1. `DWG_AUDIT_SIDECAR_EXE`
2. 安装包资源 `sidecar/dwg-audit-sidecar.exe`
3. 开发态源码回退 `python -m dwg_audit.cli`（debug 或 `DWG_AUDIT_ALLOW_SOURCE_FALLBACK=1`）

ODA File Converter 解析顺序（用户机可不预装）：

1. 配置 `ingest.odafc_path`（可选覆盖）
2. 环境变量 `ODAFC_PATH` / `ODA_FILE_CONVERTER`（桌面壳会注入打包路径）
3. 安装包资源 `oda/ODAFileConverter.exe`（`DWG_AUDIT_RESOURCE_DIR` / sidecar 同级）
4. 系统 `PATH`
5. Windows `Program Files\ODA\ODAFileConverter *`

## Windows 正式安装包（推荐一键脚本）

打包会把 **Python 引擎 sidecar** 与 **ODA File Converter** 一并打进 NSIS 安装包，用户电脑无需预装 Python / ODA。

```powershell
# 需要本机构建环境：Python 3.12+、PyInstaller、Node、Rust、VS Build Tools、本机已装 ODA 作为 stage 源
cd apps\desktop
.\scripts\build-windows-release.ps1 -Clean
```

分步执行：

```powershell
# 1) 把本机 ODA 安装树复制到 resources/oda（二进制不进 git）
.\scripts\stage-oda-resources.ps1 -Clean

# 2) PyInstaller 生成 resources/sidecar/dwg-audit-sidecar.exe
.\scripts\build-sidecar.ps1 -Clean

# 3) Tauri + NSIS
npm run tauri:build
```

产物通常在：

- `src-tauri/target/release/dwg_audit_desktop.exe`
- `src-tauri/target/release/bundle/nsis/*.exe`（安装包）

## 完整打包文档

更完整的架构、验证清单、CI 缓存与排障说明见仓库文档：

- [`doc/windows-packaging.md`](../../doc/windows-packaging.md)
- CI：`.github/workflows/windows-package.yml`

## 注意

- 正式校验必须走桌面客户端 + sidecar，避免前端空转。
- UI 只调度任务并展示 findings/结果，不在前端做 CAD 几何推理。
- 设计语言：务实、高密度、灰黑白米黄工业工作台。
- ODA 为第三方二进制，仅在本地 release 构建时 stage；仓库只保留 `resources/oda/README.md`。
- 若安装包未包含 ODA，用户仍可通过系统安装或设置 `ODAFC_PATH` 使用转换能力。
