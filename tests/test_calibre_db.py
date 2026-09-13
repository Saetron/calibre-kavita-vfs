import os
import sqlite3
import tempfile
import unittest

from calibre_db import CalibreDBReader


class TestCalibreDB(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.calibre_dir = self.temp_dir.name
        self.db_path = os.path.join(self.calibre_dir, "metadata.db")
        self._init_db()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        # Core Calibre tables
        cur.executescript("""
            CREATE TABLE books (
                id INTEGER PRIMARY KEY,
                title TEXT,
                path TEXT
            );

            CREATE TABLE data (
                id INTEGER PRIMARY KEY,
                book INTEGER,
                format TEXT,
                name TEXT
            );

            CREATE TABLE series (
                id INTEGER PRIMARY KEY,
                name TEXT
            );

            CREATE TABLE books_series_link (
                id INTEGER PRIMARY KEY,
                book INTEGER,
                series INTEGER
            );

            CREATE TABLE languages (
                id INTEGER PRIMARY KEY,
                lang_code TEXT
            );

            CREATE TABLE books_languages_link (
                id INTEGER PRIMARY KEY,
                book INTEGER,
                lang_code INTEGER
            );

            CREATE TABLE custom_columns (
                id INTEGER PRIMARY KEY,
                label TEXT,
                name TEXT,
                datatype TEXT,
                normalized BOOL
            );
        """)

        # Insert custom columns:
        # 1. Type (normalized text, label '#type')
        # 2. Volume (non-normalized float, label 'volume')
        # 3. Chapter (non-normalized float, label 'chapter')
        cur.execute("INSERT INTO custom_columns VALUES (1, '#type', 'Type', 'text', 1)")
        cur.execute("INSERT INTO custom_columns VALUES (2, 'volume', 'Volume', 'float', 0)")
        cur.execute("INSERT INTO custom_columns VALUES (3, 'chapter', 'Chapter', 'float', 0)")

        # Custom column 1 (type) tables: normalized
        cur.execute("CREATE TABLE custom_column_1 (id INTEGER PRIMARY KEY, value TEXT)")
        cur.execute("CREATE TABLE books_custom_column_1_link (id INTEGER PRIMARY KEY, book INTEGER, value INTEGER)")
        cur.execute("INSERT INTO custom_column_1 VALUES (10, 'Manga')")
        cur.execute("INSERT INTO custom_column_1 VALUES (11, 'Light Novel')")

        # Custom column 2 (volume) table: unnormalized
        cur.execute("CREATE TABLE custom_column_2 (id INTEGER PRIMARY KEY, book INTEGER, value REAL)")

        # Custom column 3 (chapter) table: unnormalized
        cur.execute("CREATE TABLE custom_column_3 (id INTEGER PRIMARY KEY, book INTEGER, value REAL)")

        # Series
        cur.execute("INSERT INTO series VALUES (1, 'Bleach')")
        # Language
        cur.execute("INSERT INTO languages VALUES (1, 'eng')")

        # Book 1: Bleach Vol 1 Ch 1
        cur.execute("INSERT INTO books VALUES (1, 'Bleach - Chapter 1', 'Kubo/Bleach (1)')")
        cur.execute("INSERT INTO data VALUES (1, 1, 'CBZ', 'Bleach - Chapter 1')")
        cur.execute("INSERT INTO books_series_link VALUES (1, 1, 1)")
        cur.execute("INSERT INTO books_languages_link VALUES (1, 1, 1)")
        cur.execute("INSERT INTO books_custom_column_1_link VALUES (1, 1, 10)")  # Manga
        cur.execute("INSERT INTO custom_column_2 VALUES (1, 1, 1.0)")             # Vol 1
        cur.execute("INSERT INTO custom_column_3 VALUES (1, 1, 1.0)")             # Ch 1

        # Book 2: Bleach Vol 2 (No chapter)
        cur.execute("INSERT INTO books VALUES (2, 'Bleach Volume 2', 'Kubo/Bleach (2)')")
        cur.execute("INSERT INTO data VALUES (2, 2, 'CBZ', 'Bleach Volume 2')")
        cur.execute("INSERT INTO books_series_link VALUES (2, 2, 1)")
        cur.execute("INSERT INTO books_languages_link VALUES (2, 2, 1)")
        cur.execute("INSERT INTO books_custom_column_1_link VALUES (2, 2, 10)")  # Manga
        cur.execute("INSERT INTO custom_column_2 VALUES (2, 2, 2.0)")             # Vol 2

        # Book 3: Standalone novel without series, volume, chapter
        cur.execute("INSERT INTO books VALUES (3, 'A Wild Novel', 'Author/A Wild Novel (3)')")
        cur.execute("INSERT INTO data VALUES (3, 3, 'EPUB', 'A Wild Novel')")
        cur.execute("INSERT INTO books_languages_link VALUES (3, 3, 1)")
        cur.execute("INSERT INTO books_custom_column_1_link VALUES (3, 3, 11)")  # Light Novel

        # Book 4: Bleach Omnibus Vol 1-3
        cur.execute("INSERT INTO books VALUES (4, 'Bleach Omnibus 1', 'Kubo/Bleach (4)')")
        cur.execute("INSERT INTO data VALUES (4, 4, 'CBZ', 'Bleach Omnibus 1')")
        cur.execute("INSERT INTO books_series_link VALUES (4, 4, 1)")
        cur.execute("INSERT INTO books_languages_link VALUES (4, 4, 1)")
        cur.execute("INSERT INTO books_custom_column_1_link VALUES (4, 4, 10)")  # Manga
        cur.execute("INSERT INTO custom_column_2 VALUES (4, 4, '1-3')")          # Vol 1-3
        cur.execute("INSERT INTO custom_column_3 VALUES (4, 4, '1-25')")         # Ch 1-25

        conn.commit()
        conn.close()

        # Create dummy file paths in filesystem
        os.makedirs(os.path.join(self.calibre_dir, "Kubo/Bleach (1)"), exist_ok=True)
        with open(os.path.join(self.calibre_dir, "Kubo/Bleach (1)/Bleach - Chapter 1.cbz"), "w") as f:
            f.write("mock content")

        os.makedirs(os.path.join(self.calibre_dir, "Kubo/Bleach (2)"), exist_ok=True)
        with open(os.path.join(self.calibre_dir, "Kubo/Bleach (2)/Bleach Volume 2.cbz"), "w") as f:
            f.write("mock content")

        os.makedirs(os.path.join(self.calibre_dir, "Author/A Wild Novel (3)"), exist_ok=True)
        with open(os.path.join(self.calibre_dir, "Author/A Wild Novel (3)/A Wild Novel.epub"), "w") as f:
            f.write("mock content")

        os.makedirs(os.path.join(self.calibre_dir, "Kubo/Bleach (4)"), exist_ok=True)
        with open(os.path.join(self.calibre_dir, "Kubo/Bleach (4)/Bleach Omnibus 1.cbz"), "w") as f:
            f.write("mock content")

    def test_custom_column_discovery_and_reading(self):
        reader = CalibreDBReader(self.calibre_dir)
        self.assertTrue(reader.exists())

        books = reader.get_all_book_files()
        self.assertEqual(len(books), 4)

        # Check Book 1
        b1 = next(b for b in books if b.book_id == 1)
        self.assertEqual(b1.series, "Bleach")
        self.assertEqual(b1.language, "eng")
        self.assertEqual(b1.type_, "Manga")
        self.assertEqual(b1.volume, 1.0)
        self.assertEqual(b1.chapter, 1.0)
        self.assertEqual(b1.format, "CBZ")
        self.assertTrue(os.path.exists(b1.source_path))

        # Check Book 2
        b2 = next(b for b in books if b.book_id == 2)
        self.assertEqual(b2.series, "Bleach")
        self.assertEqual(b2.type_, "Manga")
        self.assertEqual(b2.volume, 2.0)
        self.assertIsNone(b2.chapter)

        # Check Book 3
        b3 = next(b for b in books if b.book_id == 3)
        self.assertIsNone(b3.series)
        self.assertEqual(b3.type_, "Light Novel")
        self.assertIsNone(b3.volume)
        self.assertIsNone(b3.chapter)

        # Check Book 4 (Ranges)
        b4 = next(b for b in books if b.book_id == 4)
        self.assertEqual(b4.series, "Bleach")
        self.assertEqual(b4.type_, "Manga")
        self.assertEqual(b4.volume, "1-3")
        self.assertEqual(b4.chapter, "1-25")


if __name__ == "__main__":
    unittest.main()
