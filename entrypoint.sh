#!/bin/sh
set -e

PUID=${PUID:-1000}
PGID=${PGID:-1000}

# Create group if not exists
if ! getent group "$PGID" >/dev/null 2>&1; then
    groupadd -g "$PGID" vfsgroup 2>/dev/null || addgroup -g "$PGID" vfsgroup 2>/dev/null || true
fi

# Create user if not exists
if ! getent passwd "$PUID" >/dev/null 2>&1; then
    useradd -u "$PUID" -g "$PGID" -m -s /bin/sh vfsuser 2>/dev/null || adduser -u "$PUID" -G vfsgroup -D vfsuser 2>/dev/null || true
fi

# Resolve VFS directory for permission adjustment
TARGET_VFS="${VFS_DIR:-${OUTPUT_DIR:-}}"
if [ -z "$TARGET_VFS" ] && [ -n "$DATA_DIR" ]; then
    TARGET_VFS="$DATA_DIR/vfs"
fi
TARGET_VFS="${TARGET_VFS:-/vfs}"

if [ -d "$TARGET_VFS" ]; then
    chown -R "$PUID:$PGID" "$TARGET_VFS" 2>/dev/null || true
fi

# If gosu is available and running as root, drop privileges (unless in FUSE mode where root/fuse group may be required)
if [ "$(id -u)" = "0" ] && [ "$VFS_MODE" != "fuse" ] && command -v gosu >/dev/null 2>&1; then
    exec gosu "$PUID:$PGID" python3 /app/main.py "$@"
else
    exec python3 /app/main.py "$@"
fi
