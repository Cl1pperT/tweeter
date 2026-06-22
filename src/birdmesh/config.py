from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_DB_PATH = "~/BirdNET-Pi/scripts/birds.db"
DEFAULT_CHANNEL_NAME = "Bird Mesh"
DEFAULT_COMMAND_PREFIX = "bird"
DEFAULT_POLL_SECONDS = 15
DEFAULT_SUMMARY_MINUTES = 60
DEFAULT_MESHTASTIC_PORT = 4403


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip("'").strip('"')
        values[key.strip()] = value
    return values


def _get_value(env: dict[str, str], file_values: dict[str, str], key: str, default: str | None = None) -> str | None:
    return env.get(key) or file_values.get(key) or default


def _resolve_state_path() -> Path:
    root = Path(os.environ.get("XDG_STATE_HOME", "~/.local/state")).expanduser()
    return root / "birdmesh" / "state.json"


def _parse_int(name: str, value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed < 1:
        raise ValueError(f"{name} must be at least 1")
    return parsed


@dataclass(frozen=True, slots=True)
class Config:
    birdnet_db_path: Path
    meshtastic_host: str | None
    meshtastic_port: int
    channel_name: str
    channel_index: int | None
    poll_seconds: int
    summary_minutes: int
    command_prefix: str
    timezone_name: str
    log_level: str
    env_file: Path | None
    state_path: Path
    meshtastic_device: str | None = None

    @property
    def summary_interval_seconds(self) -> int:
        return self.summary_minutes * 60


def load_config(env_file: str | None = None) -> Config:
    explicit_env_file = Path(env_file).expanduser() if env_file else None
    default_env_file = Path(".env")
    file_values = _parse_env_file(explicit_env_file) if explicit_env_file else _parse_env_file(default_env_file)
    env = dict(os.environ)

    meshtastic_host = _get_value(env, file_values, "BIRDMESH_MESHTASTIC_HOST")
    meshtastic_device = _get_value(env, file_values, "BIRDMESH_MESHTASTIC_DEVICE")
    if bool(meshtastic_host) == bool(meshtastic_device):
        raise ValueError(
            "Set exactly one of BIRDMESH_MESHTASTIC_HOST or BIRDMESH_MESHTASTIC_DEVICE"
        )

    timezone_value = _get_value(env, file_values, "BIRDMESH_TIMEZONE")
    if timezone_value:
        try:
            ZoneInfo(timezone_value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown BIRDMESH_TIMEZONE: {timezone_value}") from exc
        timezone_name = timezone_value
    else:
        timezone_name = str(Path("/etc/localtime"))

    channel_index_raw = _get_value(env, file_values, "BIRDMESH_CHANNEL_INDEX")
    channel_index = int(channel_index_raw) if channel_index_raw else None

    return Config(
        birdnet_db_path=Path(_get_value(env, file_values, "BIRDMESH_BIRDNET_DB_PATH", DEFAULT_DB_PATH)).expanduser(),
        meshtastic_host=meshtastic_host,
        meshtastic_port=_parse_int(
            "BIRDMESH_MESHTASTIC_PORT",
            _get_value(env, file_values, "BIRDMESH_MESHTASTIC_PORT", str(DEFAULT_MESHTASTIC_PORT)) or str(DEFAULT_MESHTASTIC_PORT),
        ),
        meshtastic_device=meshtastic_device,
        channel_name=_get_value(env, file_values, "BIRDMESH_CHANNEL_NAME", DEFAULT_CHANNEL_NAME) or DEFAULT_CHANNEL_NAME,
        channel_index=channel_index,
        poll_seconds=_parse_int(
            "BIRDMESH_POLL_SECONDS",
            _get_value(env, file_values, "BIRDMESH_POLL_SECONDS", str(DEFAULT_POLL_SECONDS)) or str(DEFAULT_POLL_SECONDS),
        ),
        summary_minutes=_parse_int(
            "BIRDMESH_SUMMARY_MINUTES",
            _get_value(env, file_values, "BIRDMESH_SUMMARY_MINUTES", str(DEFAULT_SUMMARY_MINUTES)) or str(DEFAULT_SUMMARY_MINUTES),
        ),
        command_prefix=(_get_value(env, file_values, "BIRDMESH_COMMAND_PREFIX", DEFAULT_COMMAND_PREFIX) or DEFAULT_COMMAND_PREFIX).strip(),
        timezone_name=timezone_name,
        log_level=(_get_value(env, file_values, "BIRDMESH_LOG_LEVEL", "INFO") or "INFO").upper(),
        env_file=explicit_env_file if explicit_env_file else (default_env_file if default_env_file.exists() else None),
        state_path=_resolve_state_path(),
    )
