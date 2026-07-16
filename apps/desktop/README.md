# DWG Audit Desktop

Tauri 2 + React + TypeScript 本地离线校验客户端。

## 能力

- 启动：最近项目、目录选择、拖放导入、开始校验
- 过程：阶段进度、实时问题、引擎事件日志
- 结果：问题清单、筛选、证据字段、预览定位、状态写回
- 后端接入：Tauri command → Python sidecar（`analyze-session` / `list-recent-projects` / `load-result` / `render-preview` / `set-issue-status`）

## 前端

```bash
npm install
npm run dev      # 浏览器 mock，不连 sidecar
npm run build
npm run check
```

顶栏会显示运行态：

- `引擎：本地 sidecar` — 桌面壳已连接原生命令
- `引擎：浏览器 mock` — 仅界面预览，数据为本地 mock

## 原生运行

```bash
npm run tauri:dev
npm run tauri:build
```

Sidecar 解析顺序：

1. `DWG_AUDIT_SIDECAR_EXE`
2. 安装包资源 `sidecar/dwg-audit-sidecar(.exe)`
3. 开发态源码回退 `python -m dwg_audit.cli`（debug 或 `DWG_AUDIT_ALLOW_SOURCE_FALLBACK=1`）

打包前构建 sidecar：

```powershell
.\scripts\build-sidecar.ps1 -Clean
npm run tauri:build
```

## 注意

- 正式校验必须走桌面客户端 + sidecar，避免前端空转。
- UI 只调度任务并展示 findings/结果，不在前端做 CAD 几何推理。
- 设计语言：务实、高密度、灰黑白米黄工业工作台。
