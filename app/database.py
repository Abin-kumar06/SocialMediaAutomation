import sqlite3
import threading
from pathlib import Path
from app.config import settings

class Database:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(Database, cls).__new__(cls)
                cls._instance._db_path = "accounts.db"
                cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        with sqlite3.connect(self._db_path) as conn:
            # Users table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    full_name TEXT NOT NULL,
                    hashed_password TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # LinkedIn accounts table (updated with user_id)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS linkedin_accounts (
                    member_urn TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    access_token TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)

            # Instagram accounts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS instagram_accounts (
                    user_id INTEGER PRIMARY KEY,
                    access_token TEXT NOT NULL,
                    expires_at DATETIME NOT NULL,
                    last_refreshed_at DATETIME NOT NULL,
                    status TEXT DEFAULT 'active',
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)
            
            # X accounts table (Moving from JSON to SQLite for consistency)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS x_accounts (
                    x_user_id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT,
                    expires_at REAL NOT NULL,
                    status TEXT DEFAULT 'active',
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)
            
            # Migration for linkedin_accounts to add user_id if missing
            cursor = conn.execute("PRAGMA table_info(linkedin_accounts)")
            columns = [column[1] for column in cursor.fetchall()]
            if columns and "user_id" not in columns:
                print("Migrating linkedin_accounts table: adding user_id column")
                # SQLite doesn't support adding a column with NOT NULL and without a DEFAULT value comfortably in one step 
                # if there is existing data. We'll add it as nullable first or with a default.
                # Since we want it NOT NULL and bound to a user, we'll use a default of 1 if users exist, 
                # or just add it if the table is empty.
                conn.execute("ALTER TABLE linkedin_accounts ADD COLUMN user_id INTEGER DEFAULT 1 REFERENCES users(id)")
                print("Successfully added user_id column to linkedin_accounts")

            conn.commit()

    def get_connection(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

db = Database()
