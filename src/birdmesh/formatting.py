from __future__ import annotations

from datetime import datetime

from .state import AppState


MAX_TEXT_LENGTH = 180


def format_alert(detection) -> str:
    return _limit_text(
        f"BirdMesh {detection.observed_at.strftime('%H:%M')} {detection.common_name} {round(detection.confidence * 100):d}%"
    )


def format_summary(state: AppState, window_minutes: int) -> str:
    species = sorted(
        state.pending_summary_species.items(),
        key=lambda item: (-int(item[1]["count"]), item[0].lower()),
    )
    base = f"BirdMesh sum {state.pending_summary_total} det/{len(species)} spp/{window_minutes}m:"
    if not species:
        return _limit_text(base)

    rendered: list[str] = []
    remaining = len(species)
    for name, stats in species:
        remaining -= 1
        candidate = ", ".join(rendered + [f"{name} x{int(stats['count'])}"])
        text = f"{base} {candidate}"
        if len(text) <= MAX_TEXT_LENGTH:
            rendered.append(f"{name} x{int(stats['count'])}")
            continue
        suffix = f", +{remaining + 1} more"
        truncated = f"{base} {', '.join(rendered)}{suffix}" if rendered else f"{base} +{remaining + 1} more"
        return _limit_text(truncated)
    return _limit_text(f"{base} {', '.join(rendered)}")


def format_status(state: AppState, now: datetime, db_ok: bool, mesh_ok: bool) -> str:
    today = now.date().isoformat()
    counts = state.today_counts(today)
    last = state.last_detection_at
    if last:
        try:
            last = datetime.fromisoformat(last).strftime("%H:%M")
        except ValueError:
            pass
    else:
        last = "none"
    return _limit_text(
        " ".join(
            [
                "birdmesh",
                "ok",
                f"db={'ok' if db_ok else 'err'}",
                f"mesh={'ok' if mesh_ok else 'err'}",
                f"last={last}",
                f"today={counts['detections']}det/{counts['unique_species']}spp",
                f"alerts={counts['alerts']}",
                f"sum={counts['summaries']}",
            ]
        )
    )


def _limit_text(text: str) -> str:
    return text if len(text) <= MAX_TEXT_LENGTH else text[: MAX_TEXT_LENGTH - 3] + "..."
