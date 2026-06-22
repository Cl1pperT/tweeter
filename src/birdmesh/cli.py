from __future__ import annotations

import argparse
import logging
import sys

from .app import BirdMeshApp, ConnectivityCheckError
from .config import load_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="birdmesh", description="BirdNET-Pi to Meshtastic bridge.")
    parser.add_argument("--env-file", help="Optional path to a .env-style config file.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run", help="Run the long-lived daemon.")
    subparsers.add_parser("once", help="Run one polling cycle and send any due messages.")
    subparsers.add_parser("check", help="Validate config, BirdNET DB access, and Meshtastic connectivity.")
    return parser


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args.env_file)
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    configure_logging(config.log_level)
    app = BirdMeshApp(config)
    try:
        if args.command == "check":
            app.check()
            print("BirdMesh check OK")
            return 0
        if args.command == "once":
            app.run_once()
            return 0
        app.run_forever()
        return 0
    except KeyboardInterrupt:
        return 130
    except ConnectivityCheckError as exc:
        logging.getLogger(__name__).error("BirdMesh check failed: %s", exc)
        return 1
    except Exception as exc:  # noqa: BLE001 - top-level CLI should exit non-zero on fatal error
        logging.getLogger(__name__).exception("BirdMesh failed: %s", exc)
        return 1
    finally:
        app.close()


if __name__ == "__main__":
    sys.exit(main())
