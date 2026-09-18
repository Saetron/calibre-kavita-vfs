"""Symlink and Hardlink VFS generator for Kavita.

Synchronizes a target directory with the structure expected by Kavita:
language/type/series/series Vol. volume Ch. chapter.ext
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Set, Tuple

from calibre_db import BookFileRecord
from formatter import build_vfs_relpath

logger = logging.getLogger(__name__)


class SymlinkVFS:
    def __init__(
        self,
        vfs_dir: str,
        link_type: str = "symlink",  # "symlink" or "hardlink"
        relative_links: bool = False,
        default_language: str = "unknown",
        default_type: str = "Unknown",
        calibre_dir: str = "/calibre",
        target_calibre_dir: Optional[str] = None,
    ):
        self.vfs_dir = os.path.abspath(vfs_dir)
        self.link_type = link_type.lower()
        self.relative_links = relative_links
        self.default_language = default_language
        self.default_type = default_type
        self.calibre_dir = os.path.abspath(calibre_dir)
        self.target_calibre_dir = target_calibre_dir.strip() if target_calibre_dir else None

        self.last_collisions: List[Dict[str, Any]] = []

        if self.link_type not in ("symlink", "hardlink"):
            raise ValueError(f"Unsupported link_type: {link_type}. Must be 'symlink' or 'hardlink'")

    def build_desired_tree(
        self, records: List[BookFileRecord]
    ) -> Dict[str, str]:
        """Map absolute target file paths in VFS to source file paths in Calibre.

        Handles collisions by suffixing duplicate index if multiple files map to the same path.
        """
        self.last_collisions = []
        desired: Dict[str, str] = {}
        # Keep track of paths to detect and resolve collisions
        used_relpaths: Dict[str, Dict[str, Any]] = {}

        for rec in records:
            _, ext = os.path.splitext(rec.source_path)
            relpath = build_vfs_relpath(
                language=rec.language,
                type_=rec.type_,
                series=rec.series,
                volume=rec.volume,
                chapter=rec.chapter,
                calibre_id=rec.book_id,
                extension=ext,
                title=rec.title,
                default_language=self.default_language,
                default_type=self.default_type,
            )

            # Check for collision
            if relpath in used_relpaths:
                prior = used_relpaths[relpath]
                base, dot_ext = os.path.splitext(relpath)
                disambiguated = f"{base}_collision_{len(self.last_collisions) + 1}{dot_ext}"
                collision_info = {
                    "relpath": relpath,
                    "existing_book_id": prior["book_id"],
                    "existing_source": prior["source_path"],
                    "colliding_book_id": rec.book_id,
                    "colliding_source": rec.source_path,
                    "resolved_path": disambiguated,
                }
                self.last_collisions.append(collision_info)
                logger.warning(
                    "Collision detected for path '%s'! Books #%s and #%s. Resolved to '%s'",
                    relpath,
                    prior["book_id"],
                    rec.book_id,
                    disambiguated,
                )
                relpath = disambiguated

            used_relpaths[relpath] = {"book_id": rec.book_id, "source_path": rec.source_path}
            target_path = os.path.join(self.vfs_dir, relpath)
            desired[target_path] = rec.source_path

        return desired

    def sync(self, records: List[BookFileRecord]) -> Tuple[int, int, int]:
        """Synchronize the VFS directory with current Calibre records.

        Returns a tuple: (created_count, updated_count, deleted_count).
        """
        os.makedirs(self.vfs_dir, exist_ok=True)
        desired_map = self.build_desired_tree(records)

        existing_links: Dict[str, str] = {}
        for root, dirs, files in os.walk(self.vfs_dir):
            for file in files:
                target_path = os.path.join(root, file)
                if os.path.islink(target_path):
                    existing_links[target_path] = os.readlink(target_path)
                elif os.path.isfile(target_path):
                    existing_links[target_path] = "file"

        created_count = 0
        updated_count = 0
        deleted_count = 0

        # Remove stale links or files that are no longer in desired_map
        for existing_path in existing_links:
            if existing_path not in desired_map:
                try:
                    os.unlink(existing_path)
                    deleted_count += 1
                    logger.debug("Removed stale link: %s", existing_path)
                except OSError as e:
                    logger.warning("Failed to remove stale link %s: %s", existing_path, e)

        # Create or update links
        for target_path, source_path in desired_map.items():
            parent_dir = os.path.dirname(target_path)
            os.makedirs(parent_dir, exist_ok=True)

            target_source = source_path
            if self.link_type == "symlink":
                if self.target_calibre_dir:
                    rel_to_calibre = os.path.relpath(source_path, self.calibre_dir)
                    target_source = os.path.join(self.target_calibre_dir, rel_to_calibre)
                elif self.relative_links:
                    target_source = os.path.relpath(source_path, parent_dir)

            needs_create = True
            if self.link_type == "symlink":
                if os.path.islink(target_path):
                    current_link = os.readlink(target_path)
                    if current_link == target_source:
                        needs_create = False
                    else:
                        try:
                            os.unlink(target_path)
                            updated_count += 1
                        except OSError as e:
                            logger.warning("Failed to remove link for update %s: %s", target_path, e)
                elif os.path.exists(target_path):
                    # File exists but is not a symlink (e.g. was a hardlink); remove to recreate as symlink
                    try:
                        os.unlink(target_path)
                        updated_count += 1
                    except OSError as e:
                        logger.warning("Failed to remove non-symlink file for symlink update %s: %s", target_path, e)
            else:
                # self.link_type == "hardlink"
                if os.path.islink(target_path):
                    # It is a symlink; remove to recreate as hardlink
                    try:
                        os.unlink(target_path)
                        updated_count += 1
                    except OSError as e:
                        logger.warning("Failed to remove symlink for hardlink update %s: %s", target_path, e)
                elif os.path.exists(target_path):
                    try:
                        if os.stat(target_path).st_ino == os.stat(source_path).st_ino:
                            needs_create = False
                    except OSError:
                        pass
                    if needs_create:
                        try:
                            os.unlink(target_path)
                            updated_count += 1
                        except OSError as e:
                            logger.warning("Failed to remove stale file for hardlink update %s: %s", target_path, e)

            if needs_create:
                try:
                    if self.link_type == "symlink":
                        os.symlink(target_source, target_path)
                    else:
                        os.link(source_path, target_path)
                    created_count += 1
                    logger.debug("Linked: %s -> %s", target_path, target_source)
                except OSError as e:
                    import errno
                    if self.link_type == "hardlink" and e.errno == errno.EXDEV:
                        logger.error(
                            "Cannot create hardlink across different filesystems/mounts (%s -> %s). "
                            "Ensure both /calibre and /vfs are on the same filesystem/disk, or use VFS_MODE=symlink.",
                            source_path, target_path
                        )
                    else:
                        logger.error("Failed to create %s %s -> %s: %s", self.link_type, target_path, target_source, e)

        # Clean up empty directories
        self._prune_empty_dirs(self.vfs_dir)

        logger.info(
            "Sync complete. Created: %d, Updated: %d, Deleted: %d (Total in VFS: %d)",
            created_count,
            updated_count,
            deleted_count,
            len(desired_map),
        )
        return created_count, updated_count, deleted_count

    def cleanup_unregistered(self, records: List[BookFileRecord]) -> Dict[str, Any]:
        """Scan VFS directory and remove any file, symlink, or broken link not in desired_map.

        Also cleans empty directories and ensures all links match current mode.
        """
        os.makedirs(self.vfs_dir, exist_ok=True)
        desired_map = self.build_desired_tree(records)
        removed_files = []

        for root, dirs, files in os.walk(self.vfs_dir):
            for file in files:
                target_path = os.path.join(root, file)
                if target_path not in desired_map:
                    try:
                        is_link = os.path.islink(target_path)
                        os.unlink(target_path)
                        rel = os.path.relpath(target_path, self.vfs_dir)
                        removed_files.append({"path": rel, "is_symlink": is_link})
                        logger.info("Cleaned up unregistered file: %s (symlink=%s)", rel, is_link)
                    except OSError as e:
                        logger.warning("Failed to remove unregistered file %s: %s", target_path, e)

        empty_dirs_removed = self._prune_empty_dirs(self.vfs_dir)

        # Run sync to guarantee mode conversion (e.g. symlinks -> hardlinks)
        created, updated, deleted = self.sync(records)

        return {
            "removed_files": removed_files,
            "removed_count": len(removed_files),
            "empty_dirs_removed": empty_dirs_removed,
            "sync_created": created,
            "sync_updated": updated,
            "sync_deleted": deleted,
        }

    def _prune_empty_dirs(self, root_dir: str) -> int:
        """Recursively remove empty directories. Returns count of removed directories."""
        removed = 0
        for root, dirs, files in os.walk(root_dir, topdown=False):
            if root == root_dir:
                continue
            if not os.listdir(root):
                try:
                    os.rmdir(root)
                    removed += 1
                    logger.debug("Removed empty directory: %s", root)
                except OSError:
                    pass
        return removed
