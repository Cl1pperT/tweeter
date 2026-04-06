from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Detection:
    rowid: int
    observed_at: datetime
    scientific_name: str
    common_name: str
    confidence: float
    file_name: str | None = None

    @property
    def species_key(self) -> str:
        return self.scientific_name.strip() or self.common_name.strip()


@dataclass(frozen=True, slots=True)
class CommandMessage:
    sender: int | str
    text: str
