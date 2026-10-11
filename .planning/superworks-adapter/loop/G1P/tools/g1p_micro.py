"""G1P micro-benchmark (read-only): extract_superworks_semantics on the frozen DXF pages of 8 projects, one code version.

Usage: python g1p_micro.py <src_dir> <out_json> <project ids...>
Each page is read once with ezdxf; extract_superworks_semantics runs three times on the same document and the
minimum is kept per page. Run the HEAD source and the new source in separate processes, alternately, and compare.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path("F:/workspace/XJToolkit")


def main(src: Path, out: Path, projects: list[str]) -> None:
    sys.path.insert(0, str(src))
    import ezdxf
    import dwg_audit.extract.superworks_semantics as sem
    assert str(Path(sem.__file__).resolve()).startswith(str(src.resolve())), sem.__file__
    manifest = json.loads((ROOT / ".planning/superworks-adapter/corpus_manifest.json").read_text(encoding="utf-8"))
    total = 0.0
    pages = {}
    for project in manifest["projects"]:
        if project["project_id"] not in projects:
            continue
        for source in project["files"]:
            doc = ezdxf.readfile(source["dxf_path"])
            best = None
            for _ in range(3):
                started = time.perf_counter()
                sem.extract_superworks_semantics(doc, sheet_id=source["file_id"], file_id=source["file_id"])
                elapsed = time.perf_counter() - started
                best = elapsed if best is None else min(best, elapsed)
            pages[f'{project["project_id"]}:{source["file_id"]}'] = best
            total += best
    out.write_text(json.dumps({"src": str(src), "pages": len(pages), "total_min_seconds": total, "per_page": pages},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print("pages", len(pages), "total_min_seconds", round(total, 3), flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:])
