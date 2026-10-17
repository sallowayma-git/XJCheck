import { useEffect, useMemo, useState } from "react"

import {
  buildComparisonRows,
  buildIssueNarrative,
  getIssueLocations,
  groupLocationsBySheet,
  isCrossSheetIssue,
  type BBox,
  type LocationView,
  type SheetGroup,
} from "../lib/issueLocations"
import type { IssueSummary } from "../types"
import { LocationPreviewPane } from "./LocationPreviewPane"

/** 窄于此宽度时，跨图预览改为标签页切换。 */
const WIDE_INSPECTOR_MIN_WIDTH = 1100

export type InspectorTechnicalRow = { label: string; value: string; mono?: boolean }

export type IssueInspectorProps = {
  issue: IssueSummary
  /** 原始处理分桶（error / warning / review）。 */
  handlingClass: string
  projectId: string | null
  runId: string | null
  clientSessionId: string
  clientSessionEpoch: number | null
  statusDraft: string
  statusOptions: readonly string[]
  statusLabel: (value: string) => string
  onStatusDraftChange: (value: string) => void
  onSaveStatus: () => void
  isSavingStatus: boolean
  technicalRows: InspectorTechnicalRow[]
  scoreRows: InspectorTechnicalRow[]
  rawSections: Array<{ title: string; text: string }>
}

function useIsWideWindow(minWidth: number): boolean {
  const [wide, setWide] = useState(() => typeof window === "undefined" || window.innerWidth > minWidth)
  useEffect(() => {
    const onResize = () => setWide(window.innerWidth > minWidth)
    window.addEventListener("resize", onResize)
    return () => window.removeEventListener("resize", onResize)
  }, [minWidth])
  return wide
}

function groupKeyOf(view: LocationView): string {
  return view.sheetId ?? `no-sheet:${view.key}`
}

/** 某张图上应取景的框：卡片选中的位置是“打开整张图”时取整图，否则取该图所有可渲染位置。 */
function focusFor(group: SheetGroup | null, activeView: LocationView | null): number[][] | null {
  if (!group?.sheetId) {
    return null
  }
  if (activeView && activeView.sheetId === group.sheetId && !activeView.renderable) {
    return null
  }
  const boxes = group.views
    .filter((view) => view.renderable && view.bbox)
    .map((view) => view.bbox as BBox)
  return boxes.length ? boxes : null
}

function highlightFor(group: SheetGroup | null, activeView: LocationView | null): BBox | null {
  if (!group?.sheetId || !activeView || activeView.sheetId !== group.sheetId) {
    return null
  }
  return activeView.renderable ? activeView.bbox : null
}

export function IssueInspector({
  issue,
  handlingClass,
  projectId,
  runId,
  clientSessionId,
  clientSessionEpoch,
  statusDraft,
  statusOptions,
  statusLabel,
  onStatusDraftChange,
  onSaveStatus,
  isSavingStatus,
  technicalRows,
  scoreRows,
  rawSections,
}: IssueInspectorProps) {
  const views = useMemo(() => getIssueLocations(issue), [issue])
  const groups = useMemo(() => groupLocationsBySheet(views), [views])
  const sheetGroups = useMemo(() => groups.filter((group) => group.sheetId), [groups])
  const narrative = useMemo(() => buildIssueNarrative(issue, views, handlingClass), [issue, views, handlingClass])
  const crossSheet = isCrossSheetIssue(groups)
  const wide = useIsWideWindow(WIDE_INSPECTOR_MIN_WIDTH)

  const defaultView = views.find((view) => view.renderable) ?? views[0] ?? null
  const [activeKey, setActiveKey] = useState<string | null>(defaultView?.key ?? null)
  const activeView = views.find((view) => view.key === activeKey) ?? null
  const [tabGroupKey, setTabGroupKey] = useState<string | null>(
    activeView?.sheetId ? groupKeyOf(activeView) : sheetGroups[0]?.groupKey ?? null,
  )

  const sideBySide = wide && sheetGroups.length === 2
  const paneGroups: Array<SheetGroup | null> = sideBySide
    ? sheetGroups
    : [sheetGroups.find((group) => group.groupKey === tabGroupKey) ?? sheetGroups[0] ?? groups[0] ?? null]
  const showTabs = !sideBySide && sheetGroups.length >= 2

  function selectView(view: LocationView): void {
    setActiveKey(view.key)
    if (view.sheetId) {
      setTabGroupKey(groupKeyOf(view))
    }
  }

  const comparisonRows = crossSheet && views.length >= 2 ? buildComparisonRows(views) : []

  return (
    <>
      <div className="panel inspector-header">
        <div className="section-heading">
          <h3>问题详情</h3>
          <span>{statusLabel(issue.status)}</span>
        </div>
        <div className="issue-headline">
          <span className={`level-tag tone-${narrative.tone}`} title={`处理分桶：${narrative.levelTitle}`}>
            {narrative.levelLabel}
          </span>
          <strong>{narrative.title}</strong>
        </div>
        <p className="issue-lead">{narrative.lead}</p>
        {narrative.comparison ? (
          <p className="issue-compare">
            <span>对比</span>
            {narrative.comparison}
          </p>
        ) : null}
      </div>

      <div className="panel inspector-preview">
        {showTabs ? (
          <div className="location-tabs" role="tablist" aria-label="切换图纸">
            {sheetGroups.map((group) => (
              <button
                key={group.groupKey}
                type="button"
                role="tab"
                aria-selected={paneGroups[0]?.groupKey === group.groupKey}
                className={paneGroups[0]?.groupKey === group.groupKey ? "active" : ""}
                onClick={() => setTabGroupKey(group.groupKey)}
              >
                {group.sheetLabel}
              </button>
            ))}
          </div>
        ) : null}
        <div className={`location-panes${sideBySide ? " is-pair" : ""}`}>
          {paneGroups.map((group, index) => (
            <LocationPreviewPane
              key={group?.groupKey ?? `empty-${index}`}
              caption={group?.sheetLabel ?? "未定位图纸"}
              subcaption={group ? `${group.views.length} 处位置` : ""}
              projectId={projectId}
              runId={runId}
              issueId={null}
              sheetId={group?.sheetId ?? null}
              focus={focusFor(group, activeView)}
              highlightBox={highlightFor(group, activeView)}
              clientSessionId={clientSessionId}
              clientSessionEpoch={clientSessionEpoch}
              emptyText="当前问题没有可定位的图纸区域，请阅读文字说明。"
            />
          ))}
        </div>
      </div>

      <div className="panel inspector-detail">
        <section className="detail-section">
          <h4>
            涉及位置 <span>{views.length ? `${views.length} 处` : ""}</span>
          </h4>
          {views.length ? (
            <div className="location-card-list">
              {views.map((view) => (
                <button
                  key={view.key}
                  type="button"
                  className={`location-card${view.key === activeKey ? " is-active" : ""}`}
                  aria-pressed={view.key === activeKey}
                  onClick={() => selectView(view)}
                >
                  <span className="location-card-title" title={view.title}>
                    {view.title}
                  </span>
                  <span className="location-card-meta">
                    <span className="location-role">{view.roleLabel}</span>
                    <span className="location-hint">{view.renderable ? "点击在预览区定位" : "打开整张图"}</span>
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <p className="muted">暂无可定位的图纸位置。</p>
          )}
        </section>

        {comparisonRows.length ? (
          <section className="detail-section">
            <h4>差异对比</h4>
            <div className="compare-table-wrap">
              <table className="compare-table">
                <thead>
                  <tr>
                    <th>图纸</th>
                    <th>端子</th>
                    <th>对端</th>
                  </tr>
                </thead>
                <tbody>
                  {comparisonRows.map((row) => (
                    <tr key={row.key}>
                      <td>{row.sheetLabel}</td>
                      <td>{row.terminal}</td>
                      <td className={row.peerDiffers ? "is-diff" : undefined}>{row.peer}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ) : null}

        <section className="detail-section">
          <h4>怎么改</h4>
          <p className="detail-action">{narrative.action}</p>
        </section>

        <section className="detail-section detail-status">
          <h4>处理结论</h4>
          <div className="detail-status-row">
            <label className="field compact-field">
              <span>结论</span>
              <select value={statusDraft} onChange={(event) => onStatusDraftChange(event.target.value)}>
                {statusOptions.map((status) => (
                  <option key={status} value={status}>
                    {statusLabel(status)}
                  </option>
                ))}
              </select>
            </label>
            <button type="button" className="ghost-button" disabled={isSavingStatus} onClick={onSaveStatus}>
              {isSavingStatus ? "保存中…" : "保存"}
            </button>
          </div>
        </section>

        <details className="detail-fold">
          <summary>详细说明</summary>
          <p>{issue.explanation || issue.summary || "暂无更多说明。"}</p>
        </details>

        <details className="detail-fold detail-tech">
          <summary>更多技术细节（排障用，一般无需查看）</summary>
          <dl className="tech-grid">
            {technicalRows.map((row) => (
              <div key={row.label}>
                <dt>{row.label}</dt>
                <dd className={row.mono ? "coords-mono" : undefined}>{row.value}</dd>
              </div>
            ))}
          </dl>
          {scoreRows.length ? (
            <>
              <h5>识别把握拆解</h5>
              <dl className="tech-grid">
                {scoreRows.map((row) => (
                  <div key={row.label}>
                    <dt>{row.label}</dt>
                    <dd>{row.value}</dd>
                  </div>
                ))}
              </dl>
            </>
          ) : null}
          {rawSections.map((section) => (
            <div key={section.title} className="tech-raw">
              <h5>{section.title}</h5>
              <pre>{section.text}</pre>
            </div>
          ))}
        </details>
      </div>
    </>
  )
}
