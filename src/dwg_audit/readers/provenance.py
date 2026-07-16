from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any

from dwg_audit.readers.base import ReaderCapabilities, ReaderProbe


READER_CONTRACT_VERSION = "1.0.0"
READER_CACHE_SCHEMA_VERSION = "reader-cache/v1"
READER_RUN_SCHEMA_VERSION = "reader-run/v1"
READER_RUN_MANIFEST_SCHEMA_VERSION = "reader-run-manifest/v1"


@dataclass(frozen=True, slots=True)
class ReaderCacheIdentity:
    source_sha256: str
    reader_backend: str
    reader_version: str | None
    reader_build_id: str | None
    reader_options: dict[str, Any]
    reader_contract_version: str = READER_CONTRACT_VERSION
    schema_version: str = READER_CACHE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.reader_version and not self.reader_build_id:
            raise ValueError("Reader cache identity requires a version or build ID.")

    def payload(self) -> dict[str, Any]:
        return asdict(self)

    def canonical_json(self) -> str:
        return json.dumps(
            self.payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def cache_key(self) -> str:
        return sha256(self.canonical_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ReaderRun:
    file_id: str
    backend_name: str
    backend_version: str | None
    backend_build_id: str | None
    capabilities: dict[str, bool]
    discovery_source: str | None
    options: dict[str, Any]
    status: str
    cache_hit: bool
    cache_identity_enforced: bool
    document_path: str | None
    error_code: str | None
    detail: str | None
    health_status: str | None = None
    health_error_code: str | None = None
    health_checks: dict[str, bool] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    cache_identity: dict[str, Any] | None = None
    cache_key: str | None = None
    reader_contract_version: str = READER_CONTRACT_VERSION
    schema_version: str = READER_RUN_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ReaderRunManifest:
    project_id: str
    runs: list[ReaderRun]
    schema_version: str = READER_RUN_MANIFEST_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "runs": [run.to_dict() for run in self.runs],
        }


def normalized_reader_options(*, target_version: str, audit: bool) -> dict[str, Any]:
    return {
        "output_format": "dxf",
        "target_version": target_version,
        "audit": audit,
        "replace": True,
    }


def executable_build_id(executable: Path | None) -> str | None:
    if executable is None or not executable.is_file():
        return None
    digest = sha256()
    with executable.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def infer_backend_version(executable: Path | None) -> str | None:
    if executable is None:
        return None
    match = re.search(
        r"ODAFileConverter[ _-]+(?P<version>\d+(?:\.\d+)+)",
        str(executable),
        re.IGNORECASE,
    )
    return match.group("version") if match else None


def build_cache_identity(
    *,
    source_sha256: str,
    probe: ReaderProbe,
    backend_version: str | None,
    backend_build_id: str | None,
    options: dict[str, Any],
) -> ReaderCacheIdentity | None:
    if not backend_version and not backend_build_id:
        return None
    return ReaderCacheIdentity(
        source_sha256=source_sha256,
        reader_backend=probe.backend_name,
        reader_version=backend_version,
        reader_build_id=backend_build_id,
        reader_options=options,
    )


def capabilities_dict(capabilities: ReaderCapabilities) -> dict[str, bool]:
    return asdict(capabilities)
