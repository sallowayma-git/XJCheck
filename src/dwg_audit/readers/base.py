from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class ReaderCapabilities:
    native_dwg: bool = False
    blocks: bool = False
    xdata: bool = False
    layouts: bool = False
    preview: bool = False
    write_support: bool = False


@dataclass(frozen=True, slots=True)
class ReaderProbe:
    backend_name: str
    available: bool
    capabilities: ReaderCapabilities
    backend_version: str | None = None
    executable_path: Path | None = None
    discovery_source: str | None = None
    detail: str | None = None


class ReaderHealthStatus(str, Enum):
    READY = "READY"
    UNAVAILABLE = "UNAVAILABLE"
    DEGRADED = "DEGRADED"


@dataclass(frozen=True, slots=True)
class ReaderHealth:
    status: ReaderHealthStatus
    backend: str
    version: str | None = None
    build: str | None = None
    checks: dict[str, bool] = field(default_factory=dict)
    error_code: str | None = None
    detail: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "backend": self.backend,
            "version": self.version,
            "build": self.build,
            "checks": dict(self.checks),
            "error_code": self.error_code,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class ReaderOptions:
    output_path: Path | None = None
    target_version: str = "R2018"
    audit: bool = True
    replace: bool = True


@dataclass(slots=True)
class CadDocument:
    source_path: Path
    document_path: Path
    backend_name: str
    backend_version: str | None = None
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    native_document: Any | None = field(default=None, repr=False)


class ReaderError(RuntimeError):
    def __init__(self, code: str, message: str, *, backend_name: str) -> None:
        super().__init__(message)
        self.code = code
        self.backend_name = backend_name


class CadReader(Protocol):
    backend_name: str

    def probe(self) -> ReaderProbe: ...

    def health_check(self) -> ReaderHealth: ...

    def read(self, path: Path, options: ReaderOptions) -> CadDocument: ...
