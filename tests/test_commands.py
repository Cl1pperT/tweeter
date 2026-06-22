from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from birdmesh.commands import command_kind


class CommandTests(unittest.TestCase):
    def test_all_supported_commands_are_case_insensitive(self) -> None:
        commands = {
            "who's here?": "last_seen",
            "whos here?": "last_seen",
            "who is here?": "last_seen",
            "bird who's here?": "last_seen",
            "bird who?": "last_seen",
            "birds today?": "today",
            "what have you seen?": "today",
            "bird today?": "today",
            "bird status": "status",
            "bird help": "help",
            "what can i ask?": "help",
        }

        for text, expected in commands.items():
            for variant in (text.lower(), text.upper(), text.swapcase()):
                with self.subTest(text=variant):
                    self.assertEqual(command_kind(variant, "BiRd"), expected)

    def test_curly_apostrophe_is_supported(self) -> None:
        self.assertEqual(command_kind("Who’s Here?", "bird"), "last_seen")


if __name__ == "__main__":
    unittest.main()
