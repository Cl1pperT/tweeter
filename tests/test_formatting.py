from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from birdmesh.formatting import MAX_TEXT_LENGTH, format_status, format_summary
from birdmesh.state import AppState


class FormattingTests(unittest.TestCase):
    def test_summary_truncates_with_more_suffix(self) -> None:
        state = AppState(
            pending_summary_total=25,
            pending_summary_species={
                "American Robin": {"count": 10, "max_confidence": 0.9},
                "Black-capped Chickadee": {"count": 8, "max_confidence": 0.8},
                "Mountain Bluebird": {"count": 4, "max_confidence": 0.7},
                "Northern Flicker": {"count": 3, "max_confidence": 0.6},
            },
        )
        text = format_summary(state, window_minutes=15)
        self.assertLessEqual(len(text), MAX_TEXT_LENGTH)
        self.assertIn("BirdMesh sum 25 det/4 spp/15m:", text)

    def test_status_compacts_daily_counts(self) -> None:
        state = AppState(
            last_detection_at="2026-04-04T06:30:00+00:00",
            daily_counters={
                "2026-04-04": {
                    "detections": 8,
                    "alerts": 2,
                    "summaries": 1,
                    "unique_species": ["Robin", "Jay", "Wren"],
                }
            },
        )
        text = format_status(state, datetime(2026, 4, 4, 7, 0, tzinfo=timezone.utc), db_ok=True, mesh_ok=False)
        self.assertIn("db=ok", text)
        self.assertIn("mesh=err", text)
        self.assertIn("today=8det/3spp", text)


if __name__ == "__main__":
    unittest.main()
