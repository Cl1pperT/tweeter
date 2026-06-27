from __future__ import annotations

import logging
import time
from collections.abc import Iterable
from datetime import datetime, timedelta

from .bird_emojis import is_owl
from .birdnet import BirdNETDatabase
from .commands import parse_command
from .config import Config
from .formatting import (
    format_activity,
    format_alert,
    format_help,
    format_last_seen,
    format_owls_today,
    format_species_not_seen,
    format_species_list,
    format_species_list_update,
    format_species_list_usage,
    format_species_seen,
    format_status,
    format_summary,
    format_today,
    format_top_bird,
    format_unrecognized_request,
)
from .meshtastic_client import MeshtasticClient
from .models import CommandMessage
from .state import AppState, StateStore
from .timeutil import resolve_tzinfo


LOGGER = logging.getLogger(__name__)

SPECIES_LIST_COMMANDS = {
    "whitelist",
    "whitelist_add",
    "whitelist_remove",
    "blacklist",
    "blacklist_add",
    "blacklist_remove",
}


class ConnectivityCheckError(RuntimeError):
    """Raised when an explicit connectivity check cannot access the radio."""


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
        try:
            self.mesh.connect()
        except Exception as exc:
            if self.config.meshtastic_device:
                raise ConnectivityCheckError(
                    f"Unable to open Meshtastic serial device {self.config.meshtastic_device!r}. "
                    "If birdmesh.service is running, it owns the serial port. Run "
                    "`sudo systemctl stop birdmesh.service`, retry the check, then run "
                    "`sudo systemctl restart birdmesh.service`. For updates, use "
                    "`sudo ./scripts/update.sh`, which always restarts the service. "
                    f"Original error: {exc}"
                ) from exc
            raise
        finally:
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
        queued_commands = self.mesh.drain_commands()
        species_list_commands = []
        other_commands = []
        for command in queued_commands:
            parsed = parse_command(command.text, self.config.command_prefix)
            if parsed and parsed.kind in SPECIES_LIST_COMMANDS:
                species_list_commands.append(command)
            else:
                other_commands.append(command)
        self._handle_commands(species_list_commands)

        detections = self.db.fetch_new_detections(self.state.last_rowid)
        for detection in detections:
            day = detection.observed_at.date().isoformat()
            first_of_day = not self.state.has_alerted_species(day, detection.species_key)
            notification_tier = self.state.notification_tier(detection)
            should_alert = first_of_day or notification_tier == "whitelist"
            if should_alert:
                self.mesh.send_broadcast(format_alert(detection))
            self.state.record_detection(
                detection,
                alerted=should_alert,
                include_in_summary=notification_tier != "blacklist",
            )
            self.state_store.save(self.state)
        self._send_summary_if_due()
        self._handle_commands(other_commands)
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

    def _handle_commands(self, commands: Iterable[CommandMessage] | None = None) -> None:
        now = datetime.now(self.tzinfo)
        for command in commands if commands is not None else self.mesh.drain_commands():
            LOGGER.info("Replying to mesh command from %s: %s", command.sender, command.text)
            parsed = parse_command(command.text, self.config.command_prefix)
            if parsed is None:
                if command.is_direct:
                    self.mesh.send_direct(command.sender, format_unrecognized_request())
                continue
            kind = parsed.kind
            if kind == "last_seen":
                self._restore_last_seen_if_needed()
                response = format_last_seen(self.state, now)
            elif kind == "today":
                self._restore_today_species_if_needed(now)
                response = format_today(self.state, now)
            elif kind == "help":
                response = format_help()
            elif kind == "status":
                response = format_status()
            elif kind == "top_today":
                response = format_top_bird(self.db.fetch_top_common_name_for_day(now.date().isoformat()))
            elif kind == "owls_today":
                species_names = self.db.fetch_common_names_for_day(now.date().isoformat())
                response = format_owls_today([name for name in species_names if is_owl(name)])
            elif kind == "species_last_seen" and parsed.argument:
                detection = self.db.fetch_latest_detection_for_species(parsed.argument)
                response = (
                    format_species_seen(detection.common_name, detection.observed_at, now)
                    if detection
                    else format_species_not_seen(parsed.argument)
                )
            elif kind == "busy":
                detections, species = self.db.fetch_activity_between(now - timedelta(hours=1), now)
                response = format_activity(detections, species)
            elif kind in SPECIES_LIST_COMMANDS:
                response = self._handle_species_list_command(kind, parsed.argument)
            else:
                if command.is_direct:
                    self.mesh.send_direct(command.sender, format_unrecognized_request())
                continue
            self.mesh.send_direct(command.sender, response)

    def _handle_species_list_command(self, kind: str, argument: str | None) -> str:
        list_name, _, action = kind.partition("_")
        if not action:
            return format_species_list(list_name, self.state.listed_species(list_name))
        if not argument:
            return format_species_list_usage(list_name)

        detection = self.db.fetch_latest_detection_for_species(argument)
        canonical_name = detection.common_name if detection else " ".join(argument.split())
        if action == "add":
            species_name, added, moved = self.state.add_listed_species(list_name, canonical_name)
            removed_pending = (
                self.state.drop_pending_summary_species(species_name)
                if list_name == "blacklist"
                else 0
            )
            if added or moved or removed_pending:
                self.state_store.save(self.state)
            return format_species_list_update(
                list_name,
                species_name,
                action,
                changed=added,
                moved=moved,
            )

        removed_name = self.state.remove_listed_species(list_name, canonical_name)
        if removed_name is None and canonical_name.casefold() != argument.casefold():
            removed_name = self.state.remove_listed_species(list_name, argument)
        if removed_name is not None:
            self.state_store.save(self.state)
        return format_species_list_update(
            list_name,
            removed_name or canonical_name,
            action,
            changed=removed_name is not None,
        )

    def _restore_last_seen_if_needed(self) -> None:
        if self.state.last_detection_name:
            return
        latest = self.db.fetch_latest_detection()
        if latest is None:
            return
        self.state.last_detection_name = latest.common_name
        self.state.last_detection_at = latest.observed_at.isoformat()
        self.state_store.save(self.state)

    def _restore_today_species_if_needed(self, now: datetime) -> None:
        day = now.date().isoformat()
        counts = self.state.today_counts(day)
        if len(self.state.today_species(day)) >= counts["unique_species"]:
            return
        species_names = self.db.fetch_common_names_for_day(day)
        if not species_names:
            return
        self.state.set_today_species(day, species_names)
        self.state_store.save(self.state)
