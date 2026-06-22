from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from birdmesh.birdnet import BirdNETDatabase


SCHEMA = """
CREATE TABLE detections (
    Date TEXT,
    Time TEXT,
    Sci_Name TEXT,
    Com_Name TEXT,
    Confidence REAL,
    Lat REAL,
    Lon REAL,
    Cutoff REAL,
    Week INTEGER,
    Sens REAL,
    Overlap REAL,
    File_Name TEXT
)
"""


class BirdNETDatabaseTests(unittest.TestCase):
    def test_fetch_new_detections_parses_expected_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "birds.db"
            connection = sqlite3.connect(db_path)
            connection.execute(SCHEMA)
            connection.execute(
                """
                INSERT INTO detections
                (Date, Time, Sci_Name, Com_Name, Confidence, Lat, Lon, Cutoff, Week, Sens, Overlap, File_Name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("2026-04-04", "06:05:00", "Turdus migratorius", "American Robin", 0.92, 0, 0, 0, 14, 1, 0, "bird.wav"),
            )
            connection.execute(
                """
                INSERT INTO detections
                (Date, Time, Sci_Name, Com_Name, Confidence, Lat, Lon, Cutoff, Week, Sens, Overlap, File_Name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("2026-04-04", "06:06:00", "", "", 0.50, 0, 0, 0, 14, 1, 0, "bad.wav"),
            )
            connection.commit()
            connection.close()

            reader = BirdNETDatabase(db_path, tzinfo=None)
            detections = reader.fetch_new_detections(last_rowid=0)

        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0].common_name, "American Robin")
        self.assertEqual(detections[0].scientific_name, "Turdus migratorius")
        self.assertEqual(detections[0].rowid, 1)

    def test_reader_explicitly_closes_connection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "birds.db"
            setup = sqlite3.connect(db_path)
            setup.execute(SCHEMA)
            setup.commit()
            setup.close()
            connection = sqlite3.connect(db_path)
            reader = BirdNETDatabase(db_path, tzinfo=None)
            reader._connect = lambda: connection

            reader.check()

            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute("SELECT 1")


if __name__ == "__main__":
    unittest.main()
