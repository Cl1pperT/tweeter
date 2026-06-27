from __future__ import annotations

from datetime import datetime

from .bird_emojis import species_emoji
from .state import AppState


MAX_TEXT_LENGTH = 180


def format_alert(detection) -> str:
    confidence = round(detection.confidence * 100)
    emoji = species_emoji(detection.common_name)
    return _limit_text(f"{emoji} Look who's here: {detection.common_name}! ({confidence}%)")


def format_summary(state: AppState, window_minutes: int) -> str:
    species = sorted(
        state.pending_summary_species.items(),
        key=lambda item: (-int(item[1]["count"]), item[0].lower()),
    )
    base = "🦉 More bird visits:"
    if not species:
        return _limit_text(base)

    rendered: list[str] = []
    remaining = len(species)
    for name, stats in species:
        remaining -= 1
        species_text = f"{species_emoji(name)} {name} ×{int(stats['count'])}"
        candidate = ", ".join(rendered + [species_text])
        text = f"{base} {candidate}"
        if len(text) <= MAX_TEXT_LENGTH:
            rendered.append(species_text)
            continue
        suffix = f", +{remaining + 1} more"
        truncated = f"{base} {', '.join(rendered)}{suffix}" if rendered else f"{base} +{remaining + 1} more"
        return _limit_text(truncated)
    return _limit_text(f"{base} {', '.join(rendered)}")


def format_status() -> str:
    return "BirdMesh is listening and ready!"


def format_today(state: AppState, now: datetime) -> str:
    today = now.date().isoformat()
    counts = state.today_counts(today)
    species = state.today_species(today)
    visit_word = "visit" if counts["detections"] == 1 else "visits"
    base = (
        f"Today I've heard {counts['detections']} {visit_word} "
        f"from {counts['unique_species']} species"
    )
    if not species:
        return _limit_text(f"{base}.")

    rendered: list[str] = []
    for index, name in enumerate(species):
        species_text = name
        candidate = f"{base}: {', '.join(rendered + [species_text])}."
        if len(candidate) <= MAX_TEXT_LENGTH:
            rendered.append(species_text)
            continue
        remaining = len(species) - index
        suffix = f", +{remaining} more."
        if rendered:
            return _limit_text(f"{base}: {', '.join(rendered)}{suffix}")
        return _limit_text(f"{base}: +{remaining} more.")
    return _limit_text(f"{base}: {', '.join(rendered)}.")


def format_last_seen(state: AppState, now: datetime) -> str:
    if not state.last_detection_name or not state.last_detection_at:
        return "No visitors yet. Check back soon!"
    try:
        observed_at = datetime.fromisoformat(state.last_detection_at)
    except (TypeError, ValueError):
        return f"The latest visitor was {state.last_detection_name}."
    return format_species_seen(state.last_detection_name, observed_at, now)


def format_species_seen(species_name: str, observed_at: datetime, now: datetime) -> str:
    minutes = max(0, int((now - observed_at).total_seconds() // 60))
    if minutes < 1:
        return _limit_text(f"{species_name} was here just now.")
    minute_word = "minute" if minutes == 1 else "minutes"
    return _limit_text(f"{species_name} was here {minutes} {minute_word} ago.")


def format_species_not_seen(species_name: str) -> str:
    return _limit_text(f"I haven't heard {species_name} yet.")


def format_top_bird(top_bird: tuple[str, int] | None) -> str:
    if top_bird is None:
        return "No birds heard today."
    species_name, count = top_bird
    visit_word = "visit" if count == 1 else "visits"
    return _limit_text(f"Top bird today: {species_name} with {count} {visit_word}.")


def format_owls_today(species_names: list[str]) -> str:
    if not species_names:
        return "No owls heard today."
    base = "Owls today:"
    rendered: list[str] = []
    for index, name in enumerate(species_names):
        candidate = f"{base} {', '.join(rendered + [name])}."
        if len(candidate) <= MAX_TEXT_LENGTH:
            rendered.append(name)
            continue
        remaining = len(species_names) - index
        suffix = f", +{remaining} more."
        return _limit_text(f"{base} {', '.join(rendered)}{suffix}")
    return _limit_text(f"{base} {', '.join(rendered)}.")


def format_activity(detections: int, species: int) -> str:
    visit_word = "visit" if detections == 1 else "visits"
    return f"Last hour: {detections} {visit_word} from {species} species."


def format_species_list(list_name: str, species_names: list[str]) -> str:
    label = list_name.capitalize()
    if not species_names:
        return f"{label} is empty."
    return _limit_text(f"{label}: {', '.join(species_names)}.")


def format_species_list_update(
    list_name: str,
    species_name: str,
    action: str,
    changed: bool,
    moved: bool = False,
) -> str:
    if action == "add":
        if not changed and not moved:
            return _limit_text(f"{species_name} is already on the {list_name}.")
        suffix = " and removed it from the other list" if moved else ""
        return _limit_text(f"Added {species_name} to the {list_name}{suffix}.")
    if changed:
        return _limit_text(f"Removed {species_name} from the {list_name}.")
    return _limit_text(f"{species_name} is not on the {list_name}.")


def format_species_list_usage(list_name: str) -> str:
    return _limit_text(
        f"Use: bird {list_name} add <species> or bird {list_name} remove <species>."
    )


def format_unrecognized_request() -> str:
    return "Unrecognized request. Send 'bird help' for commands."


def format_help() -> str:
    return _limit_text(
        "Commands: Who's here? | birds today? | top bird today? | any owls today? | "
        "when was <species> here? | busy | status | whitelist/blacklist "
        "[add/remove <species>] | help"
    )


def _limit_text(text: str) -> str:
    return text if len(text) <= MAX_TEXT_LENGTH else text[: MAX_TEXT_LENGTH - 3] + "..."
