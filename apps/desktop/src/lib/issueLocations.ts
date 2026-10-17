import type { IssueLocation, IssueLocationRole, IssueSummary } from "../types"

/**
 * 问题的“涉及位置”与客户化文案（纯函数，不依赖界面状态）。
 * 优先使用后端返回的 issue.locations；旧结果没有该字段时，从 evidence_refs / 线端坐标派生。
 */

export type BBox = [number, number, number, number]

export const LOCATION_ROLE_LABELS: Record<IssueLocationRole | "reference", string> = {
  conflict_party: "冲突一方",
  other_party: "另一方",
  table_row: "端子表行",
  wire: "图内连线",
  unnumbered_symbol: "无编号图块",
  reference: "关联位置",
}

export type LocationView = {
  key: string
  role: IssueLocationRole | "reference"
  roleLabel: string
  sheetId: string | null
  sheetNo: string
  sheetTitle: string
  sheetLabel: string
  terminal: string
  peer: string
  pairId: string | null
  bbox: BBox | null
  renderable: boolean
  title: string
}

export type SheetGroup = {
  groupKey: string
  sheetId: string | null
  sheetNo: string
  sheetLabel: string
  views: LocationView[]
}

export type IssueLevelTone = "error" | "warning" | "review"

export type IssueNarrative = {
  /** 一句话标题 */
  title: string
  /** 一句话说明 */
  lead: string
  /** 跨页对比的一句话（仅跨图问题） */
  comparison: string | null
  /** “怎么改” */
  action: string
  /** 客户化级别标签（需修改 / 请确认 / 请核对） */
  levelLabel: string
  /** 原始处理分桶词，放 tooltip */
  levelTitle: string
  tone: IssueLevelTone
}

const LEVEL_LABEL_BY_HANDLING: Record<IssueLevelTone, string> = {
  error: "需修改",
  warning: "请确认",
  review: "请核对",
}

const LEVEL_RAW_BY_HANDLING: Record<IssueLevelTone, string> = {
  error: "确定性错误",
  warning: "可能有错误",
  review: "须人工校验",
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value)
}

function normalizeBBox(value: unknown): BBox | null {
  if (!Array.isArray(value) || value.length !== 4 || !value.every(isFiniteNumber)) {
    return null
  }
  const [x0, y0, x1, y1] = value as number[]
  return [Math.min(x0, x1), Math.min(y0, y1), Math.max(x0, x1), Math.max(y0, y1)]
}

function bboxFromPoints(points: Array<unknown>, padding: number): BBox | null {
  const valid = points.filter(
    (point): point is number[] => Array.isArray(point) && point.length >= 2 && isFiniteNumber(point[0]) && isFiniteNumber(point[1]),
  )
  if (!valid.length) {
    return null
  }
  const xs = valid.map((point) => point[0])
  const ys = valid.map((point) => point[1])
  return [Math.min(...xs) - padding, Math.min(...ys) - padding, Math.max(...xs) + padding, Math.max(...ys) + padding]
}

function stripDrawingExtension(filename: string): string {
  return filename.replace(/\.(dwg|dxf)$/i, "").trim()
}

function buildSheetLabel(sheetNo: string, sheetTitle: string, filename: string): string {
  const number = sheetNo.trim()
  const head = number ? `图 ${number}` : stripDrawingExtension(filename) || "未标注图号"
  return [head, sheetTitle.trim()].filter(Boolean).join(" ")
}

const UNNUMBERED_TERMINAL = "无编号"

function buildLocationTitle(view: Pick<LocationView, "role" | "sheetLabel" | "terminal" | "peer">): string {
  const numbered = view.terminal && view.terminal !== UNNUMBERED_TERMINAL ? view.terminal : ""
  if (view.role === "unnumbered_symbol" || view.terminal === UNNUMBERED_TERMINAL) {
    return `${view.sheetLabel} · 无编号图块${numbered ? ` · 端子 ${numbered}` : ""}`
  }
  if (view.role === "table_row") {
    return `${view.sheetLabel} · 端子表${view.terminal ? ` · 端子 ${view.terminal}` : ""}`
  }
  if (view.terminal && view.peer) {
    return `${view.sheetLabel} · 端子 ${view.terminal} → ${view.peer}`
  }
  if (view.terminal) {
    return `${view.sheetLabel} · 端子 ${view.terminal}`
  }
  return view.sheetLabel
}

function viewFromLocation(location: IssueLocation, index: number): LocationView {
  const bbox = normalizeBBox(location.bbox) ?? bboxFromPoints([location.point, location.wire?.start, location.wire?.end], 12)
  const role = location.role
  const sheetLabel = buildSheetLabel(location.sheet_no ?? "", location.sheet_title ?? "", location.filename ?? "")
  const base = {
    key: location.location_id || `loc-${index}`,
    role,
    roleLabel: LOCATION_ROLE_LABELS[role] ?? LOCATION_ROLE_LABELS.reference,
    sheetId: location.sheet_id ?? null,
    sheetNo: location.sheet_no ?? "",
    sheetTitle: location.sheet_title ?? "",
    sheetLabel,
    terminal: location.terminal ?? "",
    peer: location.peer ?? "",
    pairId: location.pair_id ?? null,
    bbox,
    renderable: Boolean(location.renderable && location.sheet_id && bbox),
  }
  return { ...base, title: buildLocationTitle(base) }
}

function readString(value: unknown): string {
  return typeof value === "string" ? value.trim() : ""
}

/** 旧结果兼容：没有 locations 时，从主页面与 evidence_refs 派生。 */
function deriveLocations(issue: IssueSummary): LocationView[] {
  const evidence = issue.evidence ?? {}
  const views: LocationView[] = []
  const primaryBBox = bboxFromPoints([evidence.line_start, evidence.line_end], 12)
  if (issue.sheet_id || issue.sheet_no || issue.filename) {
    views.push(
      viewFromLocation(
        {
          location_id: `${issue.issue_id}-primary`,
          role: "conflict_party",
          sheet_id: issue.sheet_id,
          file_id: issue.file_id,
          filename: issue.filename,
          sheet_no: issue.sheet_no,
          sheet_title: readString(evidence.sheet_title),
          sheet_order: null,
          terminal: issue.left_value,
          peer: issue.right_value,
          text_id: null,
          point: null,
          wire: null,
          bbox: primaryBBox,
          pair_id: issue.primary_pair_id,
          renderable: false,
        },
        0,
      ),
    )
    views[0].renderable = Boolean(issue.sheet_id && views[0].bbox)
  }
  issue.evidence_refs.forEach((ref, index) => {
    const record = ref as Record<string, unknown>
    const sheetId = readString(record.sheet_id) || null
    const bbox = bboxFromPoints([record.line_start, record.line_end], 12)
    views.push(
      viewFromLocation(
        {
          location_id: `${issue.issue_id}-ref-${index}`,
          role: "other_party",
          sheet_id: sheetId,
          file_id: readString(record.file_id) || null,
          filename: readString(record.filename),
          sheet_no: readString(record.sheet_no),
          sheet_title: readString(record.sheet_title),
          sheet_order: null,
          terminal: readString(record.left_value) || null,
          peer: readString(record.right_value) || null,
          text_id: null,
          point: null,
          wire: null,
          bbox,
          pair_id: readString(record.pair_id) || null,
          renderable: Boolean(sheetId && bbox),
        },
        index + 1,
      ),
    )
  })
  return views
}

/** 问题的涉及位置（卡片与预览共用）。 */
export function getIssueLocations(issue: IssueSummary): LocationView[] {
  if (issue.locations && issue.locations.length) {
    return issue.locations.map((location, index) => viewFromLocation(location, index))
  }
  return deriveLocations(issue)
}

/** 按图纸分组，保持首次出现的顺序；没有图号的位置归入无图组。 */
export function groupLocationsBySheet(views: LocationView[]): SheetGroup[] {
  const groups = new Map<string, SheetGroup>()
  for (const view of views) {
    const groupKey = view.sheetId ?? `no-sheet:${view.key}`
    const existing = groups.get(groupKey)
    if (existing) {
      existing.views.push(view)
      continue
    }
    groups.set(groupKey, {
      groupKey,
      sheetId: view.sheetId,
      sheetNo: view.sheetNo,
      sheetLabel: view.sheetLabel,
      views: [view],
    })
  }
  return Array.from(groups.values())
}

/** 跨页问题：至少两张不同的图。 */
export function isCrossSheetIssue(groups: SheetGroup[]): boolean {
  return groups.filter((group) => group.sheetId).length >= 2
}

/** 列表“位置”列的简短文字，不出现“本页”等内部说法。 */
export function summarizeLocations(views: LocationView[]): string {
  const first = views[0]
  if (!first) {
    return "未定位"
  }
  const head = first.sheetNo ? `图 ${first.sheetNo}` : first.sheetLabel
  return views.length > 1 ? `${head} 等 ${views.length} 处` : head
}

function readReasonCodes(issue: IssueSummary): string[] {
  const evidence = issue.evidence ?? {}
  const raw = Array.isArray(evidence.resolution_reason_codes) ? evidence.resolution_reason_codes : evidence.reason_codes
  return Array.isArray(raw) ? raw.map((item) => String(item)) : []
}

/** 后端 superworks_extractor._TRUE_CONFLICTS 中的实际原因码（精确匹配）。 */
const OVERLAP_REASON_CODES = ["competing_physical_port_instances", "competing_physical_port_identities"]
const STRIP_REASON_CODES = ["invalid_strip_header_reference", "invalid_strip_connection_reference"]
const NONRECIPROCAL_REASON_CODES = ["nonreciprocal_label", "nonreciprocal_pin"]
/** rules.py / component_diagrams.py：缺端的原因为端口无标注（英式拼写 unlabelled）。 */
const UNLABELLED_PORT_REASON = "unlabelled_port"

function describeSheet(view: LocationView | undefined): string {
  if (!view) {
    return "【未标注图纸】"
  }
  const number = view.sheetNo ? `图 ${view.sheetNo}` : "图纸"
  return `【${[number, view.sheetTitle].filter(Boolean).join(" ")}】`
}

function firstTerminal(views: LocationView[], fallback: string): string {
  return views.find((view) => view.terminal)?.terminal || fallback
}

function distinctSheetViews(groups: SheetGroup[]): LocationView[] {
  return groups.map((group) => group.views[0]).filter((view): view is LocationView => Boolean(view))
}

/** 跨图对比的一句话：“图 12 接到 622，图 16 接到 623”，或同端子多路接入时的说明。 */
export function buildComparisonSentence(views: LocationView[]): string | null {
  const groups = groupLocationsBySheet(views)
  if (!isCrossSheetIssue(groups)) {
    return null
  }
  const picked = distinctSheetViews(groups.filter((group) => group.sheetId))
  const peers = new Set(picked.map((view) => view.peer).filter(Boolean))
  if (peers.size > 1) {
    return picked
      .map((view) => `${view.sheetNo ? `图 ${view.sheetNo}` : view.sheetLabel} 接到 ${view.peer || "未识别"}`)
      .join("，")
  }
  return picked
    .map((view) => `${view.sheetNo ? `图 ${view.sheetNo}` : view.sheetLabel} 的 ${view.terminal || "未识别"}`)
    .join(" 与 ")
    .concat(peers.size === 1 ? ` 都接到了 ${Array.from(peers)[0]}` : "")
}

/** 差异表的一行。对端不同于多数位置时 differs 为 true（并列时全部标记）。 */
export type ComparisonRow = {
  key: string
  sheetLabel: string
  terminal: string
  peer: string
  roleLabel: string
  peerDiffers: boolean
}

export function buildComparisonRows(views: LocationView[]): ComparisonRow[] {
  const counts = new Map<string, number>()
  for (const view of views) {
    counts.set(view.peer, (counts.get(view.peer) ?? 0) + 1)
  }
  const maxCount = Math.max(0, ...counts.values())
  const modes = Array.from(counts.entries()).filter(([, count]) => count === maxCount).map(([peer]) => peer)
  const hasUniqueMode = modes.length === 1 && counts.size > 1
  const allDiffer = counts.size > 1 && modes.length > 1
  return views.map((view) => ({
    key: view.key,
    sheetLabel: view.sheetNo ? `图 ${view.sheetNo}${view.sheetTitle ? ` ${view.sheetTitle}` : ""}` : view.sheetLabel,
    terminal: view.terminal || "—",
    peer: view.peer || "—",
    roleLabel: view.roleLabel,
    peerDiffers: counts.size > 1 && (allDiffer || (hasUniqueMode && view.peer !== modes[0])),
  }))
}

function levelFor(tone: IssueLevelTone): { levelLabel: string; levelTitle: string } {
  return { levelLabel: LEVEL_LABEL_BY_HANDLING[tone], levelTitle: LEVEL_RAW_BY_HANDLING[tone] }
}

function toneFromHandling(handlingClass: string | null | undefined): IssueLevelTone {
  if (handlingClass === "error" || handlingClass === "warning" || handlingClass === "review") {
    return handlingClass
  }
  return "review"
}

/**
 * 按规则模板生成客户化文案。规则未在下表中时回退到后端的标题与说明。
 * handlingClass 为原始处理分桶（error / warning / review），仅用于没有专门模板的规则。
 */
export function buildIssueNarrative(
  issue: IssueSummary,
  views: LocationView[],
  handlingClass: string | null | undefined,
): IssueNarrative {
  const groups = groupLocationsBySheet(views)
  const crossSheet = isCrossSheetIssue(groups)
  const comparison = buildComparisonSentence(views)
  const reasons = readReasonCodes(issue)
  const fallbackTone = toneFromHandling(handlingClass)
  const fallbackLead = issue.summary || issue.explanation || issue.title
  const fallbackAction = issue.recommended_action || "按图纸核对该处接线。"
  const left = issue.left_value?.trim() || ""
  const right = issue.right_value?.trim() || ""
  const first = views[0]

  const build = (
    tone: IssueLevelTone,
    levelOverride: string | null,
    title: string,
    lead: string,
    action: string,
  ): IssueNarrative => ({
    title,
    lead,
    comparison: crossSheet ? comparison : null,
    action,
    tone,
    levelLabel: levelOverride ?? levelFor(tone).levelLabel,
    levelTitle: levelFor(tone).levelTitle,
  })

  switch (issue.rule_id) {
    case "R-CROSS-PAGE-CONFLICT": {
      const [a, b] = groups.filter((group) => group.sheetId)
      const terminal = firstTerminal(views, left)
      const viewA = a?.views[0]
      const viewB = b?.views[0]
      return build(
        "error",
        "需修改",
        "同一端子在两张图上接到了不同的端子",
        `端子 ${terminal || "—"} 在${describeSheet(viewA)}接到 ${viewA?.peer || "—"}，在${describeSheet(viewB)}却接到 ${viewB?.peer || "—"}，两处应一致。`,
        "核对两张图的实际接线，以正确一方为准修改另一张图上的对端端子号。",
      )
    }
    case "R-SUPERWORKS-CONFLICT": {
      const overlap = reasons.some((reason) => OVERLAP_REASON_CODES.includes(reason))
      const strip = reasons.some((reason) => STRIP_REASON_CODES.includes(reason))
      const nonreciprocal = reasons.some((reason) => NONRECIPROCAL_REASON_CODES.includes(reason))
      if (overlap) {
        const terminal = first?.terminal && first.terminal !== UNNUMBERED_TERMINAL ? first.terminal : ""
        return build(
          "review",
          "请核对",
          "同一位置有两个重叠的端子图形",
          `${describeSheet(first)}的${terminal ? ` ${terminal} ` : "一处"}端子位置画了两个重叠的端子图块，其中一个没有编号，程序无法确定它们是否为同一个端子。`,
          "到图上确认该处只有一个端子；若是重复绘制，删除多余图块或补上端子编号。",
        )
      }
      if (strip) {
        return build(
          "review",
          "请核对",
          "端子排的引用找不到对应项",
          `${describeSheet(first)}的端子排中，${left || "一项"}的引用在图上找不到对应的端子。`,
          "核对端子排与对应端子的编号，修正引用或补充缺失的端子。",
        )
      }
      if (nonreciprocal) {
        return build(
          "review",
          "请核对",
          "一端有连接标注，另一端没有回指",
          `${describeSheet(first)}的端子 ${left || "—"} 标注连到 ${right || "—"}，但 ${right || "—"} 没有回指到 ${left || "—"}。`,
          "核对两端的连接标注，补上缺少的回指或删除错误的标注。",
        )
      }
      return build("review", "请核对", issue.title, fallbackLead, fallbackAction)
    }
    case "R-MANY-TO-ONE": {
      const shared = first?.peer || right
      const [v1, v2] = views
      const l1 = v1?.terminal || left
      const l2 = v2?.terminal || "—"
      return build(
        "warning",
        "请确认",
        "多个端子接到了同一个端子",
        `端子 ${shared || "—"} 同时被 ${l1 || "—"}（${v1?.sheetNo ? `图 ${v1.sheetNo}` : "未标注图纸"}）与 ${l2}（${v2?.sheetNo ? `图 ${v2.sheetNo}` : "未标注图纸"}）连接。一个端子通常只接一根线，请确认是否重复连线。`,
        "若是并联或分支，在图上标注保留；否则修正其中一个端子号。",
      )
    }
    case "R-TABLE-MAPPING-SOURCE-CONFLICT":
      return build(
        "error",
        "需修改",
        "端子表与图内连线对同一端子的记录不一致",
        `端子表与图纸上的连线对端子 ${left || first?.terminal || "—"} 给出了不同的记录，以图纸为准核对。`,
        "核对端子表与图内连线，修正记录不一致的一方。",
      )
    case "R-PAIR-MISSING-SIDE": {
      const known = left || right || first?.terminal || "—"
      const nested = issue.evidence?.pair_evidence
      const pairEvidence = nested && typeof nested === "object" ? (nested as Record<string, unknown>) : {}
      const unlabeled =
        issue.evidence?.missing_side_reason === UNLABELLED_PORT_REASON ||
        pairEvidence.missing_side_reason === UNLABELLED_PORT_REASON
      return build(
        "review",
        "请核对",
        "导线只识别到一端的端子号",
        `${describeSheet(first)}的一条导线，只读到 ${known} 一端的端子号，另一端没有识别到编号。${unlabeled ? "该端口在图上没有标注。" : ""}`,
        "到图上确认导线另一端的端子号，并补全标注。",
      )
    }
    case "R-PAIR-LOW-CONFIDENCE":
      return build(
        "review",
        "请核对",
        "导线两端的配对不够确定",
        `端子 ${left || "—"} 与 ${right || "—"} 之间的配对，备选相差不大，程序无法自动确定。`,
        issue.recommended_action || "打开图纸对照两端端子号，确认配对是否正确；若正确可标为已处理。",
      )
    default:
      return build(fallbackTone, null, issue.title, fallbackLead, fallbackAction)
  }
}
