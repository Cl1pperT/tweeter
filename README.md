# BirdMesh

BirdMesh is a lightweight Python daemon that reads new detections from an existing BirdNET-Pi SQLite database and forwards compact bird updates over Meshtastic TCP on the `Bird Mesh` channel.

It is designed for a Raspberry Pi Zero 2 W running on solar power:
- One small process
- No web server
- No extra database
- Standard library plus the `meshtastic` package

## Features

- Polls `~/BirdNET-Pi/scripts/birds.db` for new rows in `detections`
- Sends an immediate mesh alert the first time a species appears each local day
- Batches repeat detections into periodic summary messages
- Replies directly to `bird status` commands received over the mesh
- Persists cursor and alert state with atomic writes so restarts do not resend old detections

## Install

Clone the repo onto the Pi and install it into a venv:

```bash
git clone <your-repo-url> birdmesh
cd birdmesh
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install .
```

## Configuration

BirdMesh reads config from environment variables or an optional `.env` file. Direct environment variables override file values.

Example `.env`:

```dotenv
BIRDMESH_MESHTASTIC_HOST=192.168.1.50
BIRDMESH_MESHTASTIC_PORT=4403
BIRDMESH_CHANNEL_NAME=Bird Mesh
BIRDMESH_BIRDNET_DB_PATH=/home/birder/BirdNET-Pi/scripts/birds.db
BIRDMESH_POLL_SECONDS=15
BIRDMESH_SUMMARY_MINUTES=15
BIRDMESH_COMMAND_PREFIX=bird
BIRDMESH_TIMEZONE=America/Denver
BIRDMESH_LOG_LEVEL=INFO
```

Supported variables:
- `BIRDMESH_BIRDNET_DB_PATH`
- `BIRDMESH_MESHTASTIC_HOST`
- `BIRDMESH_MESHTASTIC_PORT`
- `BIRDMESH_CHANNEL_NAME`
- `BIRDMESH_CHANNEL_INDEX`
- `BIRDMESH_POLL_SECONDS`
- `BIRDMESH_SUMMARY_MINUTES`
- `BIRDMESH_COMMAND_PREFIX`
- `BIRDMESH_TIMEZONE`
- `BIRDMESH_LOG_LEVEL`

Notes:
- `BIRDMESH_MESHTASTIC_HOST` is required.
- `BIRDMESH_CHANNEL_INDEX` is optional fallback if channel lookup by name fails.
- If `BIRDMESH_TIMEZONE` is omitted, BirdMesh uses the Pi’s local timezone.

## Usage

Validate config, DB access, and Meshtastic connectivity:

```bash
birdmesh --env-file /path/to/birdmesh.env check
```

Run a single cycle:

```bash
birdmesh --env-file /path/to/birdmesh.env once
```

Run the long-lived daemon:

```bash
birdmesh --env-file /path/to/birdmesh.env run
```

## systemd

A service template is included at [systemd/birdmesh.service](/Users/cliptaylor/Desktop/Programs/tweeter/systemd/birdmesh.service).

Typical deployment:

1. Copy the repo to `/opt/birdmesh`
2. Install into a venv under `/opt/birdmesh/.venv`
3. Copy `systemd/birdmesh.service` to `/etc/systemd/system/birdmesh.service`
4. Create `/etc/birdmesh.env`
5. Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now birdmesh.service
sudo systemctl status birdmesh.service
```

## Mesh Behavior

- Alert format: `BirdMesh HH:MM Common Name 92%`
- Summary format: `BirdMesh sum 12 det/4 spp/15m: Robin x5, Jay x3, +1 more`
- Command: `bird status`
- Status reply is sent directly back to the requesting node

Routine bird broadcasts are sent with `wantAck=False` to keep airtime and power use low.

## State

BirdMesh stores state at:

```text
~/.local/state/birdmesh/state.json
```

That file keeps:
- Last processed BirdNET `rowid`
- First-of-day species already alerted
- Pending summary aggregation
- Daily counters used in status replies

## Tests

Run the test suite with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```
