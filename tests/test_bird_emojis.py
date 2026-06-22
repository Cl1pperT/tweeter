from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from birdmesh.bird_emojis import species_emoji


class BirdEmojiTests(unittest.TestCase):
    def test_species_categories_use_relevant_emojis(self) -> None:
        species = {
            "Great Horned Owl": "🦉",
            "Red-tailed Hawk": "🦅",
            "Bald Eagle": "🦅",
            "Mute Swan": "🦢",
            "Canada Goose": "🪿",
            "Mallard": "🦆",
            "Mourning Dove": "🕊️",
            "Anna's Hummingbird": "🌺",
            "Northern Flicker": "🌳",
            "Atlantic Puffin": "🌊",
            "Great Blue Heron": "🎾",
            "Spotted Sandpiper": "🏖️",
            "Ruffed Grouse": "🪶",
            "American Robin": "🐦",
        }

        for name, expected in species.items():
            with self.subTest(name=name):
                self.assertEqual(species_emoji(name), expected)

    def test_keywords_match_whole_words(self) -> None:
        self.assertEqual(species_emoji("Western Tanager"), "🐦")


if __name__ == "__main__":
    unittest.main()
