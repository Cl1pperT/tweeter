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
    return "🦉 BirdMesh is listening and ready!"


def format_today(state: AppState, now: datetime) -> str:
    today = now.date().isoformat()
    counts = state.today_counts(today)
    species = state.today_species(today)
    visit_word = "visit" if counts["detections"] == 1 else "visits"
    base = (
        f"🦉 Today I've heard {counts['detections']} {visit_word} "
        f"from {counts['unique_species']} species"
    )
    if not species:
        return _limit_text(f"{base}.")

    rendered: list[str] = []
    for index, name in enumerate(species):
        species_text = f"{species_emoji(name)} {name}"
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
        return "🦉 No visitors yet. Check back soon!"
    try:
        observed_at = datetime.fromisoformat(state.last_detection_at)
        minutes = max(0, int((now - observed_at).total_seconds() // 60))
    except (TypeError, ValueError):
        emoji = species_emoji(state.last_detection_name)
        return f"{emoji} The latest visitor was {state.last_detection_name}."
    emoji = species_emoji(state.last_detection_name)
    if minutes < 1:
        return _limit_text(f"{emoji} {state.last_detection_name} just stopped by!")
    minute_word = "minute" if minutes == 1 else "minutes"
    return _limit_text(f"{emoji} {state.last_detection_name} stopped by {minutes} {minute_word} ago!")


def format_help() -> str:
    return _limit_text("🦉 Ask me: Who's here? • Birds today? • bird status • bird help")


def _limit_text(text: str) -> str:
    return text if len(text) <= MAX_TEXT_LENGTH else text[: MAX_TEXT_LENGTH - 3] + "..."
