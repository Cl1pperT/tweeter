from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from .models import Detection


LOGGER = logging.getLogger(__name__)


class BirdNETDatabase:
    def __init__(self, db_path: Path, tzinfo) -> None:
        self.db_path = db_path
        self.tzinfo = tzinfo

    def _connect(self) -> sqlite3.Connection:
        uri = f"file:{self.db_path}?mode=ro"
        return sqlite3.connect(uri, uri=True)

    def check(self) -> None:
        connection = self._connect()
        try:
            connection.execute("SELECT rowid FROM detections ORDER BY rowid DESC LIMIT 1").fetchone()
        finally:
            connection.close()

    def fetch_new_detections(self, last_rowid: int) -> list[Detection]:
        connection = self._connect()
        try:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT
                    rowid,
                    Date,
                    Time,
                    Sci_Name,
                    Com_Name,
                    Confidence,
                    File_Name
                FROM detections
                WHERE rowid > ?
                ORDER BY rowid ASC
                """,
                (last_rowid,),
            ).fetchall()
        finally:
            connection.close()
        return list(self._parse_rows(rows))

    def fetch_latest_detection(self) -> Detection | None:
        connection = self._connect()
        try:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT
                    rowid,
                    Date,
                    Time,
                    Sci_Name,
                    Com_Name,
                    Confidence,
                    File_Name
                FROM detections
                ORDER BY rowid DESC
                LIMIT 10
                """
            ).fetchall()
        finally:
            connection.close()
        return next(iter(self._parse_rows(rows)), None)

    def _parse_rows(self, rows: Iterable[sqlite3.Row]) -> Iterable[Detection]:
        for row in rows:
            try:
                observed_at = datetime.strptime(f"{row['Date']} {row['Time']}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=self.tzinfo)
                scientific_name = (row["Sci_Name"] or "").strip()
                common_name = (row["Com_Name"] or scientific_name).strip()
                confidence = float(row["Confidence"])
                if not scientific_name and not common_name:
                    raise ValueError("missing bird name")
                yield Detection(
                    rowid=int(row["rowid"]),
                    observed_at=observed_at,
                    scientific_name=scientific_name or common_name,
                    common_name=common_name or scientific_name,
                    confidence=max(0.0, min(confidence, 1.0)),
                    file_name=row["File_Name"],
                )
            except Exception as exc:  # noqa: BLE001 - malformed BirdNET rows should not crash the daemon
                LOGGER.warning("Skipping malformed BirdNET row %s: %s", dict(row), exc)
