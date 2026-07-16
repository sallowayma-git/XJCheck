from __future__ import annotations

from collections.abc import Mapping

from dwg_audit.readers.base import CadReader, ReaderError, ReaderProbe
from dwg_audit.readers.ezdxf_reader import EzdxfReader
from dwg_audit.readers.oda_reader import OdaFileConverterReader


class ReaderRegistry:
    def __init__(self, readers: Mapping[str, CadReader]) -> None:
        self._readers = dict(readers)

    @classmethod
    def from_config(cls, config: Mapping[str, object]) -> "ReaderRegistry":
        oda_reader = OdaFileConverterReader(config)
        ezdxf_reader = EzdxfReader()
        return cls(
            {
                oda_reader.backend_name: oda_reader,
                ezdxf_reader.backend_name: ezdxf_reader,
            }
        )

    def get(self, backend_name: str) -> CadReader:
        try:
            return self._readers[backend_name]
        except KeyError as exc:
            raise ReaderError(
                "unknown_backend",
                f"Unknown CAD reader backend: {backend_name}",
                backend_name=backend_name,
            ) from exc

    def configured(self, config: Mapping[str, object]) -> CadReader:
        ingest = config.get("ingest", {})
        ingest_config = ingest if isinstance(ingest, Mapping) else {}
        backend_name = str(ingest_config.get("dwg_reader", "odafc"))
        return self.get(backend_name)

    def probes(self) -> dict[str, ReaderProbe]:
        return {name: reader.probe() for name, reader in self._readers.items()}
