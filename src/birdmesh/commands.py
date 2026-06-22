from __future__ import annotations


def command_kind(text: str, command_prefix: str) -> str | None:
    normalized = " ".join(text.strip().lower().replace("’", "'").split()).rstrip("?!.")
    prefix = command_prefix.strip().lower()

    commands = {
        "who's here": "last_seen",
        "whos here": "last_seen",
        "who is here": "last_seen",
        f"{prefix} who's here": "last_seen",
        f"{prefix} who": "last_seen",
        "birds today": "today",
        "what have you seen": "today",
        f"{prefix} today": "today",
        f"{prefix} status": "status",
        f"{prefix} help": "help",
        "what can i ask": "help",
    }
    return commands.get(normalized)
