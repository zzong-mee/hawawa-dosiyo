"""Small server-scoped store, isolated from legacy databases."""

import asyncio
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "hawawa-v3.db"


class Store:
    def __init__(self, path: Path = DEFAULT_PATH):
        self.path = Path(path)
        self._schema_ready = False
        self._schema_lock = threading.Lock()

    async def execute(self, query: str, parameters: tuple = ()) -> list[tuple]:
        return await asyncio.to_thread(self._execute, query, parameters)

    def _execute(self, query, parameters):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path, timeout=10)) as connection:
            if not self._schema_ready:
                with self._schema_lock:
                    if not self._schema_ready:
                        with connection:
                            version = connection.execute("PRAGMA user_version").fetchone()[0]
                            if version > 1:
                                raise RuntimeError("Database schema is newer than this bot supports")
                            connection.execute("CREATE TABLE IF NOT EXISTS settings (guild INTEGER NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY (guild, key))")
                            connection.execute("CREATE TABLE IF NOT EXISTS tags (guild INTEGER NOT NULL, name TEXT NOT NULL, content TEXT NOT NULL, PRIMARY KEY (guild, name))")
                            connection.execute("CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY AUTOINCREMENT, guild INTEGER NOT NULL, user INTEGER NOT NULL, text TEXT NOT NULL, due REAL NOT NULL, state TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0)")
                            reminder_columns = {row[1] for row in connection.execute("PRAGMA table_info(reminders)")}
                            if "name" not in reminder_columns:
                                try:
                                    connection.execute("ALTER TABLE reminders ADD COLUMN name TEXT NOT NULL DEFAULT ''")
                                except sqlite3.OperationalError as error:
                                    # Several Cogs may initialize their own Store concurrently.
                                    # Another connection can add the column between PRAGMA and ALTER.
                                    if "duplicate column name" not in str(error).lower():
                                        raise
                            connection.execute("CREATE INDEX IF NOT EXISTS reminder_due ON reminders(state,due)")
                            connection.execute("CREATE TABLE IF NOT EXISTS role_panels (guild INTEGER NOT NULL, message INTEGER NOT NULL, role INTEGER NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, PRIMARY KEY (guild,message))")
                            connection.execute("CREATE TABLE IF NOT EXISTS experience (guild INTEGER NOT NULL, user INTEGER NOT NULL, xp INTEGER NOT NULL, last REAL NOT NULL, PRIMARY KEY(guild,user))")
                            connection.execute("CREATE TABLE IF NOT EXISTS temporary_roles (guild INTEGER NOT NULL, user INTEGER NOT NULL, role INTEGER NOT NULL, due REAL NOT NULL, PRIMARY KEY(guild,user,role))")
                            connection.execute("CREATE TABLE IF NOT EXISTS giveaways (guild INTEGER NOT NULL, message INTEGER NOT NULL, channel INTEGER NOT NULL, prize TEXT NOT NULL, due REAL NOT NULL, count INTEGER NOT NULL, result TEXT, announced INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(guild,message))")
                            connection.execute("CREATE TABLE IF NOT EXISTS giveaway_entries (guild INTEGER NOT NULL, message INTEGER NOT NULL, user INTEGER NOT NULL, PRIMARY KEY(guild,message,user))")
                            connection.execute("CREATE TABLE IF NOT EXISTS star_posts (guild INTEGER NOT NULL, source INTEGER NOT NULL, channel INTEGER NOT NULL, post INTEGER NOT NULL, PRIMARY KEY(guild,source))")
                            connection.execute("CREATE TABLE IF NOT EXISTS moderation_cases (id INTEGER PRIMARY KEY AUTOINCREMENT, guild INTEGER NOT NULL, user INTEGER NOT NULL, moderator INTEGER NOT NULL, reason TEXT NOT NULL, created REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0)")
                            connection.execute("CREATE TABLE IF NOT EXISTS triggers (guild INTEGER NOT NULL, keyword TEXT NOT NULL, response TEXT NOT NULL, PRIMARY KEY(guild,keyword))")
                            connection.execute("CREATE TABLE IF NOT EXISTS delayed_roles (guild INTEGER NOT NULL, role INTEGER NOT NULL, delay INTEGER NOT NULL, PRIMARY KEY(guild,role))")
                            connection.execute("CREATE TABLE IF NOT EXISTS delayed_role_jobs (guild INTEGER NOT NULL, user INTEGER NOT NULL, role INTEGER NOT NULL, due REAL NOT NULL, PRIMARY KEY(guild,user,role))")
                            connection.execute("CREATE TABLE IF NOT EXISTS saved_roles (guild INTEGER NOT NULL, user INTEGER NOT NULL, roles TEXT NOT NULL, expires REAL NOT NULL, PRIMARY KEY(guild,user))")
                            connection.execute("CREATE TABLE IF NOT EXISTS reminder_repeats (reminder INTEGER PRIMARY KEY, minutes INTEGER NOT NULL)")
                            connection.execute("CREATE TABLE IF NOT EXISTS sticky_messages (guild INTEGER NOT NULL, channel INTEGER NOT NULL, text TEXT NOT NULL, post INTEGER NOT NULL DEFAULT 0, last REAL NOT NULL DEFAULT 0, PRIMARY KEY(guild,channel))")
                            connection.execute("CREATE TABLE IF NOT EXISTS level_roles (guild INTEGER NOT NULL, level INTEGER NOT NULL, role INTEGER NOT NULL, PRIMARY KEY(guild,level))")
                            connection.execute("CREATE TABLE IF NOT EXISTS suggestions (guild INTEGER NOT NULL, message INTEGER NOT NULL, channel INTEGER NOT NULL, author INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending', reason TEXT NOT NULL DEFAULT '', PRIMARY KEY(guild,message))")
                            connection.execute("CREATE TABLE IF NOT EXISTS suggestion_votes (guild INTEGER NOT NULL, message INTEGER NOT NULL, user INTEGER NOT NULL, vote INTEGER NOT NULL, PRIMARY KEY(guild,message,user))")
                            connection.execute("CREATE TABLE IF NOT EXISTS stock_accounts (guild INTEGER NOT NULL, user INTEGER NOT NULL, cash INTEGER NOT NULL DEFAULT 10000, PRIMARY KEY(guild,user))")
                            connection.execute("CREATE TABLE IF NOT EXISTS stock_holdings (guild INTEGER NOT NULL, user INTEGER NOT NULL, symbol TEXT NOT NULL, quantity INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(guild,user,symbol))")
                            connection.execute("CREATE TABLE IF NOT EXISTS stock_market (guild INTEGER NOT NULL, symbol TEXT NOT NULL, price INTEGER NOT NULL, PRIMARY KEY(guild,symbol))")
                            connection.execute("PRAGMA user_version=1")
                        self._schema_ready = True
            with connection:
                return connection.execute(query, parameters).fetchall()

    async def get(self, guild: int, key: str):
        rows = await self.execute("SELECT value FROM settings WHERE guild=? AND key=?", (guild, key))
        return rows[0][0] if rows else None

    async def set(self, guild: int, key: str, value: str):
        await self.execute("INSERT INTO settings VALUES (?, ?, ?) ON CONFLICT(guild,key) DO UPDATE SET value=excluded.value", (guild, key, value))
