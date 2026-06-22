from __future__ import annotations

from datetime import datetime

from .state import AppState


MAX_TEXT_LENGTH = 180


def format_alert(detection) -> str:
    confidence = round(detection.confidence * 100)
    return _limit_text(f"🐦 Look who's here: {detection.common_name}! ({confidence}%)")


def format_summary(state: AppState, window_minutes: int) -> str:
    species = sorted(
        state.pending_summary_species.items(),
        key=lambda item: (-int(item[1]["count"]), item[0].lower()),
    )
    base = "🎶 More bird visits:"
    if not species:
        return _limit_text(base)

    rendered: list[str] = []
    remaining = len(species)
    for name, stats in species:
        remaining -= 1
        candidate = ", ".join(rendered + [f"{name} ×{int(stats['count'])}"])
        text = f"{base} {candidate}"
        if len(text) <= MAX_TEXT_LENGTH:
            rendered.append(f"{name} ×{int(stats['count'])}")
            continue
        suffix = f", +{remaining + 1} more"
        truncated = f"{base} {', '.join(rendered)}{suffix}" if rendered else f"{base} +{remaining + 1} more"
        return _limit_text(truncated)
    return _limit_text(f"{base} {', '.join(rendered)}")


def format_status() -> str:
    return "🐦 BirdMesh is listening and ready!"


def format_today(state: AppState, now: datetime) -> str:
    today = now.date().isoformat()
    counts = state.today_counts(today)
    visit_word = "visit" if counts["detections"] == 1 else "visits"
    return _limit_text(
        f"🐦 Today I've heard {counts['detections']} {visit_word} "
        f"from {counts['unique_species']} species."
    )


def format_last_seen(state: AppState, now: datetime) -> str:
    if not state.last_detection_name or not state.last_detection_at:
        return "🐦 No visitors yet. Check back soon!"
    try:
        observed_at = datetime.fromisoformat(state.last_detection_at)
        minutes = max(0, int((now - observed_at).total_seconds() // 60))
    except (TypeError, ValueError):
        return f"🐦 The latest visitor was {state.last_detection_name}."
    if minutes < 1:
        return _limit_text(f"🐦 {state.last_detection_name} just stopped by!")
    minute_word = "minute" if minutes == 1 else "minutes"
    return _limit_text(f"🐦 {state.last_detection_name} stopped by {minutes} {minute_word} ago!")


def format_help() -> str:
    return _limit_text("🐦 Ask me: Who's here? • Birds today? • bird status • bird help")


def _limit_text(text: str) -> str:
    return text if len(text) <= MAX_TEXT_LENGTH else text[: MAX_TEXT_LENGTH - 3] + "..."
