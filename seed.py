#!/usr/bin/env python3
"""Idempotently seeds xyOps with pre-built Restore/Backup jobs for
jellyfin-watch-sync, so a first-time user can log in and just click Run
instead of learning xyOps's event editor or this tool's CLI flags from
scratch. Safe to re-run on every container start: skips anything that
already exists by title, never overwrites or duplicates.

Talks to xyOps's own REST API (https://github.com/pixlcore/xyops/blob/main/docs/api.md)
using the default admin/admin credentials -- confirmed working against a
real instance before writing this, not assumed from docs alone (login
returns a session cookie + a csrf_token; every write call needs both the
cookie and that token in an X-CSRF-Token header, confirmed empirically --
omitting the header fails with a generic "Invalid session" error that
doesn't actually mention CSRF). This only ever runs from inside the same
container against localhost, never exposed externally, so the default
credential is an acceptable bootstrap step here -- the README tells the
user to change it immediately, same as xyOps's own first-login already
prompts for.
"""

from __future__ import annotations

import sys

import httpx

XYOPS_URL = "http://localhost:5522"
CATEGORY_TITLE = "Jellyfin Watch Sync"

# Every seeded script references these env vars explicitly, rather than
# relying on jellyfin-watch-sync's own envvar-bound CLI options -- so a
# user reading the script in xyOps's own event editor can see exactly what
# it expects, instead of it being invisible auto-binding.
JELLYFIN_FLAGS = (
    '--jellyfin-url "$JELLYFIN_URL" '
    '--jellyfin-api-key "$JELLYFIN_API_KEY" '
    '--jellyfin-user-id "$JELLYFIN_USER_ID"'
)
YAMTRACK_FLAGS = '--yamtrack-dsn "$YAMTRACK_DSN" --yamtrack-user-id "$YAMTRACK_USER_ID"'

EVENTS = [
    {
        "title": "Restore watch history -- DRY RUN (safe, writes nothing)",
        "notes": "Reads /data/watch-history.csv and shows what would be restored into Jellyfin. Always safe to run.",
        "script": (
            "#!/bin/sh\n"
            f"jellyfin-watch-sync restore --source-type generic-csv "
            f"--source-path /data/watch-history.csv {JELLYFIN_FLAGS}\n"
        ),
    },
    {
        "title": "Restore watch history -- APPLY (writes to Jellyfin)",
        "notes": "Actually writes the restored watch history into Jellyfin. Run the DRY RUN version first and review its output.",
        "script": (
            "#!/bin/sh\n"
            f"jellyfin-watch-sync restore --source-type generic-csv "
            f"--source-path /data/watch-history.csv {JELLYFIN_FLAGS} --apply\n"
        ),
    },
    {
        "title": "Backup watch history to YAMTrack -- DRY RUN (safe, writes nothing)",
        "notes": "Reads Jellyfin's current watch history and shows what would be written into YAMTrack. Always safe to run.",
        "script": (
            "#!/bin/sh\n"
            f"jellyfin-watch-sync backup --target-type yamtrack-db "
            f"{YAMTRACK_FLAGS} {JELLYFIN_FLAGS}\n"
        ),
    },
    {
        "title": "Backup watch history to YAMTrack -- APPLY (writes to YAMTrack)",
        "notes": "Actually writes Jellyfin's current watch history into YAMTrack. Run the DRY RUN version first and review its output.",
        "script": (
            "#!/bin/sh\n"
            f"jellyfin-watch-sync backup --target-type yamtrack-db "
            f"{YAMTRACK_FLAGS} {JELLYFIN_FLAGS} --apply\n"
        ),
    },
]


def login(client: httpx.Client) -> str:
    resp = client.post(f"{XYOPS_URL}/api/user/login/v1", json={"username": "admin", "password": "admin"})
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"xyOps login failed: {data}")
    return data["csrf_token"]


def ensure_category(client: httpx.Client, csrf: str) -> str:
    """Returns the category's id, creating it first if it doesn't exist yet.
    xyOps auto-generates category ids on creation (confirmed against a real
    instance -- creating a category titled "Test" came back with an id like
    "camtkcegdrb3trml", not anything derived from the title), so the id used
    for events below has to come from here, not be assumed."""
    resp = client.get(f"{XYOPS_URL}/api/app/get_categories/v1")
    resp.raise_for_status()
    for row in resp.json().get("rows", []):
        if row["title"] == CATEGORY_TITLE:
            print(f"[seed] category {CATEGORY_TITLE!r} already exists, skipping")
            return row["id"]

    resp = client.post(
        f"{XYOPS_URL}/api/app/create_category/v1",
        json={
            "title": CATEGORY_TITLE,
            "enabled": True,
            "notes": "Jobs for the jellyfin-watch-sync CLI, pre-seeded on first boot.",
        },
        headers={"X-CSRF-Token": csrf},
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"failed to create category: {data}")
    print(f"[seed] created category {CATEGORY_TITLE!r}")
    return data["category"]["id"]


def ensure_events(client: httpx.Client, csrf: str, category_id: str) -> None:
    resp = client.get(f"{XYOPS_URL}/api/app/get_events/v1")
    resp.raise_for_status()
    existing_titles = {row["title"] for row in resp.json().get("rows", [])}

    for event in EVENTS:
        if event["title"] in existing_titles:
            print(f"[seed] event {event['title']!r} already exists, skipping")
            continue

        payload = {
            "title": event["title"],
            "notes": event["notes"],
            "enabled": True,
            "category": category_id,
            "targets": ["main"],
            "algo": "random",
            "plugin": "shellplug",
            "params": {"script": event["script"]},
            "triggers": [{"type": "manual", "enabled": True}],
        }
        resp = client.post(f"{XYOPS_URL}/api/app/create_event/v1", json=payload, headers={"X-CSRF-Token": csrf})
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"failed to create event {event['title']!r}: {data}")
        print(f"[seed] created event {event['title']!r}")


def main() -> int:
    with httpx.Client(timeout=30.0) as client:
        csrf = login(client)
        category_id = ensure_category(client, csrf)
        ensure_events(client, csrf, category_id)
    print("[seed] done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
