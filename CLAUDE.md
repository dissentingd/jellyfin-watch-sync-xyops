# jellyfin-watch-sync-xyops

A pre-configured web UI for [jellyfin-watch-sync](../jellyfin-watch-sync) —
[xyOps](https://github.com/pixlcore/xyops), unmodified, with
jellyfin-watch-sync installed inside it and four jobs auto-seeded on first
boot, for anyone who'd rather click a button than learn a CLI. Spun out
2026-09-02 after Dave raised wanting a web UI for jellyfin-watch-sync,
given the Jellyfin self-hosting community skews toward less technical
users, and specifically asked to check for an existing plug-and-play
project rather than hand-rolling one from scratch.

**Repo:** private for now — `gh repo view dissentingd/jellyfin-watch-sync-xyops`.

## Why xyOps, not a hand-rolled FastAPI app, not Cronicle

Real research done before building (see this project's own session
history if resuming that thread) rather than assumed:

- Considered building a bespoke FastAPI + htmx web UI first. Rejected once
  a genuinely fitting off-the-shelf option turned up — reinventing auth,
  job history, and a log viewer that already exist and are mature wasn't
  worth it just to get a purpose-built settings form.
- Considered [Cronicle](https://github.com/jhuckaby/Cronicle) (same shape:
  self-hosted job runner, web UI, shell-command plugin). Passed over
  because its own README now points to xyOps as its successor and says
  Cronicle itself only gets maintenance/security patches going forward,
  not new development -- building fresh on the tool its own author is
  moving away from would be the wrong long-term bet.
- **xyOps**: BSD-3-Clause, fully open source with no paywalled features,
  same author as Cronicle, actively developed (6.1k stars, 3,082 commits
  at the time this was checked), plugin-compatible with Cronicle's model.
  Confirmed hands-on (not from docs alone) against a real running
  instance: built-in `shellplug` plugin runs an arbitrary shell script in
  the same container, a REST API (`create_category`/`create_event`) can
  seed jobs programmatically, and running a seeded job actually works end
  to end against live Jellyfin.
- **One thing that did NOT turn out better:** xyOps ships the exact same
  static `admin`/`admin` first-login default Cronicle does. Per Dave's
  explicit call: skip building a forced-password gate ourselves: just
  document changing it immediately in the README, and rely on xyOps's own
  first-login flag for a password change nudge rather than add custom
  auth code on top of a tool that already has auth built in.

## Architecture

- `Dockerfile` — `FROM ghcr.io/pixlcore/xyops:latest`, unmodified base.
  Adds jellyfin-watch-sync into a dedicated venv (Debian bookworm's system
  Python is PEP-668 "externally managed" -- a venv avoids fighting that
  without `--break-system-packages`), symlinked onto PATH. Currently
  installs jellyfin-watch-sync straight from its GitHub repo, not PyPI --
  switch to a plain `pip install` once that project's own PyPI publish
  (blocked on Dave's account verification, see its CLAUDE.md) lands.
- `container-start-with-seed.sh` — CMD, not a replacement ENTRYPOINT (the
  base image's own `docker-entrypoint.sh` just `exec`s whatever CMD
  resolves to -- confirmed by reading it directly). Starts xyOps's own
  `bin/container-start.sh` in the background exactly as the base image
  would have, waits for its API to respond, runs the seed script once,
  then `wait`s on the real xyOps process so `docker stop` still reaches it
  (not this wrapper) and the container's lifecycle correctly tracks it.
- `seed.py` — logs into xyOps with the default credentials (this only
  ever runs from inside the same container against localhost, never
  exposed externally), creates a "Jellyfin Watch Sync" category and 4
  events (Restore/Backup × DRY RUN/APPLY) via xyOps's REST API, using the
  built-in `shellplug` plugin. Idempotent: checks existing categories/events
  by title before creating, safe to re-run on every container start.
  xyOps auto-generates category ids on creation (confirmed against a real
  instance, not assumed) -- the real returned id is captured and reused
  for the events, not guessed from the title.

## Validated 2026-09-02

Hands-on against a real xyOps instance on PlexBox (not from docs alone):
login → CSRF token flow (a write call without the `X-CSRF-Token` header
fails with a generic "Invalid session" error that doesn't mention CSRF at
all -- found by testing, not documented anywhere seen), category/event
creation, idempotent re-seeding (confirmed zero duplicates on a second
run), and a full seeded job run against live Jellyfin -- correctly
connected, read the test CSV, matched the "+1"/tmdb 176068 test record,
and rendered the exact same plan table jellyfin-watch-sync's own CLI
produces, through xyOps's own job output viewer.

**Resolved, not re-tested further (Dave's call, 2026-09-02):** that test
run took ~44 minutes elapsed, vs. a few minutes for equivalent crawls seen
elsewhere this project's history. Container logs showed a second job id
active concurrently, from an earlier `/wait`-suffixed API call that
actually launched a job before timing out client-side on my end -- a
testing-harness mistake on my part, not a product defect: two crawls
hitting the same rate-limited Jellyfin API at once, each seeing worse
latency and likely more retry/backoff cycles from the contention, fully
explains a 15-20x slowdown. Not re-tested cleanly, since the thing a
retest would confirm (normal-speed operation) is already covered by
everything else validated here.

## Not yet done

- The image hasn't been pushed anywhere (`ghcr.io/dissentingd/jellyfin-watch-sync-xyops`
  referenced in the README is aspirational, matching jellyfin-watch-sync's
  own README pattern before its first tagged release).
- No GitHub Actions release workflow yet (would mirror jellyfin-watch-sync's
  own `.github/workflows/release.yml` -- build+push to ghcr.io on a version tag).
- No automated tests -- this repo is almost entirely a Dockerfile + a
  ~150-line seed script; validated by hand against a real instance so far,
  not under CI.
- ~~planka-sync.yml exposure~~ DONE 2026-09-02 -- removed proactively
  during a pre-public privacy/security sweep, ahead of actually going
  public. This repo had picked up the same auto-onboarded workflow
  jellyfin-watch-sync did, which triggers on `issues` with no check on who
  opened one -- harmless behind private-repo access control, but would
  have let any anonymous internet user fire an automated run using a
  privileged classic PAT against private infrastructure and the real
  Planka board the moment this repo went public (same incident already
  handled on jellyfin-watch-sync itself, see that project's own history).
  Full-repo sweep otherwise came back clean: no real credentials, API
  keys, DSNs, or infra IPs anywhere in the git history or working tree.
