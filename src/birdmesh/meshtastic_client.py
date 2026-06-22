from __future__ import annotations

import logging
import queue
from typing import Any

from .commands import command_kind
from .config import Config
from .models import CommandMessage


LOGGER = logging.getLogger(__name__)


class MeshtasticClient:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.interface = None
        self.channel_index: int | None = config.channel_index
        self._commands: queue.SimpleQueue[CommandMessage] = queue.SimpleQueue()
        self._pub = None

    def connect(self) -> None:
        if self.interface is not None:
            return
        from pubsub import pub

        self._pub = pub
        if self.config.meshtastic_device:
            from meshtastic.serial_interface import SerialInterface

            self.interface = SerialInterface(devPath=self.config.meshtastic_device)
        else:
            from meshtastic.tcp_interface import TCPInterface

            self.interface = TCPInterface(
                self.config.meshtastic_host,
                portNumber=self.config.meshtastic_port,
            )
        self.channel_index = self._resolve_channel_index()
        pub.subscribe(self._on_receive_text, "meshtastic.receive.text")

    def close(self) -> None:
        if self._pub is not None:
            try:
                self._pub.unsubscribe(self._on_receive_text, "meshtastic.receive.text")
            except Exception:  # noqa: BLE001 - best effort cleanup
                pass
        if self.interface is not None:
            self.interface.close()
        self.interface = None
        self._pub = None

    def send_broadcast(self, text: str) -> None:
        self._require_ready()
        self.interface.sendText(text, channelIndex=self.channel_index, wantAck=False)

    def send_direct(self, destination: int | str, text: str) -> None:
        self._require_ready()
        self.interface.sendText(text, destinationId=destination, channelIndex=self.channel_index, wantAck=False)

    def drain_commands(self) -> list[CommandMessage]:
        drained: list[CommandMessage] = []
        while True:
            try:
                drained.append(self._commands.get_nowait())
            except queue.Empty:
                return drained

    def _require_ready(self) -> None:
        if self.interface is None or self.channel_index is None:
            raise RuntimeError("Meshtastic client is not connected")

    def _resolve_channel_index(self) -> int:
        if self.config.channel_index is not None:
            return self.config.channel_index
        if self.interface is None:
            raise RuntimeError("Meshtastic interface is not connected")
        channels = getattr(getattr(self.interface, "localNode", None), "channels", None)
        if channels is None:
            raise RuntimeError("Meshtastic channel list unavailable")
        iterable = channels.values() if isinstance(channels, dict) else channels
        for fallback_index, channel in enumerate(iterable):
            name = self._extract_channel_name(channel)
            channel_index = self._extract_channel_index(channel, fallback_index)
            if name == self.config.channel_name:
                return channel_index
        raise RuntimeError(f"Meshtastic channel '{self.config.channel_name}' not found")

    @staticmethod
    def _extract_channel_name(channel: Any) -> str | None:
        if isinstance(channel, dict):
            if "settings" in channel and isinstance(channel["settings"], dict):
                return channel["settings"].get("name")
            return channel.get("name")
        settings = getattr(channel, "settings", None)
        if settings is not None:
            name = getattr(settings, "name", None)
            if name:
                return name
        return getattr(channel, "name", None)

    @staticmethod
    def _extract_channel_index(channel: Any, fallback_index: int) -> int:
        if isinstance(channel, dict):
            return int(channel.get("index", fallback_index))
        return int(getattr(channel, "index", fallback_index))

    def _on_receive_text(self, packet, interface) -> None:
        if self.interface is None or interface is not self.interface:
            return
        if not self._is_configured_channel(packet):
            return
        text = self._extract_text(packet)
        if not text:
            return
        if self._is_from_self(packet):
            return
        if command_kind(text, self.config.command_prefix) is None:
            return
        sender = packet.get("fromId") or packet.get("from")
        if sender is None:
            LOGGER.debug("Ignoring command packet without sender: %s", packet)
            return
        self._commands.put(CommandMessage(sender=sender, text=text.strip()))

    def _is_configured_channel(self, packet: dict[str, Any]) -> bool:
        if self.channel_index is None:
            return False
        try:
            return int(packet["channel"]) == self.channel_index
        except (KeyError, TypeError, ValueError):
            return False

    def _is_from_self(self, packet: dict[str, Any]) -> bool:
        local_num = getattr(getattr(self.interface, "localNode", None), "nodeNum", None)
        my_info = getattr(self.interface, "myInfo", None)
        my_num = getattr(my_info, "my_node_num", None)
        sender = packet.get("from")
        return sender in {local_num, my_num}

    @staticmethod
    def _extract_text(packet: dict[str, Any]) -> str | None:
        if "text" in packet:
            return packet["text"]
        decoded = packet.get("decoded", {})
        if isinstance(decoded, dict):
            if "text" in decoded:
                return decoded["text"]
            data = decoded.get("data", {})
            if isinstance(data, dict):
                return data.get("text")
        return None
