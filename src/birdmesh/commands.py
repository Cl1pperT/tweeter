from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedCommand:
    kind: str
    argument: str | None = None


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
        "top bird today": "top_today",
        f"{prefix} top": "top_today",
        "any owls today": "owls_today",
        f"{prefix} owls": "owls_today",
        "how busy is it": "busy",
        f"{prefix} busy": "busy",
    }


def parse_command(text: str, command_prefix: str) -> ParsedCommand | None:
    cleaned = " ".join(text.strip().replace("’", "'").split())
    normalized = cleaned.lower().rstrip("?!.")
    kind = supported_commands(command_prefix).get(normalized)
    if kind:
        return ParsedCommand(kind)

    prefix = re.escape(command_prefix.strip())
    match = re.fullmatch(
        rf"(?:(?:{prefix})\s+)?when\s+was\s+(.+?)\s+here[?!.]*",
        cleaned,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    species_name = match.group(1).strip()
    return ParsedCommand("species_last_seen", species_name) if species_name else None


def command_kind(text: str, command_prefix: str) -> str | None:
    parsed = parse_command(text, command_prefix)
    return parsed.kind if parsed else None
