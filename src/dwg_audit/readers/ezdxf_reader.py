from __future__ import annotations

from pathlib import Path

import ezdxf
from ezdxf.lldxf.const import DXFError

from dwg_audit.readers.base import (
    CadDocument,
    ReaderCapabilities,
    ReaderError,
    ReaderHealth,
    ReaderHealthStatus,
    ReaderOptions,
    ReaderProbe,
)


EZDXF_CAPABILITIES = ReaderCapabilities(
    native_dwg=False,
    blocks=True,
    xdata=True,
    layouts=True,
    preview=False,
    write_support=True,
)


class EzdxfReader:
    """Native DXF reader that preserves the parsed ezdxf document."""

    backend_name = "ezdxf"

    def probe(self) -> ReaderProbe:
        return ReaderProbe(
            backend_name=self.backend_name,
            available=True,
            capabilities=EZDXF_CAPABILITIES,
            backend_version=ezdxf.__version__,
            discovery_source="python-package",
            detail="ezdxf Python package is importable.",
        )

    def health_check(self) -> ReaderHealth:
        probe = self.probe()
        return ReaderHealth(
            status=ReaderHealthStatus.READY,
            backend=self.backend_name,
            version=probe.backend_version,
            checks={"package_importable": True, "dxf_read_support": True},
            detail=probe.detail,
        )

    def read(self, path: Path, options: ReaderOptions) -> CadDocument:
        del options  # DXF reads do not require conversion options.
        source = Path(path)
        if source.suffix.casefold() != ".dxf":
            raise ReaderError(
                "unsupported_format",
                f"ezdxf reader accepts .dxf files only: {source}",
                backend_name=self.backend_name,
            )
        if not source.is_file():
            raise ReaderError(
                "source_not_found",
                f"DXF source file not found: {source}",
                backend_name=self.backend_name,
            )
        try:
            document = ezdxf.readfile(source)
        except DXFError as exc:
            raise ReaderError(
                "invalid_dxf",
                f"Invalid or unsupported DXF document: {source}",
                backend_name=self.backend_name,
            ) from exc
        except OSError as exc:
            code = "source_read_failed" if exc.errno is not None else "invalid_dxf"
            message = (
                f"Unable to read DXF source: {source}"
                if code == "source_read_failed"
                else f"Invalid or unsupported DXF document: {source}"
            )
            raise ReaderError(
                code,
                message,
                backend_name=self.backend_name,
            ) from exc

        probe = self.probe()
        return CadDocument(
            source_path=source,
            document_path=source,
            backend_name=self.backend_name,
            backend_version=probe.backend_version,
            metadata={"discovery_source": probe.discovery_source},
            native_document=document,
        )
