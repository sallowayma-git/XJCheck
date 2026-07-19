from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from dwg_audit.readers.oda_process import ODA_JOB_ENV
from dwg_audit.readers.oda_process import join_named_windows_job


def run_worker(request: dict[str, Any]) -> dict[str, Any]:
    operation = request.get("operation")
    if operation == "convert":
        return _run_conversion(request)
    if operation == "smoke":
        return _run_smoke(request)
    return {
        "ok": False,
        "error_code": "ODA_WORKER_PROTOCOL",
        "detail": f"Unsupported ODA worker operation: {operation!r}.",
    }


def _run_conversion(request: dict[str, Any]) -> dict[str, Any]:
    source = Path(str(request["source"])).expanduser()
    target = Path(str(request["target"])).expanduser()
    executable = Path(str(request["executable"])).expanduser()
    from ezdxf.addons import odafc

    from dwg_audit.readers.oda_reader import oda_execution_environment

    with oda_execution_environment(executable):
        odafc.convert(
            source,
            target,
            version=str(request.get("version") or "R2018"),
            audit=bool(request.get("audit", True)),
            replace=bool(request.get("replace", True)),
        )
    if not target.exists():
        return {
            "ok": False,
            "error_code": "ODA_NO_OUTPUT",
            "detail": f"ODA conversion produced no output: {target}",
        }
    return {"ok": True}


def _run_smoke(request: dict[str, Any]) -> dict[str, Any]:
    executable = Path(str(request["executable"])).expanduser()
    import ezdxf
    from ezdxf.addons import odafc

    from dwg_audit.readers.oda_reader import oda_execution_environment

    with tempfile.TemporaryDirectory(prefix="xjcheck_odafc_health_") as temp_dir:
        root = Path(temp_dir)
        source = root / "health_input.dxf"
        target = root / "health_output.dxf"
        document = ezdxf.new("R2018")
        document.modelspace().add_line((0, 0), (10, 0))
        document.saveas(source)
        with oda_execution_environment(executable):
            odafc.convert(
                source,
                target,
                version="R2018",
                audit=True,
                replace=True,
            )
        readback = ezdxf.readfile(target)
        return {"ok": True, "result": len(readback.modelspace()) == 1}


def main(_argv: list[str] | None = None) -> int:
    try:
        join_named_windows_job(os.environ.get(ODA_JOB_ENV))
        line = sys.stdin.buffer.readline()
        if not line:
            raise ValueError("ODA worker request was empty.")
        request = json.loads(line.decode("utf-8"))
        if not isinstance(request, dict):
            raise ValueError("ODA worker request must be a JSON object.")
        response = run_worker(request)
    except BaseException as exc:  # worker boundary must always return one response
        response = {
            "ok": False,
            "error_code": "ODA_WORKER_EXCEPTION",
            "error_type": type(exc).__name__,
            "detail": str(exc) or type(exc).__name__,
        }
    sys.stdout.write(json.dumps(response, ensure_ascii=True) + "\n")
    sys.stdout.flush()
    return 0 if response.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
