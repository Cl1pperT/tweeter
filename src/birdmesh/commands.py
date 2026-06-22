from __future__ import annotations


def supported_commands(command_prefix: str) -> dict[str, str]:
    prefix = command_prefix.strip().lower()
    return {
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


def command_kind(text: str, command_prefix: str) -> str | None:
    normalized = " ".join(text.strip().lower().replace("’", "'").split()).rstrip("?!.")
    return supported_commands(command_prefix).get(normalized)
