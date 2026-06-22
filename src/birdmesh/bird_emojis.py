from __future__ import annotations

import re


_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("🦉", ("owl", "owlet")),
    (
        "🦅",
        (
            "eagle",
            "hawk",
            "falcon",
            "kestrel",
            "osprey",
            "harrier",
            "kite",
            "vulture",
            "condor",
            "buzzard",
            "caracara",
            "merlin",
        ),
    ),
    ("🦢", ("swan",)),
    ("🪿", ("goose", "geese", "brant")),
    ("🦆", ("duck", "mallard", "teal", "merganser", "scaup", "eider", "goldeneye", "bufflehead", "wigeon", "shoveler", "canvasback", "pochard")),
    ("🕊️", ("dove", "pigeon")),
    ("🦃", ("turkey",)),
    ("🦜", ("parrot", "parakeet", "macaw", "cockatoo", "lorikeet")),
    ("🦚", ("peacock", "peahen", "peafowl")),
    ("🦩", ("flamingo",)),
    ("🐧", ("penguin",)),
    ("🐓", ("chicken", "rooster", "hen")),
    ("🌺", ("hummingbird",)),
    ("🌳", ("woodpecker", "flicker", "sapsucker")),
    (
        "🌊",
        (
            "gull",
            "tern",
            "albatross",
            "puffin",
            "auk",
            "murre",
            "petrel",
            "shearwater",
            "gannet",
            "booby",
            "frigatebird",
            "skua",
            "jaeger",
        ),
    ),
    ("🎾", ("heron", "egret", "crane", "stork", "ibis", "bittern", "spoonbill")),
    ("🏖️", ("sandpiper", "plover", "avocet", "oystercatcher", "curlew", "snipe", "dowitcher", "yellowlegs", "turnstone")),
    ("🪶", ("grouse", "quail", "pheasant", "ptarmigan", "partridge")),
)


def _normalize_species_name(species_name: str) -> str:
    return f" {re.sub(r'[^a-z0-9]+', ' ', species_name.casefold()).strip()} "


def species_emoji(species_name: str) -> str:
    normalized = _normalize_species_name(species_name)
    for emoji, keywords in _CATEGORY_RULES:
        if any(f" {keyword} " in normalized for keyword in keywords):
            return emoji
    return "🐦"


def is_owl(species_name: str) -> bool:
    normalized = _normalize_species_name(species_name)
    return any(f" {keyword} " in normalized for keyword in ("owl", "owlet"))
