# jellyfin-watch-sync-xyops

A full web UI for [jellyfin-watch-sync](https://github.com/dissentingd/jellyfin-watch-sync),
for anyone who'd rather click a button in a browser than learn a CLI's
flags. One Docker container: [xyOps](https://github.com/pixlcore/xyops)
(a self-hosted job-runner with a web UI, login, and job history built in)
with jellyfin-watch-sync installed inside it, pre-configured with four
ready-to-click jobs the moment it starts up.

Neither xyOps nor jellyfin-watch-sync is modified to build this — xyOps
runs completely unmodified (its own official image,
`ghcr.io/pixlcore/xyops`, is the base), and jellyfin-watch-sync is
installed the normal way inside it. This repo is only the glue: a small
script that pre-creates the jobs so there's nothing to configure by hand
before you can use it.

## Quick start

```bash
docker run --detach --name jellyfin-watch-sync-xyops \
  -e XYOPS_masters=jellyfin-watch-sync-xyops \
  -e XYOPS_xysat_local=true \
  -e XYOPS_base_app_url=http://localhost:5522 \
  -e JELLYFIN_URL=https://jellyfin.example.com \
  -e JELLYFIN_API_KEY=your-api-key-here \
  -e JELLYFIN_USER_ID=your-user-guid-here \
  -v jellyfin-watch-sync-xyops-data:/opt/xyops/data \
  -v ./data:/data \
  -p 5522:5522 \
  ghcr.io/dissentingd/jellyfin-watch-sync-xyops:latest
```

(See jellyfin-watch-sync's own README for [how to find your Jellyfin URL,
API key, and user ID](https://github.com/dissentingd/jellyfin-watch-sync#getting-your-jellyfin-credentials)
if you don't have them yet.)

Then open `http://localhost:5522` in a browser.

## ⚠️ First login: change the default password immediately

The first time you log in, use:

- **Username:** `admin`
- **Password:** `admin`

**Change this password right away** — click your username in the top
corner → account settings → change password. This is xyOps's own default,
not something specific to this image, and xyOps itself will flag the
account as needing a new password on first login. Until you change it,
anyone who can reach port 5522 can log in with this same well-known
password — don't expose this port to the internet before changing it.

## What's already set up for you

On first boot, four jobs are automatically created under a "Jellyfin
Watch Sync" category — nothing to configure, just open them and click
**Run**:

| Job | What it does |
|---|---|
| Restore watch history — DRY RUN | Shows what *would* be restored into Jellyfin from `/data/watch-history.csv`. Writes nothing. Always safe to run. |
| Restore watch history — APPLY | Actually writes it. Run the DRY RUN version first and check its output. |
| Backup watch history to YAMTrack — DRY RUN | Shows what *would* be written into YAMTrack from Jellyfin's current watch history. Writes nothing. |
| Backup watch history to YAMTrack — APPLY | Actually writes it. Run the DRY RUN version first. |

This mirrors jellyfin-watch-sync's own safety model exactly: nothing is
ever written without a separate, explicit "apply" step.

**For the restore jobs:** put your watch-history CSV at `./data/watch-history.csv`
on the host (mounted to `/data/watch-history.csv` above) — see
jellyfin-watch-sync's README for the [generic CSV format](https://github.com/dissentingd/jellyfin-watch-sync#where-restore-can-read-watch-history-from)
if you're building one by hand or exporting it from somewhere else.

**For the YAMTrack backup jobs:** also set `YAMTRACK_DSN` and
`YAMTRACK_USER_ID` as environment variables when starting the container
(same env vars jellyfin-watch-sync's own CLI uses).

Re-running the container doesn't duplicate these jobs — the seed step
checks what already exists first and only adds what's missing, so editing
or deleting one of the pre-built jobs sticks.

## Persisting your data

Without the `-v jellyfin-watch-sync-xyops-data:/opt/xyops/data` volume
shown above, xyOps's own state (your changed password, edited jobs, run
history) is lost every time the container is recreated — for example, on
an image update. Keep that mount.

## Building the image yourself

A published image is planned at `ghcr.io/dissentingd/jellyfin-watch-sync-xyops`
once this repo has its first tagged release; for now:

```bash
git clone https://github.com/dissentingd/jellyfin-watch-sync-xyops
cd jellyfin-watch-sync-xyops
docker build -t jellyfin-watch-sync-xyops .
```

## How the pre-seeding works

xyOps ships a built-in "Shell Script" plugin (`shellplug`) that runs an
arbitrary script inside the same container — that's what a "job" here
actually is under the hood, no custom xyOps plugin needed. `seed.py` runs
once at container startup (after waiting for xyOps's own API to come up),
logs in with the default credentials, and calls xyOps's REST API
(`create_category`/`create_event`) to create the four jobs above if they
don't already exist. See that file's own comments for the exact
login/CSRF mechanics, confirmed against a real running instance before
being written.

## Status

Early stage — built and confirmed working end-to-end against a real
Jellyfin server (the seeded jobs correctly ran jellyfin-watch-sync,
connected to Jellyfin, and produced the expected result), but not yet
tested at real scale or hardened for untrusted/multi-user exposure. Treat
this as new, not battle-tested.

## License

MIT for the glue code in this repo (`seed.py`, `container-start-with-seed.sh`,
`Dockerfile`). xyOps itself is [BSD-3-Clause](https://github.com/pixlcore/xyops/blob/main/LICENSE),
included here only as an unmodified base image, not vendored source.
jellyfin-watch-sync is [MIT](https://github.com/dissentingd/jellyfin-watch-sync/blob/main/LICENSE).
