from __future__ import annotations

import logging
import time
from datetime import datetime

from .birdnet import BirdNETDatabase
from .commands import command_kind
from .config import Config
from .formatting import format_alert, format_help, format_last_seen, format_status, format_summary, format_today
from .meshtastic_client import MeshtasticClient
from .state import AppState, StateStore
from .timeutil import resolve_tzinfo


LOGGER = logging.getLogger(__name__)


class BirdMeshApp:
    def __init__(
        self,
        config: Config,
        state_store: StateStore | None = None,
        db: BirdNETDatabase | None = None,
        mesh: MeshtasticClient | None = None,
    ) -> None:
        self.config = config
        self.tzinfo = resolve_tzinfo(config.timezone_name)
        self.state_store = state_store or StateStore(config.state_path)
        self.db = db or BirdNETDatabase(config.birdnet_db_path, self.tzinfo)
        self.mesh = mesh or MeshtasticClient(config)
        self.state: AppState = self.state_store.load()

    def check(self) -> None:
        self.db.check()
        self.mesh.connect()
        self.mesh.close()

    def run_once(self) -> None:
        self.mesh.connect()
        self._process_cycle()

    def run_forever(self) -> None:
        backoff = 1
        while True:
            try:
                self.mesh.connect()
                self._process_cycle()
                backoff = 1
                time.sleep(self.config.poll_seconds)
            except KeyboardInterrupt:
                raise
            except Exception as exc:  # noqa: BLE001 - daemon should recover from transient failures
                LOGGER.exception("BirdMesh cycle failed: %s", exc)
                self.mesh.close()
                time.sleep(backoff)
                backoff = min(backoff * 2, 300)

    def close(self) -> None:
        self.mesh.close()

    def _process_cycle(self) -> None:
        detections = self.db.fetch_new_detections(self.state.last_rowid)
        for detection in detections:
            day = detection.observed_at.date().isoformat()
            first_of_day = not self.state.has_alerted_species(day, detection.species_key)
            if first_of_day:
                self.mesh.send_broadcast(format_alert(detection))
            self.state.record_detection(detection, alerted=first_of_day)
            self.state_store.save(self.state)
        self._send_summary_if_due()
        self._handle_commands()

    def _send_summary_if_due(self) -> None:
        if self.state.pending_summary_total < 1:
            return
        now = datetime.now(self.tzinfo)
        reference_time_raw = self.state.pending_window_started_at or self.state.last_summary_at
        if reference_time_raw:
            reference_time = datetime.fromisoformat(reference_time_raw)
            if (now - reference_time).total_seconds() < self.config.summary_interval_seconds:
                return
        self.mesh.send_broadcast(format_summary(self.state, self.config.summary_minutes))
        self.state.mark_summary_sent(now)
        self.state_store.save(self.state)

    def _handle_commands(self) -> None:
        now = datetime.now(self.tzinfo)
        for command in self.mesh.drain_commands():
            LOGGER.info("Replying to mesh command from %s: %s", command.sender, command.text)
            kind = command_kind(command.text, self.config.command_prefix)
            if kind == "last_seen":
                self._restore_last_seen_if_needed()
                response = format_last_seen(self.state, now)
            elif kind == "today":
                response = format_today(self.state, now)
            elif kind == "help":
                response = format_help()
            elif kind == "status":
                response = format_status()
            else:
                continue
            self.mesh.send_direct(command.sender, response)

    def _restore_last_seen_if_needed(self) -> None:
        if self.state.last_detection_name:
            return
        latest = self.db.fetch_latest_detection()
        if latest is None:
            return
        self.state.last_detection_name = latest.common_name
        self.state.last_detection_at = latest.observed_at.isoformat()
        self.state_store.save(self.state)
