import os
import shutil
import tempfile
import unittest

from vfs_database import VFSDatabase


class TestVFSDatabase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_vfs.db")
        self.db = VFSDatabase(self.db_path)

    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_and_tracked_map(self):
        tracked = self.db.get_tracked_map()
        self.assertEqual(tracked, {})

    def test_upsert_and_query(self):
        entries = [
            {
                "vfs_path": "/vfs/eng/Manga/One Piece/One Piece Vol. 1 {1}.cbz",
                "vfs_relpath": "eng/Manga/One Piece/One Piece Vol. 1 {1}.cbz",
                "source_path": "/calibre/author/book1.cbz",
                "book_id": 1,
                "title": "One Piece 1",
                "series": "One Piece",
                "volume": "1",
                "chapter": "",
                "type": "Manga",
                "language": "eng",
                "format": "CBZ",
                "link_type": "symlink",
                "target_source": "/calibre/author/book1.cbz",
                "last_synced": 1000.0,
            },
            {
                "vfs_path": "/vfs/eng/Manga/One Piece/One Piece Vol. 2 {2}.cbz",
                "vfs_relpath": "eng/Manga/One Piece/One Piece Vol. 2 {2}.cbz",
                "source_path": "/calibre/author/book2.cbz",
                "book_id": 2,
                "title": "One Piece 2",
                "series": "One Piece",
                "volume": "2",
                "chapter": "",
                "type": "Manga",
                "language": "eng",
                "format": "CBZ",
                "link_type": "symlink",
                "target_source": "/calibre/author/book2.cbz",
                "last_synced": 1000.0,
            },
            {
                "vfs_path": "/vfs/eng/Comic/Batman/Batman Ch. 5 {10}.cbr",
                "vfs_relpath": "eng/Comic/Batman/Batman Ch. 5 {10}.cbr",
                "source_path": "/calibre/author/batman.cbr",
                "book_id": 10,
                "title": "Batman Year One",
                "series": "Batman",
                "volume": "",
                "chapter": "5",
                "type": "Comic",
                "language": "eng",
                "format": "CBR",
                "link_type": "symlink",
                "target_source": "/calibre/author/batman.cbr",
                "last_synced": 1000.0,
            },
        ]
        self.db.upsert_entries(entries)

        tracked = self.db.get_tracked_map()
        self.assertEqual(len(tracked), 3)
        self.assertIn("/vfs/eng/Manga/One Piece/One Piece Vol. 1 {1}.cbz", tracked)

        # Pagination & Query tests
        all_res = self.db.query_items(limit=2, offset=0)
        self.assertEqual(all_res["total"], 3)
        self.assertEqual(len(all_res["items"]), 2)
        self.assertEqual(all_res["items"][0]["book_id"], 1)
        self.assertEqual(all_res["items"][1]["book_id"], 2)

        page2 = self.db.query_items(limit=2, offset=2)
        self.assertEqual(len(page2["items"]), 1)
        self.assertEqual(page2["items"][0]["book_id"], 10)

        # Search query tests
        batman_res = self.db.query_items(query="batman")
        self.assertEqual(batman_res["total"], 1)
        self.assertEqual(batman_res["items"][0]["series"], "Batman")

        id_res = self.db.query_items(query="10")
        self.assertEqual(id_res["total"], 1)
        self.assertEqual(id_res["items"][0]["book_id"], 10)

    def test_delete_and_clear(self):
        entries = [
            {
                "vfs_path": "/vfs/p1.cbz",
                "vfs_relpath": "p1.cbz",
                "source_path": "/calibre/p1.cbz",
                "book_id": 1,
                "title": "T1",
                "series": "",
                "volume": "",
                "chapter": "",
                "type": "",
                "language": "",
                "format": "CBZ",
                "link_type": "symlink",
                "target_source": "/calibre/p1.cbz",
                "last_synced": 1000.0,
            },
            {
                "vfs_path": "/vfs/p2.cbz",
                "vfs_relpath": "p2.cbz",
                "source_path": "/calibre/p2.cbz",
                "book_id": 2,
                "title": "T2",
                "series": "",
                "volume": "",
                "chapter": "",
                "type": "",
                "language": "",
                "format": "CBZ",
                "link_type": "symlink",
                "target_source": "/calibre/p2.cbz",
                "last_synced": 1000.0,
            },
        ]
        self.db.upsert_entries(entries)
        self.assertEqual(len(self.db.get_tracked_map()), 2)

        self.db.delete_entries(["/vfs/p1.cbz"])
        tracked = self.db.get_tracked_map()
        self.assertEqual(len(tracked), 1)
        self.assertNotIn("/vfs/p1.cbz", tracked)

        self.db.clear()
        self.assertEqual(len(self.db.get_tracked_map()), 0)


if __name__ == "__main__":
    unittest.main()
