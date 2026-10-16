from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[6]
AUDIT = ROOT / ".planning/superworks-adapter/loop/PRECISION-FOLLOWUP-2026-10-16/frame-rule"
SAMPLE = AUDIT / "sample_frame_review.csv"
SCREENSHOTS = ROOT / ".tmp/precision_loop_20261016/frame_rule_full77/sample_frame_screenshots"
OUT_IMAGES = AUDIT / "wide_screenshots"

# (project, record, frame-stop judgment, manual need, reason, independent review batch)
REVIEWS = [
    ("p000", "PSW1f6336c3f9fba61f", "yes", "no", "908 短线止于闭合虚线框右边；框内有保护回路行，框顶可见 WWH-813-D1F。", "A"),
    ("p002", "PSW0dc994f315d4d037", "yes", "no", "907 短线止于虚线装置框右边；框顶可见 WWH-813-D1F。", "A"),
    ("p003", "PSW69182e0392c8b06e", "yes", "no", "608 短线止于虚线框左边；框内为成组保护回路，设备标签可见。", "A"),
    ("p005", "PSWe8e2c760745a1872", "yes", "no", "312 短线止于闭合虚线框右边；框顶可见 ZSZ-812E。", "A"),
    ("p007", "PSWd34c94aac8b700d4", "yes", "no", "1127 短线止于虚线框左边；框内为成组支路行，设备标签可见。", "A"),
    ("p009", "PSWc4269cae7c869792", "yes", "no", "2613 短线止于右侧虚线框左边；框顶可见 WMH-800-D1C-02。", "A"),
    ("p009", "PSW1ef49f34070b5913", "yes", "no", "1107 短线止于支路输出虚线框左边；设备标签可见。", "A"),
    ("p010", "PSWdac51037c5db250f", "yes", "no", "903 短线止于虚线框左边；框内为成组支路行，设备标签可见。", "A"),
    ("p011", "PSWd3fe53c55b3d81ed", "yes", "no", "721 短线止于标有 WMH-800-D1C 的虚线框左边；框内有成组 DC 信号行。", "A"),
    ("p011", "PSW84e5f725581cb1a1", "yes", "no", "924 短线止于支路输出虚线框右边；框边和设备标签可见。", "A"),
    ("p012", "PSW1f75dfad9e6e981e", "yes", "no", "1315 短线止于失灵联跳虚线框左边；设备标签可见。", "A"),
    ("p012", "PSW3b27d10ea606c437", "yes", "no", "2519 短线止于 CT 输入虚线框左边；框内 CT 行和设备标签可见。", "A"),
    ("p013", "PSW163d05e4d77c1196", "no", "yes", "候选线穿过框边并继续到框外 1S3LP 端子 2，不是止于框边。", "A"),
    ("p013", "PSWb7a63ebf9939380c", "yes", "no", "711 短线止于标有 WMH-800-D1C 的虚线框左边。", "A"),
    ("p014", "PSW864ac30ef4212842", "yes", "no", "2610 短线止于 CT 输入虚线框右边；设备标签可见。", "A"),
    ("p015", "PSW182b73a08581a82e", "yes", "no", "1119 短线止于支路输出虚线框左边；框内成组支路行和标签可见。", "A"),
    ("p015", "PSWe67b37cc2be00122", "no", "yes", "候选线穿过框边并继续到框外 1S15LP 端子 2，不是止于框边。", "A"),
    ("p015", "PSW09e10423d3889046", "yes", "no", "919 短线止于支路输出虚线框左边；设备标签可见。", "A"),
    ("p017", "PSW6aaf91ed5e87feef", "yes", "no", "2612 短线止于 CT 输入虚线框右边；框内 CT 行和设备标签可见。", "A"),
    ("p017", "PSW802f1e530f9cc5ef", "yes", "no", "1119 短线止于支路输出虚线框左边；设备标签可见。", "A"),
    ("p018", "PSW018a00f78a3fa16e", "yes", "no", "1204 短线止于失灵联跳虚线框右边；框内成组输出行和标签可见。", "A"),
    ("p018", "PSW84e5f725581cb1a1", "yes", "no", "924 短线止于支路输出虚线框右边；闭合虚线边和设备标签可见。", "A"),
    ("p018", "PSWe3b21484a24f2925", "yes", "no", "1220 短线止于失灵联跳虚线框右边；框内行列和标签可见。", "A"),
    ("p019", "PSWb6cf17e7e8e199d5", "yes", "no", "2522 短线止于 CT 输入虚线框右边；框内 CT 行和标签可见。", "A"),
    ("p020", "PSWaf09a1c215d84037", "yes", "no", "1127 短线止于支路输出虚线框左边；设备标签可见。", "A"),
    ("p021", "PSW12876c02226ecb6b", "yes", "no", "2506 短线止于 CT 输入虚线框右边；框内成组 CT 行和标签可见。", "A"),
    ("p021", "PSW24b7e1ca146d836e", "yes", "no", "2613 引脚短线从 WMH-800-D1C 闭合框左边止于框内；框线和设备标签可见。", "A"),

    ("p023", "PSWeb3bc2f7c82c6f61", "no", "yes", "1-7QD9 到 832 的线段穿过 ZYQ-810E 框边；端点身份仍需人工确认。", "B"),
    ("p024", "PSWbe2a90d324411c34", "yes", "no", "832 短线止于有 2-7n / ZYQ-810E 标签的虚线框左边。", "B"),
    ("p026", "PSW96b2a110dfca6a98", "yes", "no", "707 短线止于端子框边；旁侧可见压力开关标注。", "B"),
    ("p026", "PSW20097267144a5500", "yes", "no", "818 短线止于压力开关端子框右边。", "B"),
    ("p026", "PSW6b6eb7f86e3fcee9", "yes", "no", "127 短线止于同一压力开关端子框边。", "B"),
    ("p027", "PSWb7caaf86d322231e", "yes", "no", "324 短线止于标有 1STJ5-1 的虚线框左边。", "B"),
    ("p027", "PSW334a088d40e76f98", "yes", "no", "626 短线止于同一标有 1STJ5-1 的虚线框左边。", "B"),
    ("p027", "PSW0d27645fa5449642", "no", "yes", "导线穿过 From BCU 框边并继续到框外 3-4QD11 端子；仍需核对端点身份。", "B"),
    ("p027", "PSWded42459b9879e3a", "yes", "no", "612 短线的候选端点落在标有 ZSZ-812E 的闭合框左边；黑点和后续支路在框内。", "B"),
    ("p028", "PSW4bf837c75a913eb4", "no", "yes", "候选线穿过 CIRCUIT BREAKER 框边并接到 X7 端子。", "B"),
    ("p028", "PSWecdd0338203f361e", "no", "yes", "候选线穿过 GRUS 框左边并继续到 X19 端子。", "B"),
    ("p029", "PSW1d0e9d1c8730bda7", "uncertain", "yes", "候选线贴近断路器框边并延至接点行；全框图不能确定端点关系。", "B"),
    ("p029", "PSW9acdd8e25fd70179", "uncertain", "yes", "候选线与断路器框边及接点行重叠；全框图不能确定端点关系。", "B"),
    ("p029", "PSWe7bf98206feef16f", "no", "yes", "导线从断路器框内延伸至 52a 接点，不止于框边。", "B"),
    ("p029", "PSWe265614520be1ed7", "no", "yes", "候选线越过断路器框边并延伸到接点行。", "B"),
    ("p029", "PSW33cc5b84e21f1a0d", "yes", "no", "832 短线止于有 1-7n / ZYQ-810E 标签的虚线框左边。", "B"),
    ("p030", "PSW4df722431511ab77", "no", "yes", "候选线穿过断路器框边并连接到装置端子行。", "B"),
    ("p030", "PSW1d0e9d1c8730bda7", "no", "yes", "候选线越过断路器框边并延伸到 X8 端子。", "B"),
    ("p030", "PSWf4cf43ae7996316b", "no", "yes", "候选线穿过 GRUS 框边并延伸到框外空白处。", "B"),
    ("p030", "PSWc3dab2f65874d06a", "no", "yes", "候选线穿过断路器框边并延伸到 52a 接点。", "B"),
    ("p031", "PSW6c8cd1c2a253586f", "no", "yes", "候选线越过 GRUS 框左边并延伸到 2X2 端子行。", "B"),
    ("p031", "PSW0bd9549393aab229", "no", "yes", "候选线越过断路器框边并延伸到 52a 接点。", "B"),
    ("p031", "PSW50c65cd792bbfe33", "no", "yes", "候选线越过 GRUS 框左边并延伸到 X4 端子。", "B"),
    ("p031", "PSWe7bf98206feef16f", "no", "yes", "候选线越过断路器框边并延伸到 52a 接点。", "B"),
    ("p031", "PSWf4cf43ae7996316b", "no", "yes", "候选线穿过 GRUS 框并延伸到框外，未止于边界。", "B"),
    ("p031", "PSWc90764d8388e9f96", "no", "yes", "候选线越过 GRUS 框左边并延伸到 X19 端子行。", "B"),

    ("p031", "PSWb70618fae1eb96e0", "no", "yes", "线越过 ZYQ-810E 框边并止于 832 字样附近；未见明确端子或接点。", "C"),
    ("p031", "PSWd8dffa42748bc02e", "no", "no", "导线跨过设备框右边并接入黑点及竖向母线。", "C"),
    ("p031", "PSW7e2b895d9ffa9627", "no", "no", "导线跨过断路器框左边并连到 X5 端子。", "C"),
    ("p031", "PSW3abfc5f775920498", "no", "yes", "候选线穿过框右边继续向外；外侧目标身份仍不清楚。", "C"),
    ("p031", "PSWe5abbc585fcf0a59", "no", "no", "导线跨过断路器框右边并连到 52a 触点。", "C"),
    ("p031", "PSWc3dab2f65874d06a", "no", "no", "导线跨过断路器框右边并连到 52a 触点。", "C"),
    ("p033", "PSW98b34b18a44ad28e", "no", "yes", "线越过 ZYQ-810E 框边并止于 832 字样附近；未见明确端子或接点。", "C"),
    ("p033", "PSW37b8b7a37ebe75e5", "yes", "no", "1-7n803 短线止于标有 ZYQ-810E 的闭合虚线框左边；框内母线属于装置内部。", "C"),
    ("p035", "PSWde8859ecfa8a5189", "no", "no", "导线跨过设备框边并延伸到 CONTROL POWER 线路。", "C"),
    ("p040", "PSWd6d06fb1c79c76d4", "no", "no", "MMS A 导线穿过交换机框边并连到 LAN1，端点标记可见。", "C"),
    ("p040", "PSWf686b90b283498b8", "no", "no", "MMS B 导线穿过交换机框边并连到 LAN2，端点标记可见。", "C"),
    ("p044", "PSW757c435a4558659c", "no", "no", "导线从 1-1Q2D21 跨入 WFB-821E 框内并接到 1-1n202。", "C"),
    ("p044", "PSW86491bf03fbbdc83", "no", "no", "导线跨出 WFB-821E 框边并接到 1-1CD5 端子。", "C"),
    ("p044", "PSW439735fc41b553fb", "no", "no", "导线从 1-1Q2D17 跨入 WFB-821E 框内并接到 1-1n230。", "C"),
    ("p044", "PSW9fd1853b2fe0ee09", "no", "no", "导线跨出 WFB-821E 框边并接到 1-1CD2 端子。", "C"),
    ("p044", "PSW8e799ad930f782b1", "no", "no", "导线跨出 WFB-821E 框边并接到 1-1CD4 端子。", "C"),
    ("p045", "PSWba02b2bfcae50690", "no", "no", "KK1 的 4 脚导线穿过虚线框并接入 703 线路。", "C"),
    ("p045", "PSW32746ef473684b9b", "no", "no", "KK3 的 4 脚导线穿过虚线框并接入 719 线路。", "C"),
    ("p053", "PSWbe5ce9cb4a2513bd", "no", "no", "GND 导线跨过 DGICOM4000 框边并向框内 PWR 端延伸。", "C"),
    ("p064", "PSWa81e59c28d89ad71", "yes", "no", "短线末端落在标注 ZSZ-812E 的闭合虚线框右边，框外无续线。", "C"),
    ("p065", "PSW87bb167e6ba58a03", "yes", "no", "920 短线止于标有 WMH-800-D1C 的闭合虚线模块框右边。", "C"),
    ("p066", "PSWa63c99310f3246c1", "yes", "no", "1008 短线止于标有 WMH-800-D1C 的闭合虚线模块框右边。", "C"),
    ("p066", "PSWb23d022f263bdedc", "yes", "no", "1011 短线止于标有 WMH-800-D1C 的闭合虚线框左边；框内回路是装置内部。", "C"),
    ("p070", "PSWae2a6c2b0fc4c263", "no", "no", "导线跨过设备框左边并接到带竖向支路的黑色节点。", "C"),
    ("p072", "PSW0988c426c938d549", "yes", "no", "1010 短线止于标有 ZFZ-812E 的闭合虚线框左边；黑点和竖线在框内。", "C"),
]


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, default=SAMPLE)
    parser.add_argument("--screenshots", type=Path, default=SCREENSHOTS)
    parser.add_argument("--images-out", type=Path, default=OUT_IMAGES)
    args = parser.parse_args()

    keys = [(row[0], row[1]) for row in REVIEWS]
    if len(REVIEWS) != 78 or len(set(keys)) != 78:
        raise SystemExit(f"Review table must contain 78 unique cases; got {len(REVIEWS)} rows, {len(set(keys))} keys")
    table = pd.read_csv(args.sample, dtype=str).fillna("")
    table["_key"] = list(zip(table.project_id, table.record_id))
    by_key = {row._key: index for index, row in table.iterrows()}
    missing = set(keys) - by_key.keys()
    if missing:
        raise SystemExit(f"Review cases missing from sample CSV: {sorted(missing)}")

    args.images_out.mkdir(parents=True, exist_ok=True)
    for project, record, frame_judgment, manual_need, reason, batch in REVIEWS:
        index = by_key[(project, record)]
        row = table.loc[index]
        source = args.screenshots / Path(row.screenshot).name
        if not source.is_file():
            raise SystemExit(f"Screenshot missing for {project}/{record}: {source}")
        target = args.images_out / source.name
        if not target.is_file():
            shutil.copy2(source, target)
        file_hash = sha256(target)
        expected_hash = str(row.sha256).strip()
        if expected_hash and file_hash != expected_hash:
            raise SystemExit(f"Screenshot hash mismatch for {project}/{record}: {file_hash} != {expected_hash}")
        table.loc[index, "manual_review_before_wide"] = row.manual_review_need
        table.loc[index, "manual_review_need"] = manual_need
        table.loc[index, "wide_frame_judgment"] = frame_judgment
        table.loc[index, "wide_frame_reason"] = reason
        table.loc[index, "wide_frame_reviewer"] = f"独立原图复核批次 {batch}"
        table.loc[index, "screenshot"] = f"wide_screenshots/{target.name}"
        table.loc[index, "sha256"] = file_hash

    table.drop(columns="_key", inplace=True)
    table.to_csv(args.sample, index=False, encoding="utf-8-sig")
    print(f"reviewed={len(REVIEWS)}; screenshots={len(REVIEWS)}; image_dir={args.images_out}")


if __name__ == "__main__":
    main()
