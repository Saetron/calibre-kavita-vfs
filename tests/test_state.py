import unittest
from calibre_db import BookFileRecord
from vfs_state import VFSState, calculate_units


class TestVFSState(unittest.TestCase):
    def test_calculate_units(self):
        self.assertEqual(calculate_units(None), 0.0)
        self.assertEqual(calculate_units(""), 0.0)
        self.assertEqual(calculate_units(1), 1.0)
        self.assertEqual(calculate_units(1.0), 1.0)
        self.assertEqual(calculate_units("1"), 1.0)
        self.assertEqual(calculate_units("10.5"), 1.0)
        self.assertEqual(calculate_units("Special"), 1.0)

        # Ranges
        self.assertEqual(calculate_units("1-3"), 3.0)
        self.assertEqual(calculate_units("1 - 3"), 3.0)
        self.assertEqual(calculate_units("1-25"), 25.0)
        self.assertEqual(calculate_units("Vol. 1-5"), 5.0)
        self.assertEqual(calculate_units("Ch. 1-10"), 10.0)

    def test_state_update_and_summary(self):
        state = VFSState()

        records = [
            BookFileRecord(
                book_id=1,
                title="Berserk 1-3",
                series="Berserk",
                language="eng",
                type_="Manga",
                volume="1-3",
                chapter=None,
                format="CBZ",
                source_path="/calibre/Berserk 1.cbz",
            ),
            BookFileRecord(
                book_id=2,
                title="Berserk 4",
                series="Berserk",
                language="eng",
                type_="Manga",
                volume=4,
                chapter="1-15",
                format="CBZ",
                source_path="/calibre/Berserk 4.cbz",
            ),
            BookFileRecord(
                book_id=3,
                title="Solo Leveling",
                series=None,
                language="eng",
                type_="Comic",
                volume=None,
                chapter=100,
                format="EPUB",
                source_path="/calibre/Solo.epub",
            ),
        ]

        desired_map = {
            "/vfs/eng/Manga/Berserk/Berserk Vol. 1-3 {1}.cbz": "/calibre/Berserk 1.cbz",
            "/vfs/eng/Manga/Berserk/Berserk Vol. 4 Ch. 1-15 {2}.cbz": "/calibre/Berserk 4.cbz",
            "/vfs/eng/Comic/Solo Leveling/Solo Leveling Ch. 100 {3}.epub": "/calibre/Solo.epub",
        }

        collisions = [
            {
                "relpath": "eng/Manga/Berserk/Berserk {1}.cbz",
                "existing_book_id": 1,
                "existing_source": "/calibre/1.cbz",
                "colliding_book_id": 99,
                "colliding_source": "/calibre/99.cbz",
                "resolved_path": "eng/Manga/Berserk/Berserk {1}_collision_1.cbz",
            }
        ]

        state.update_sync_results(
            records=records,
            desired_map=desired_map,
            collisions=collisions,
            mode="symlink",
            calibre_dir="/calibre",
            vfs_dir="/vfs",
        )

        summary = state.get_summary()
        self.assertEqual(summary["total_books"], 3)
        self.assertEqual(summary["total_series"], 2)  # Berserk + Solo Leveling
        # Volumes: 1-3 (3) + 4 (1) = 4
        self.assertEqual(summary["total_volumes"], 4)
        # Chapters: 1-15 (15) + 100 (1) = 16
        self.assertEqual(summary["total_chapters"], 16)
        self.assertEqual(summary["books_with_volume"], 2)
        self.assertEqual(summary["books_with_chapter"], 2)
        self.assertEqual(summary["collision_count"], 1)
        self.assertEqual(len(summary["collisions"]), 1)
        self.assertEqual(summary["type_counts"]["Manga"], 2)
        self.assertEqual(summary["type_counts"]["Comic"], 1)

        items_resp = state.get_items(query="berserk")
        self.assertEqual(items_resp["total"], 2)


if __name__ == "__main__":
    unittest.main()
