"""Hawawa Dosiyo smoke checks and database migration safety checks."""
import ast
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class IntegrationChecks(unittest.TestCase):
    def test_all_python_modules_parse(self):
        for file in (ROOT / "bot").rglob("*.py"):
            with self.subTest(file=file.name):
                ast.parse(file.read_text(encoding="utf-8"), filename=str(file))

    def test_token_is_not_hardcoded(self):
        for file in (ROOT / "bot").rglob("*.py"):
            source = file.read_text(encoding="utf-8")
            self.assertNotIn("bot.run('", source)
            self.assertNotIn("MTAxMzg1", source)

    def test_database_backup_preserves_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "original.db"
            backup = Path(directory) / "backup.db"
            with sqlite3.connect(original) as conn:
                conn.execute("CREATE TABLE user_wallets (user_id INTEGER PRIMARY KEY, balance INTEGER)")
                conn.execute("INSERT INTO user_wallets VALUES (123, 456)")
                with sqlite3.connect(backup) as dst:
                    conn.backup(dst)
            with sqlite3.connect(backup) as conn:
                self.assertEqual(conn.execute("SELECT balance FROM user_wallets WHERE user_id=123").fetchone()[0], 456)


if __name__ == "__main__":
    unittest.main()
