from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .models import Detection


def _default_daily_counter() -> dict[str, int | list[str]]:
    return {
        "detections": 0,
        "alerts": 0,
        "summaries": 0,
        "unique_species": [],
        "species_names": [],
    }


def _normalize_species_name(name: str) -> str:
    return " ".join(name.split()).casefold()


def _load_species_names(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    names: dict[str, str] = {}
    for item in value:
        if not isinstance(item, str):
            continue
        cleaned = " ".join(item.split())
        if cleaned:
            names[_normalize_species_name(cleaned)] = cleaned
    return sorted(names.values(), key=str.casefold)


@dataclass(slots=True)
class AppState:
    last_rowid: int = 0
    last_detection_at: str | None = None
    last_detection_name: str | None = None
    last_summary_at: str | None = None
    pending_window_started_at: str | None = None
    pending_summary_total: int = 0
    pending_summary_species: dict[str, dict[str, int | float]] = field(default_factory=dict)
    alerted_species_by_day: dict[str, list[str]] = field(default_factory=dict)
    daily_counters: dict[str, dict[str, int | list[str]]] = field(default_factory=dict)
    whitelisted_species: list[str] = field(default_factory=list)
    blacklisted_species: list[str] = field(default_factory=list)

    def record_detection(
        self,
        detection: Detection,
        alerted: bool,
        include_in_summary: bool = True,
    ) -> None:
        day = detection.observed_at.date().isoformat()
        counters = self.daily_counters.setdefault(day, _default_daily_counter())
        counters["detections"] = int(counters["detections"]) + 1
        unique_species = set(counters["unique_species"])
        unique_species.add(detection.species_key)
        counters["unique_species"] = sorted(unique_species)
        species_names = set(counters.get("species_names", []))
        species_names.add(detection.common_name)
        counters["species_names"] = sorted(species_names, key=str.casefold)
        if alerted:
            counters["alerts"] = int(counters["alerts"]) + 1
            alerted_species = set(self.alerted_species_by_day.setdefault(day, []))
            alerted_species.add(detection.species_key)
            self.alerted_species_by_day[day] = sorted(alerted_species)
        elif include_in_summary:
            self.pending_summary_total += 1
            stats = self.pending_summary_species.setdefault(
                detection.common_name,
                {"count": 0, "max_confidence": 0.0},
            )
            stats["count"] = int(stats["count"]) + 1
            stats["max_confidence"] = max(float(stats["max_confidence"]), detection.confidence)
            if not self.pending_window_started_at:
                self.pending_window_started_at = detection.observed_at.isoformat()
        self.last_rowid = max(self.last_rowid, detection.rowid)
        self.last_detection_at = detection.observed_at.isoformat()
        self.last_detection_name = detection.common_name

    def mark_summary_sent(self, now: datetime) -> None:
        today = now.date().isoformat()
        counters = self.daily_counters.setdefault(today, _default_daily_counter())
        counters["summaries"] = int(counters["summaries"]) + 1
        self.pending_summary_total = 0
        self.pending_summary_species = {}
        self.pending_window_started_at = None
        self.last_summary_at = now.isoformat()

    def has_alerted_species(self, day: str, species_key: str) -> bool:
        return species_key in set(self.alerted_species_by_day.get(day, []))

    def notification_tier(self, detection: Detection) -> str:
        detection_names = {
            _normalize_species_name(detection.common_name),
            _normalize_species_name(detection.scientific_name),
        }
        if detection_names & {_normalize_species_name(name) for name in self.blacklisted_species}:
            return "blacklist"
        if detection_names & {_normalize_species_name(name) for name in self.whitelisted_species}:
            return "whitelist"
        return "default"

    def listed_species(self, list_name: str) -> list[str]:
        return list(self._species_list(list_name))

    def add_listed_species(self, list_name: str, species_name: str) -> tuple[str, bool, bool]:
        cleaned = " ".join(species_name.split())
        if not cleaned:
            raise ValueError("species name cannot be empty")

        target = self._species_list(list_name)
        other = self._species_list("blacklist" if list_name == "whitelist" else "whitelist")
        normalized = _normalize_species_name(cleaned)
        existing = next((name for name in target if _normalize_species_name(name) == normalized), None)
        if existing is None:
            target.append(cleaned)
            target.sort(key=str.casefold)
        removed_from_other = self._remove_matching(other, normalized) is not None
        return existing or cleaned, existing is None, removed_from_other

    def remove_listed_species(self, list_name: str, species_name: str) -> str | None:
        return self._remove_matching(self._species_list(list_name), _normalize_species_name(species_name))

    def drop_pending_summary_species(self, species_name: str) -> int:
        normalized = _normalize_species_name(species_name)
        matching_names = [
            name
            for name in self.pending_summary_species
            if _normalize_species_name(name) == normalized
        ]
        removed = 0
        for name in matching_names:
            stats = self.pending_summary_species.pop(name)
            removed += int(stats["count"])
        self.pending_summary_total = max(0, self.pending_summary_total - removed)
        if self.pending_summary_total == 0:
            self.pending_window_started_at = None
        return removed

    def _species_list(self, list_name: str) -> list[str]:
        if list_name == "whitelist":
            return self.whitelisted_species
        if list_name == "blacklist":
            return self.blacklisted_species
        raise ValueError(f"unknown species list: {list_name}")

    @staticmethod
    def _remove_matching(species_names: list[str], normalized: str) -> str | None:
        for index, name in enumerate(species_names):
            if _normalize_species_name(name) == normalized:
                return species_names.pop(index)
        return None

    def today_counts(self, day: str) -> dict[str, int]:
        counters = self.daily_counters.get(day, _default_daily_counter())
        return {
            "detections": int(counters["detections"]),
            "alerts": int(counters["alerts"]),
            "summaries": int(counters["summaries"]),
            "unique_species": len(set(counters["unique_species"])),
        }

    def today_species(self, day: str) -> list[str]:
        counters = self.daily_counters.get(day, _default_daily_counter())
        names = counters.get("species_names", [])
        return sorted({str(name) for name in names}, key=str.casefold)

    def set_today_species(self, day: str, species_names: list[str]) -> None:
        counters = self.daily_counters.setdefault(day, _default_daily_counter())
        counters["species_names"] = sorted(set(species_names), key=str.casefold)

    def trim(self, keep_days: int = 7) -> None:
        all_days = sorted(set(self.alerted_species_by_day) | set(self.daily_counters))
        days_to_drop = all_days[:-keep_days] if len(all_days) > keep_days else []
        for day in days_to_drop:
            self.alerted_species_by_day.pop(day, None)
            self.daily_counters.pop(day, None)

    def to_dict(self) -> dict[str, object]:
        return {
            "last_rowid": self.last_rowid,
            "last_detection_at": self.last_detection_at,
            "last_detection_name": self.last_detection_name,
            "last_summary_at": self.last_summary_at,
            "pending_window_started_at": self.pending_window_started_at,
            "pending_summary_total": self.pending_summary_total,
            "pending_summary_species": self.pending_summary_species,
            "alerted_species_by_day": self.alerted_species_by_day,
            "daily_counters": self.daily_counters,
            "whitelisted_species": self.whitelisted_species,
            "blacklisted_species": self.blacklisted_species,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "AppState":
        blacklisted_species = _load_species_names(payload.get("blacklisted_species", []))
        blacklisted_keys = {_normalize_species_name(name) for name in blacklisted_species}
        whitelisted_species = [
            name
            for name in _load_species_names(payload.get("whitelisted_species", []))
            if _normalize_species_name(name) not in blacklisted_keys
        ]
        return cls(
            last_rowid=int(payload.get("last_rowid", 0)),
            last_detection_at=payload.get("last_detection_at") or None,
            last_detection_name=payload.get("last_detection_name") or None,
            last_summary_at=payload.get("last_summary_at") or None,
            pending_window_started_at=payload.get("pending_window_started_at") or None,
            pending_summary_total=int(payload.get("pending_summary_total", 0)),
            pending_summary_species=dict(payload.get("pending_summary_species", {})),
            alerted_species_by_day={key: list(value) for key, value in dict(payload.get("alerted_species_by_day", {})).items()},
            daily_counters={key: dict(value) for key, value in dict(payload.get("daily_counters", {})).items()},
            whitelisted_species=whitelisted_species,
            blacklisted_species=blacklisted_species,
        )


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> AppState:
        if not self.path.exists():
            return AppState()
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return AppState.from_dict(payload)

    def save(self, state: AppState) -> None:
        state.trim()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(dir=self.path.parent, prefix=".birdmesh-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(state.to_dict(), handle, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
