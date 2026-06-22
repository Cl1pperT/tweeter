from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from birdmesh.app import BirdMeshApp, ConnectivityCheckError
from birdmesh.birdnet import BirdNETDatabase
from birdmesh.config import Config
from birdmesh.meshtastic_client import MeshtasticClient
from birdmesh.models import CommandMessage
from birdmesh.state import AppState, StateStore


SCHEMA = """
CREATE TABLE detections (
    Date TEXT,
    Time TEXT,
    Sci_Name TEXT,
    Com_Name TEXT,
    Confidence REAL,
    Lat REAL,
    Lon REAL,
    Cutoff REAL,
    Week INTEGER,
    Sens REAL,
    Overlap REAL,
    File_Name TEXT
)
"""


class FakeMeshClient:
    def __init__(self) -> None:
        self.interface = None
        self.broadcasts: list[str] = []
        self.direct_messages: list[tuple[int | str, str]] = []
        self._commands: list[CommandMessage] = []

    def connect(self) -> None:
        self.interface = object()

    def close(self) -> None:
        self.interface = None

    def send_broadcast(self, text: str) -> None:
        self.broadcasts.append(text)

    def send_direct(self, destination: int | str, text: str) -> None:
        self.direct_messages.append((destination, text))

    def drain_commands(self) -> list[CommandMessage]:
        commands = list(self._commands)
        self._commands.clear()
        return commands


class FailingMeshClient(FakeMeshClient):
    def connect(self) -> None:
        raise OSError("device or resource busy")


class AppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_root = Path(self.temp_dir.name)
        self.db_path = temp_root / "birds.db"
        self.state_path = temp_root / "state.json"
        connection = sqlite3.connect(self.db_path)
        connection.execute(SCHEMA)
        connection.commit()
        connection.close()
        self.config = Config(
            birdnet_db_path=self.db_path,
            meshtastic_host="127.0.0.1",
            meshtastic_port=4403,
            channel_name="Bird Mesh",
            channel_index=None,
            poll_seconds=15,
            summary_minutes=60,
            command_prefix="bird",
            timezone_name="UTC",
            log_level="INFO",
            env_file=None,
            state_path=self.state_path,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _insert_detection(self, when: datetime, sci_name: str, common_name: str, confidence: float) -> None:
        connection = sqlite3.connect(self.db_path)
        connection.execute(
            """
            INSERT INTO detections
            (Date, Time, Sci_Name, Com_Name, Confidence, Lat, Lon, Cutoff, Week, Sens, Overlap, File_Name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                when.strftime("%Y-%m-%d"),
                when.strftime("%H:%M:%S"),
                sci_name,
                common_name,
                confidence,
                0,
                0,
                0,
                14,
                1,
                0,
                "clip.wav",
            ),
        )
        connection.commit()
        connection.close()

    def test_run_once_sends_first_of_day_alerts_and_persists_cursor(self) -> None:
        now = datetime.now(timezone.utc)
        self._insert_detection(now - timedelta(minutes=2), "Turdus migratorius", "American Robin", 0.91)
        self._insert_detection(now - timedelta(minutes=1), "Turdus migratorius", "American Robin", 0.88)
        self._insert_detection(now - timedelta(seconds=30), "Cyanocitta stelleri", "Steller's Jay", 0.87)

        mesh = FakeMeshClient()
        app = BirdMeshApp(
            self.config,
            state_store=StateStore(self.state_path),
            db=BirdNETDatabase(self.db_path, timezone.utc),
            mesh=mesh,
        )

        app.run_once()
        app.close()

        self.assertEqual(len(mesh.broadcasts), 2)
        self.assertEqual(mesh.broadcasts[0], "🦉 Look who's here: American Robin! (91%)")
        saved_state = StateStore(self.state_path).load()
        today = now.date().isoformat()
        self.assertEqual(saved_state.today_species(today), ["American Robin", "Steller's Jay"])

        reloaded_mesh = FakeMeshClient()
        reloaded = BirdMeshApp(
            self.config,
            state_store=StateStore(self.state_path),
            db=BirdNETDatabase(self.db_path, timezone.utc),
            mesh=reloaded_mesh,
        )
        reloaded.run_once()
        reloaded.close()
        self.assertEqual(reloaded_mesh.broadcasts, [])

    def test_due_summary_is_sent_for_pending_repeats(self) -> None:
        state = AppState(
            last_rowid=3,
            pending_summary_total=2,
            pending_summary_species={"American Robin": {"count": 2, "max_confidence": 0.9}},
            pending_window_started_at=(datetime.now(timezone.utc) - timedelta(minutes=61)).isoformat(),
        )
        StateStore(self.state_path).save(state)
        mesh = FakeMeshClient()
        app = BirdMeshApp(
            self.config,
            state_store=StateStore(self.state_path),
            db=BirdNETDatabase(self.db_path, timezone.utc),
            mesh=mesh,
        )

        app.run_once()
        app.close()

        self.assertEqual(len(mesh.broadcasts), 1)
        self.assertEqual(mesh.broadcasts[0], "🦉 More bird visits: American Robin ×2")

    def test_status_command_replies_directly(self) -> None:
        mesh = FakeMeshClient()
        mesh._commands.append(CommandMessage(sender=1234, text="bird status"))
        app = BirdMeshApp(
            self.config,
            state_store=StateStore(self.state_path),
            db=BirdNETDatabase(self.db_path, timezone.utc),
            mesh=mesh,
        )

        app.run_once()
        app.close()

        self.assertEqual(len(mesh.direct_messages), 1)
        self.assertEqual(mesh.direct_messages[0][0], 1234)
        self.assertEqual(mesh.direct_messages[0][1], "🦉 BirdMesh is listening and ready!")

    def test_whos_here_replies_with_latest_bird_and_elapsed_minutes(self) -> None:
        self._insert_detection(
            datetime.now(timezone.utc) - timedelta(minutes=5),
            "Haemorhous mexicanus",
            "House Finch",
            0.92,
        )
        mesh = FakeMeshClient()
        mesh._commands.append(CommandMessage(sender=1234, text="Who's here?"))
        app = BirdMeshApp(
            self.config,
            state_store=StateStore(self.state_path),
            db=BirdNETDatabase(self.db_path, timezone.utc),
            mesh=mesh,
        )

        app.run_once()
        app.close()

        self.assertEqual(mesh.direct_messages, [(1234, "🦉 House Finch stopped by 5 minutes ago!")])
        reloaded = StateStore(self.state_path).load()
        self.assertEqual(reloaded.last_detection_name, "House Finch")

    def test_whos_here_restores_latest_bird_for_existing_state(self) -> None:
        observed_at = datetime.now(timezone.utc) - timedelta(minutes=3)
        self._insert_detection(observed_at, "Turdus migratorius", "American Robin", 0.91)
        StateStore(self.state_path).save(AppState(last_rowid=1, last_detection_at=observed_at.isoformat()))
        mesh = FakeMeshClient()
        mesh._commands.append(CommandMessage(sender=1234, text="who's here?"))
        app = BirdMeshApp(
            self.config,
            state_store=StateStore(self.state_path),
            db=BirdNETDatabase(self.db_path, timezone.utc),
            mesh=mesh,
        )

        app.run_once()
        app.close()

        self.assertEqual(mesh.direct_messages, [(1234, "🦉 American Robin stopped by 3 minutes ago!")])

    def test_interactive_commands_are_recognized_from_mesh_text(self) -> None:
        client = MeshtasticClient(self.config)
        interface = SimpleNamespace(localNode=SimpleNamespace(nodeNum=99))
        client.interface = interface
        client.channel_index = 2

        mixed_case_commands = ("wHo'S HeRe?", "BIRDS TODAY?", "BiRd HeLp", "BIRD STATUS")
        for index, text in enumerate(mixed_case_commands, start=1):
            client._on_receive_text({"from": index, "channel": 2, "decoded": {"text": text}}, interface)

        commands = client.drain_commands()
        self.assertEqual([command.text for command in commands], list(mixed_case_commands))

    def test_group_commands_are_filtered_to_configured_channel(self) -> None:
        client = MeshtasticClient(self.config)
        interface = SimpleNamespace(localNode=SimpleNamespace(nodeNum=99))
        client.interface = interface
        client.channel_index = 2

        client._on_receive_text({"from": 1, "channel": 1, "decoded": {"text": "bird status"}}, interface)
        client._on_receive_text({"from": 2, "decoded": {"text": "bird status"}}, interface)
        client._on_receive_text({"from": 3, "channel": 2, "decoded": {"text": "bird status"}}, interface)

        commands = client.drain_commands()
        self.assertEqual([(command.sender, command.text) for command in commands], [(3, "bird status")])

    def test_direct_commands_are_accepted_from_any_channel(self) -> None:
        client = MeshtasticClient(self.config)
        interface = SimpleNamespace(localNode=SimpleNamespace(nodeNum=99))
        client.interface = interface
        client.channel_index = 2

        client._on_receive_text(
            {"from": 1, "to": 99, "channel": 1, "decoded": {"text": "bird status"}},
            interface,
        )
        client._on_receive_text(
            {"from": 2, "toId": "!00000063", "decoded": {"text": "birds today?"}},
            interface,
        )
        client._on_receive_text(
            {"from": 3, "to": 100, "channel": 1, "decoded": {"text": "bird help"}},
            interface,
        )

        commands = client.drain_commands()
        self.assertEqual(
            [(command.sender, command.text) for command in commands],
            [(1, "bird status"), (2, "birds today?")],
        )

    def test_serial_check_explains_service_port_conflict(self) -> None:
        config = replace(
            self.config,
            meshtastic_host=None,
            meshtastic_device="/dev/ttyUSB0",
        )
        app = BirdMeshApp(
            config,
            state_store=StateStore(self.state_path),
            db=BirdNETDatabase(self.db_path, timezone.utc),
            mesh=FailingMeshClient(),
        )

        with self.assertRaises(ConnectivityCheckError) as raised:
            app.check()

        self.assertIn("owns the serial port", str(raised.exception))
        self.assertIn("sudo systemctl stop birdmesh.service", str(raised.exception))
        self.assertIn("sudo systemctl restart birdmesh.service", str(raised.exception))

    def test_channel_resolution_uses_name_then_fallback_index(self) -> None:
        client = MeshtasticClient(self.config)
        client.interface = SimpleNamespace(
            localNode=SimpleNamespace(
                channels=[
                    {"index": 0, "settings": {"name": "Primary"}},
                    {"index": 2, "settings": {"name": "Bird Mesh"}},
                ]
            )
        )
        self.assertEqual(client._resolve_channel_index(), 2)

        with_index = replace(self.config, channel_index=7)
        direct_client = MeshtasticClient(with_index)
        direct_client.interface = client.interface
        self.assertEqual(direct_client._resolve_channel_index(), 7)


if __name__ == "__main__":
    unittest.main()
