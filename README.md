# dwg-audit

`dwg-audit` 是一个本地离线 DWG 审计工具，目标是从多页配线图中抽取水平连接线两端数字、建立跨页配对，并输出可复核的 findings 与 issue 报告。

当前版本包含：

- 项目扫描、`manifest.json` 与 `findings.md`
- `DWG -> DXF` 转换（通过本地 ODA File Converter）
- DXF 文本、线段、块属性抽取
- 候选连接线、端点数字候选、pair 构建
- 项目级规则审计与 Markdown / HTML / Excel 报告
- 最小可用 Streamlit 本地查看界面
- Windows 桌面端（Tauri）可安装包，可捆绑 Python sidecar + ODA

快速开始：

```powershell
python -m pip install -e .
dwg-audit init-config
dwg-audit analyze-project --input ./test --output ./artifacts
dwg-audit serve-ui --artifacts ./artifacts
```

## Windows 桌面安装包

离线安装包构建说明见：

- [`doc/windows-packaging.md`](doc/windows-packaging.md)
- [`apps/desktop/README.md`](apps/desktop/README.md)

本地一键打包：

```powershell
cd apps/desktop
npm run package:windows
```

CI 工作流：`.github/workflows/windows-package.yml`（仅在打 `v*` 标签 / 发布 GitHub Release 时触发；也可手动 workflow_dispatch）。
