from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from birdmesh.formatting import (
    MAX_TEXT_LENGTH,
    format_alert,
    format_help,
    format_last_seen,
    format_status,
    format_summary,
    format_today,
)
from birdmesh.models import Detection
from birdmesh.state import AppState


class FormattingTests(unittest.TestCase):
    def test_alert_is_friendly_and_omits_time(self) -> None:
        detection = Detection(
            rowid=1,
            observed_at=datetime(2026, 4, 4, 6, 30, tzinfo=timezone.utc),
            scientific_name="Haemorhous mexicanus",
            common_name="House Finch",
            confidence=0.92,
        )

        text = format_alert(detection)

        self.assertEqual(text, "🐦 Look who's here: House Finch! (92%)")
        self.assertNotIn("06:30", text)

    def test_alert_uses_species_category_emoji(self) -> None:
        owl = Detection(
            rowid=1,
            observed_at=datetime(2026, 4, 4, 6, 30, tzinfo=timezone.utc),
            scientific_name="Bubo virginianus",
            common_name="Great Horned Owl",
            confidence=0.95,
        )
        hawk = Detection(
            rowid=2,
            observed_at=datetime(2026, 4, 4, 6, 31, tzinfo=timezone.utc),
            scientific_name="Buteo jamaicensis",
            common_name="Red-tailed Hawk",
            confidence=0.90,
        )

        self.assertTrue(format_alert(owl).startswith("🦉"))
        self.assertTrue(format_alert(hawk).startswith("🦅"))

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
        text = format_summary(state, window_minutes=60)
        self.assertLessEqual(len(text), MAX_TEXT_LENGTH)
        self.assertTrue(text.startswith("🦉 More bird visits:"))
        self.assertNotIn("60m", text)
        self.assertNotIn("det/", text)

    def test_today_reports_daily_counts(self) -> None:
        state = AppState(
            last_detection_at="2026-04-04T06:30:00+00:00",
            daily_counters={
                "2026-04-04": {
                    "detections": 8,
                    "alerts": 2,
                    "summaries": 1,
                    "unique_species": ["Turdus migratorius", "Cyanocitta cristata", "Troglodytes aedon"],
                    "species_names": ["American Robin", "Blue Jay", "House Wren"],
                }
            },
        )
        text = format_today(state, datetime(2026, 4, 4, 7, 0, tzinfo=timezone.utc))
        self.assertEqual(
            text,
            "🦉 Today I've heard 8 visits from 3 species: 🐦 American Robin, 🐦 Blue Jay, 🐦 House Wren.",
        )

    def test_today_falls_back_to_species_keys_from_existing_state(self) -> None:
        state = AppState(
            daily_counters={
                "2026-04-04": {
                    "detections": 2,
                    "alerts": 2,
                    "summaries": 0,
                    "unique_species": ["Robin", "Wren"],
                }
            },
        )

        text = format_today(state, datetime(2026, 4, 4, 7, 0, tzinfo=timezone.utc))

        self.assertEqual(text, "🦉 Today I've heard 2 visits from 2 species: 🐦 Robin, 🐦 Wren.")

    def test_last_seen_reports_elapsed_minutes(self) -> None:
        state = AppState(
            last_detection_at="2026-04-04T06:55:00+00:00",
            last_detection_name="House Finch",
        )

        text = format_last_seen(state, datetime(2026, 4, 4, 7, 0, tzinfo=timezone.utc))

        self.assertEqual(text, "🐦 House Finch stopped by 5 minutes ago!")

    def test_last_seen_handles_no_visitors(self) -> None:
        self.assertEqual(
            format_last_seen(AppState(), datetime(2026, 4, 4, 7, 0, tzinfo=timezone.utc)),
            "🦉 No visitors yet. Check back soon!",
        )

    def test_status_and_help_are_friendly(self) -> None:
        self.assertEqual(format_status(), "🦉 BirdMesh is listening and ready!")
        self.assertIn("Who's here?", format_help())


if __name__ == "__main__":
    unittest.main()
