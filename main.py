"""Kavita VFS Daemon & CLI.

Bridges Calibre metadata and files to Kavita's expected directory structure:
language/type/series/series Vol. volume Ch. chapter.ext
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time

from calibre_db import CalibreDBReader
from vfs_symlink import SymlinkVFS

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("kavita-vfs")


def str_to_bool(val: str) -> bool:
    return val.strip().lower() in ("true", "1", "yes", "y", "t")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a Kavita-formatted VFS from a Calibre library."
    )
    parser.add_argument(
        "--calibre-dir",
        default=os.environ.get("CALIBRE_DIR", "/calibre"),
        help="Path to Calibre library containing metadata.db (env: CALIBRE_DIR, default: /calibre)",
    )
    parser.add_argument(
        "--vfs-dir",
        default=os.environ.get("VFS_DIR", os.environ.get("OUTPUT_DIR", "/vfs")),
        help="Target path for Kavita VFS (env: VFS_DIR, default: /vfs)",
    )
    parser.add_argument(
        "--mode",
        choices=["symlink", "hardlink", "fuse"],
        default=os.environ.get("VFS_MODE", "symlink").lower(),
        help="Operating mode: symlink, hardlink, or fuse (env: VFS_MODE, default: symlink)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.environ.get("SYNC_INTERVAL", "60")),
        help="Sync interval in seconds for daemon mode (env: SYNC_INTERVAL, default: 60)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        default=str_to_bool(os.environ.get("SYNC_ONCE", "false")),
        help="Run sync once and exit (env: SYNC_ONCE)",
    )
    parser.add_argument(
        "--relative-links",
        action="store_true",
        default=str_to_bool(os.environ.get("RELATIVE_LINKS", "false")),
        help="Use relative paths for symlinks (env: RELATIVE_LINKS, default: false)",
    )
    parser.add_argument(
        "--default-language",
        default=os.environ.get("DEFAULT_LANGUAGE", "unknown"),
        help="Fallback language when not specified in Calibre (env: DEFAULT_LANGUAGE, default: unknown)",
    )
    parser.add_argument(
        "--default-type",
        default=os.environ.get("DEFAULT_TYPE", "Unknown"),
        help="Fallback type when custom column 'type' is not set (env: DEFAULT_TYPE, default: Unknown)",
    )
    parser.add_argument(
        "--target-calibre-dir",
        default=os.environ.get("CALIBRE_TARGET_DIR", os.environ.get("SYMLINK_TARGET_PREFIX", "")),
        help="Custom target directory prefix for symlinks (e.g. host path /mnt/user/... or Kavita path) (env: CALIBRE_TARGET_DIR)",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("LOG_LEVEL", "INFO").upper(),
        help="Logging level (DEBUG, INFO, WARNING, ERROR) (env: LOG_LEVEL, default: INFO)",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    log_level = getattr(logging, args.log_level, logging.INFO)
    logging.getLogger().setLevel(log_level)

    logger.info("Starting Kavita VFS...")
    logger.info("Calibre directory: %s", args.calibre_dir)
    logger.info("VFS target directory: %s", args.vfs_dir)
    logger.info("Operating mode: %s", args.mode)

    calibre_reader = CalibreDBReader(args.calibre_dir)

    if not calibre_reader.exists():
        logger.warning(
            "Calibre metadata.db not found at %s. Waiting for database to appear...",
            calibre_reader.db_path,
        )
        if args.once:
            logger.error("Database not found and --once specified. Exiting.")
            return 1

    if args.mode == "fuse":
        from vfs_fuse import mount_fuse
        try:
            mount_fuse(
                calibre_reader=calibre_reader,
                mount_point=args.vfs_dir,
                default_language=args.default_language,
                default_type=args.default_type,
                foreground=True,
            )
            return 0
        except Exception as e:
            logger.exception("FUSE mounting failed: %s", e)
            return 1

    # Mode: symlink or hardlink
    link_type = "hardlink" if args.mode == "hardlink" else "symlink"
    syncer = SymlinkVFS(
        vfs_dir=args.vfs_dir,
        link_type=link_type,
        relative_links=args.relative_links,
        default_language=args.default_language,
        default_type=args.default_type,
        calibre_dir=args.calibre_dir,
        target_calibre_dir=args.target_calibre_dir,
    )

    stop_requested = False

    def handle_signal(sig, frame):
        nonlocal stop_requested
        logger.info("Signal received (%s). Shutting down...", sig)
        stop_requested = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    last_synced_mtime = -1.0

    while not stop_requested:
        if calibre_reader.exists():
            current_mtime = calibre_reader.get_last_modified()
            if current_mtime != last_synced_mtime:
                logger.info("Calibre database updated (or first run). Synchronizing VFS...")
                try:
                    records = calibre_reader.get_all_book_files()
                    syncer.sync(records)
                    last_synced_mtime = current_mtime
                except Exception as e:
                    logger.exception("Error during synchronization: %s", e)
            else:
                logger.debug("Database unchanged. Skipping sync.")
        else:
            logger.warning("Waiting for %s to become available...", calibre_reader.db_path)

        if args.once:
            break

        # Sleep in small slices to respond promptly to SIGTERM
        for _ in range(max(1, args.interval)):
            if stop_requested:
                break
            time.sleep(1)

    logger.info("Kavita VFS stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
