from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from birdmesh.commands import ParsedCommand, command_kind, parse_command


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
            "top bird today?": "top_today",
            "bird top": "top_today",
            "any owls today?": "owls_today",
            "bird owls": "owls_today",
            "how busy is it?": "busy",
            "bird busy": "busy",
        }

        for text, expected in commands.items():
            for variant in (text.lower(), text.upper(), text.swapcase()):
                with self.subTest(text=variant):
                    self.assertEqual(command_kind(variant, "BiRd"), expected)

    def test_curly_apostrophe_is_supported(self) -> None:
        self.assertEqual(command_kind("Who’s Here?", "bird"), "last_seen")

    def test_species_lookup_preserves_common_or_scientific_name(self) -> None:
        common = parse_command("When was Great Horned Owl here?", "bird")
        scientific = parse_command("BIRD WHEN WAS Bubo virginianus HERE?", "bird")

        self.assertEqual(common, ParsedCommand("species_last_seen", "Great Horned Owl"))
        self.assertEqual(scientific, ParsedCommand("species_last_seen", "Bubo virginianus"))


if __name__ == "__main__":
    unittest.main()
