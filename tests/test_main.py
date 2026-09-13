import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest


class TestMainCLI(unittest.TestCase):
    def setUp(self):
        self.temp_calibre = tempfile.TemporaryDirectory()
        self.temp_vfs = tempfile.TemporaryDirectory()

        self.calibre_dir = self.temp_calibre.name
        self.vfs_dir = self.temp_vfs.name
        self.db_path = os.path.join(self.calibre_dir, "metadata.db")

        self._setup_calibre_db()

    def tearDown(self):
        self.temp_calibre.cleanup()
        self.temp_vfs.cleanup()

    def _setup_calibre_db(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.executescript("""
            CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT, path TEXT);
            CREATE TABLE data (id INTEGER PRIMARY KEY, book INTEGER, format TEXT, name TEXT);
            CREATE TABLE series (id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE books_series_link (id INTEGER PRIMARY KEY, book INTEGER, series INTEGER);
            CREATE TABLE languages (id INTEGER PRIMARY KEY, lang_code TEXT);
            CREATE TABLE books_languages_link (id INTEGER PRIMARY KEY, book INTEGER, lang_code INTEGER);
            CREATE TABLE custom_columns (id INTEGER PRIMARY KEY, label TEXT, name TEXT, datatype TEXT, normalized BOOL);

            INSERT INTO custom_columns VALUES (1, 'type', 'Type', 'text', 0);
            INSERT INTO custom_columns VALUES (2, 'volume', 'Volume', 'int', 0);
            INSERT INTO custom_columns VALUES (3, 'chapter', 'Chapter', 'int', 0);

            CREATE TABLE custom_column_1 (id INTEGER PRIMARY KEY, book INTEGER, value TEXT);
            CREATE TABLE custom_column_2 (id INTEGER PRIMARY KEY, book INTEGER, value INTEGER);
            CREATE TABLE custom_column_3 (id INTEGER PRIMARY KEY, book INTEGER, value INTEGER);

            INSERT INTO languages VALUES (1, 'eng');
            INSERT INTO series VALUES (1, 'One Piece');

            -- Book 1: Vol 10, Ch 100
            INSERT INTO books VALUES (1, 'Chapter 100', 'Oda/One Piece (1)');
            INSERT INTO data VALUES (1, 1, 'CBZ', 'Chapter 100');
            INSERT INTO books_series_link VALUES (1, 1, 1);
            INSERT INTO books_languages_link VALUES (1, 1, 1);
            INSERT INTO custom_column_1 VALUES (1, 1, 'Manga');
            INSERT INTO custom_column_2 VALUES (1, 1, 10);
            INSERT INTO custom_column_3 VALUES (1, 1, 100);
        """)
        conn.commit()
        conn.close()

        # Create source file
        book_folder = os.path.join(self.calibre_dir, "Oda/One Piece (1)")
        os.makedirs(book_folder, exist_ok=True)
        with open(os.path.join(book_folder, "Chapter 100.cbz"), "w") as f:
            f.write("mock comic data")

    def test_main_cli_once(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Run main.py as a subprocess
        cmd = [
            sys.executable,
            "main.py",
            "--calibre-dir", self.calibre_dir,
            "--vfs-dir", self.vfs_dir,
            "--mode", "symlink",
            "--once",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_root)
        self.assertEqual(result.returncode, 0, f"Process failed: {result.stderr}")

        expected_file = os.path.join(
            self.vfs_dir,
            "eng/Manga/One Piece/One Piece Vol. 10 Ch. 100.cbz"
        )
        self.assertTrue(os.path.exists(expected_file))
        self.assertTrue(os.path.islink(expected_file))

    def test_main_cli_data_dir(self):
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with tempfile.TemporaryDirectory() as single_mount_dir:
            calibre_subdir = os.path.join(single_mount_dir, "calibre")
            vfs_subdir = os.path.join(single_mount_dir, "vfs")
            os.makedirs(calibre_subdir, exist_ok=True)
            os.makedirs(vfs_subdir, exist_ok=True)

            # Copy DB and test files
            import shutil
            shutil.copy2(self.db_path, os.path.join(calibre_subdir, "metadata.db"))
            shutil.copytree(
                os.path.join(self.calibre_dir, "Oda"),
                os.path.join(calibre_subdir, "Oda"),
            )

            cmd = [
                sys.executable,
                "main.py",
                "--data-dir", single_mount_dir,
                "--mode", "hardlink",
                "--once",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_root)
            self.assertEqual(result.returncode, 0, f"Process failed: {result.stderr}")

            expected_file = os.path.join(
                vfs_subdir,
                "eng/Manga/One Piece/One Piece Vol. 10 Ch. 100.cbz"
            )
            self.assertTrue(os.path.exists(expected_file))
            # Verify it is a real file (hardlink, not symlink)
            self.assertFalse(os.path.islink(expected_file))


if __name__ == "__main__":
    unittest.main()
