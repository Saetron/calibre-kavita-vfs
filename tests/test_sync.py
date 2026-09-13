import os
import tempfile
import unittest

from calibre_db import BookFileRecord
from vfs_symlink import SymlinkVFS


class TestSync(unittest.TestCase):
    def setUp(self):
        self.temp_calibre = tempfile.TemporaryDirectory()
        self.temp_vfs = tempfile.TemporaryDirectory()

        # Create source mock files
        self.source1 = os.path.join(self.temp_calibre.name, "book1.cbz")
        with open(self.source1, "w") as f:
            f.write("content 1")

        self.source2 = os.path.join(self.temp_calibre.name, "book2.cbz")
        with open(self.source2, "w") as f:
            f.write("content 2")

    def tearDown(self):
        self.temp_calibre.cleanup()
        self.temp_vfs.cleanup()

    def test_sync_creation_and_pruning(self):
        vfs = SymlinkVFS(
            vfs_dir=self.temp_vfs.name,
            link_type="symlink",
            default_language="eng",
            default_type="Manga",
        )

        records = [
            BookFileRecord(
                book_id=1,
                title="Naruto 1",
                series="Naruto",
                language="eng",
                type_="Manga",
                volume=1,
                chapter=1,
                format="CBZ",
                source_path=self.source1,
            ),
            BookFileRecord(
                book_id=2,
                title="Naruto 2",
                series="Naruto",
                language="eng",
                type_="Manga",
                volume=1,
                chapter=2,
                format="CBZ",
                source_path=self.source2,
            ),
        ]

        created, updated, deleted = vfs.sync(records)
        self.assertEqual(created, 2)
        self.assertEqual(updated, 0)
        self.assertEqual(deleted, 0)

        # Expected files in VFS
        file1 = os.path.join(self.temp_vfs.name, "eng/Manga/Naruto/Naruto Vol. 1 Ch. 1.cbz")
        file2 = os.path.join(self.temp_vfs.name, "eng/Manga/Naruto/Naruto Vol. 1 Ch. 2.cbz")

        self.assertTrue(os.path.islink(file1))
        self.assertTrue(os.path.islink(file2))
        self.assertEqual(os.path.realpath(file1), os.path.realpath(self.source1))
        self.assertEqual(os.path.realpath(file2), os.path.realpath(self.source2))

        # Re-run sync with same records: no change
        created, updated, deleted = vfs.sync(records)
        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(deleted, 0)

        # Now remove book 2 and run sync: book 2 link should be pruned
        created, updated, deleted = vfs.sync([records[0]])
        self.assertEqual(created, 0)
        self.assertEqual(updated, 0)
        self.assertEqual(deleted, 1)
        self.assertFalse(os.path.exists(file2))
        self.assertTrue(os.path.exists(file1))

    def test_relative_symlinks(self):
        vfs = SymlinkVFS(
            vfs_dir=self.temp_vfs.name,
            link_type="symlink",
            relative_links=True,
            default_language="eng",
            default_type="Manga",
        )

        record = BookFileRecord(
            book_id=1,
            title="Naruto 1",
            series="Naruto",
            language="eng",
            type_="Manga",
            volume=1,
            chapter=1,
            format="CBZ",
            source_path=self.source1,
        )

        vfs.sync([record])
        target = os.path.join(self.temp_vfs.name, "eng/Manga/Naruto/Naruto Vol. 1 Ch. 1.cbz")
        self.assertTrue(os.path.islink(target))
        link_dest = os.readlink(target)
        # Verify it is relative
        self.assertFalse(os.path.isabs(link_dest))
        # Verify it resolves to source1
        self.assertEqual(os.path.realpath(target), os.path.realpath(self.source1))


if __name__ == "__main__":
    unittest.main()
