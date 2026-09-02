# syntax=docker/dockerfile:1
#
# Layers jellyfin-watch-sync on top of the official xyOps image, unmodified
# (https://github.com/pixlcore/xyops) -- xyOps itself is never patched or
# forked here, only extended, so upstream security/feature updates just
# mean rebuilding this image against a newer base tag.
#
# xyOps's built-in "Shell Script" plugin (shellplug) runs an arbitrary shell
# script in the same container it's already running in -- that's what lets
# a plain `pip install` here be enough, with no second container, no
# Docker-socket mount, and no custom xyOps plugin to write and maintain.
FROM ghcr.io/pixlcore/xyops:latest

# Debian bookworm's system Python is "externally managed" (PEP 668) -- pip
# refuses a bare `pip install` into it. A dedicated venv, with its bin/
# symlinked onto PATH, avoids fighting that without needing
# --break-system-packages (which would risk actual system package conflicts,
# not just a refusal).
# Installed straight from GitHub for now, not PyPI -- jellyfin-watch-sync
# isn't published there yet (pending its own account verification, see its
# own CLAUDE.md). Switch this to a plain "jellyfin-watch-sync[yamtrack-db]"
# once that lands; git only needs to stay a build dependency either way.
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3-venv git \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/jellyfin-watch-sync/venv \
    && /opt/jellyfin-watch-sync/venv/bin/pip install --no-cache-dir \
        "jellyfin-watch-sync[yamtrack-db] @ git+https://github.com/dissentingd/jellyfin-watch-sync.git" \
    && ln -s /opt/jellyfin-watch-sync/venv/bin/jellyfin-watch-sync /usr/local/bin/jellyfin-watch-sync

COPY seed.py container-start-with-seed.sh /opt/jellyfin-watch-sync/
RUN chmod +x /opt/jellyfin-watch-sync/container-start-with-seed.sh

# Deliberately does NOT replace xyOps's own ENTRYPOINT (docker-entrypoint.sh
# just `exec`s whatever CMD resolves to -- confirmed by reading it directly,
# not assumed) -- only CMD, so xyOps's own startup/signal-handling path is
# untouched. The wrapper starts xyOps exactly as the base image would have,
# waits for it to come up, seeds the Restore/Backup jobs once, then forwards
# the container's lifecycle to the real xyOps process.
CMD ["/opt/jellyfin-watch-sync/container-start-with-seed.sh"]
