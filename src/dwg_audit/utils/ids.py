from __future__ import annotations

from dataclasses import dataclass


@dataclass
class IdFactory:
    prefix: str
    width: int = 4
    counter: int = 0

    def next(self) -> str:
        self.counter += 1
        return f"{self.prefix}{self.counter:0{self.width}d}"
