#!/bin/bash
# Wraps xyOps's own startup command rather than replacing it: starts xyOps
# exactly as the base image would have, waits for its API to actually
# respond (storage init takes a few seconds on first boot), seeds the
# Restore/Backup jobs once xyOps is up, then hands the container's
# lifecycle over to the real xyOps process -- `docker stop` still reaches
# xyOps, not this wrapper.
set -u
cd /opt/xyops

bash bin/container-start.sh &
XYOPS_PID=$!
trap 'kill -TERM "$XYOPS_PID" 2>/dev/null' TERM INT

echo "[seed] waiting for xyOps to become ready..."
ready=0
for _ in $(seq 1 60); do
    if curl -s -o /dev/null http://localhost:5522/api/user/login/v1 -X POST \
        -H 'Content-Type: application/json' -d '{}'; then
        ready=1
        break
    fi
    sleep 1
done

if [ "$ready" -eq 1 ]; then
    echo "[seed] xyOps is up, seeding Restore/Backup jobs (safe to re-run; skips what already exists)..."
    /opt/jellyfin-watch-sync/venv/bin/python3 /opt/jellyfin-watch-sync/seed.py \
        || echo "[seed] seeding failed -- xyOps itself is unaffected; see the log above for details" >&2
else
    echo "[seed] xyOps did not respond within 60s -- skipping seed this run. xyOps itself may still be starting; check 'docker logs' for its own status." >&2
fi

wait "$XYOPS_PID"
