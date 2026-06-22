# BirdMesh

BirdMesh is a lightweight Python daemon that reads new detections from an existing BirdNET-Pi SQLite database and forwards compact bird updates through a serial- or TCP-connected Meshtastic radio on the `Bird Mesh` channel.

It is designed for a Raspberry Pi Zero 2 W running on solar power:
- One small process
- No web server
- No extra database
- Standard library plus the `meshtastic` package

## Features

- Polls `~/BirdNET-Pi/scripts/birds.db` for new rows in `detections`
- Sends an immediate mesh alert the first time a species appears each local day
- Batches repeat detections into periodic summary messages
- Replies directly to friendly questions and commands received over the mesh
- Persists cursor and alert state with atomic writes so restarts do not resend old detections

## Install

Clone the repo onto the Pi and install it into a virtual environment:

```bash
git clone https://github.com/Cl1pperT/tweeter.git birdmesh
cd birdmesh
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install .
```

## Configuration

BirdMesh reads config from environment variables or an optional `.env` file. Direct environment variables override file values.

Example `.env` for a Meshtastic radio connected over USB serial:

```dotenv
BIRDMESH_MESHTASTIC_DEVICE=/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0
BIRDMESH_CHANNEL_NAME=Bird Mesh
BIRDMESH_BIRDNET_DB_PATH=/home/puffin2/BirdNET-Pi/scripts/birds.db
BIRDMESH_POLL_SECONDS=15
BIRDMESH_SUMMARY_MINUTES=15
BIRDMESH_COMMAND_PREFIX=bird
BIRDMESH_TIMEZONE=America/Denver
BIRDMESH_LOG_LEVEL=INFO
```

To use a radio over TCP instead, replace `BIRDMESH_MESHTASTIC_DEVICE` with:

```dotenv
BIRDMESH_MESHTASTIC_HOST=192.168.1.50
BIRDMESH_MESHTASTIC_PORT=4403
```

Supported variables:
- `BIRDMESH_BIRDNET_DB_PATH`
- `BIRDMESH_MESHTASTIC_HOST`
- `BIRDMESH_MESHTASTIC_DEVICE`
- `BIRDMESH_MESHTASTIC_PORT`
- `BIRDMESH_CHANNEL_NAME`
- `BIRDMESH_CHANNEL_INDEX`
- `BIRDMESH_POLL_SECONDS`
- `BIRDMESH_SUMMARY_MINUTES`
- `BIRDMESH_COMMAND_PREFIX`
- `BIRDMESH_TIMEZONE`
- `BIRDMESH_LOG_LEVEL`

Notes:
- Set exactly one of `BIRDMESH_MESHTASTIC_HOST` or `BIRDMESH_MESHTASTIC_DEVICE`.
- `BIRDMESH_MESHTASTIC_PORT` defaults to `4403` and is only used for TCP connections.
- Prefer the stable `/dev/serial/by-id/...` path for USB radios; find it with `ls -l /dev/serial/by-id/`.
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

A service template is included at [`systemd/birdmesh.service`](systemd/birdmesh.service). It runs as the `puffin2` user and includes membership in the `dialout` group for USB serial access.

Typical deployment:

```bash
sudo cp -a . /opt/birdmesh
cd /opt/birdmesh
sudo -u puffin2 python3 -m venv .venv
sudo -u puffin2 .venv/bin/pip install .
sudo cp systemd/birdmesh.service /etc/systemd/system/birdmesh.service
sudo install -o root -g root -m 600 /dev/null /etc/birdmesh.env
sudoedit /etc/birdmesh.env
```

After adding the configuration values described above, enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now birdmesh.service
sudo systemctl status birdmesh.service
```

Follow its logs with:

```bash
sudo journalctl -u birdmesh.service -f
```

## Mesh Behavior

- Alert format: `🐦 Look who's here: House Finch! (92%)`
- Summary format: `🎶 More bird visits: House Finch ×5, Blue Jay ×3`
- `who's here?` replies with the most recently heard bird and how many minutes ago it visited
- `birds today?` shares today's visit and species counts
- `bird status` confirms BirdMesh is listening
- `bird help` lists the available questions
- Replies are sent directly back to the requesting node

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
