"""
Lost Island: 15 Boys Survival RPG Engine
Database & Profile Persistence Layer.
Transactional SQLite storage tracking users, active sessions, profiles, and saves.
"""

import sqlite3
import hashlib
import secrets
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from contextlib import contextmanager

class PersistenceEngine:
    def __init__(self, db_path: str = "lost_island.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    @contextmanager
    def transaction(self):
        """Safe atomic transactional context manager."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        """Initialize all relational database tables safely."""
        with self.transaction() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    last_login REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS profiles (
                    user_id TEXT PRIMARY KEY,
                    xp INTEGER DEFAULT 0,
                    total_games INTEGER DEFAULT 0,
                    storms_survived INTEGER DEFAULT 0,
                    days_survived INTEGER DEFAULT 0,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS achievements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    achievement_key TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    unlocked_at REAL NOT NULL,
                    UNIQUE(user_id, achievement_key),
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS active_sessions (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    room_id TEXT,
                    character_id TEXT,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS campaign_saves (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    save_name TEXT NOT NULL,
                    game_mode TEXT NOT NULL,
                    day INTEGER NOT NULL,
                    time_of_day TEXT NOT NULL,
                    camp_data_json TEXT NOT NULL,
                    roster_data_json TEXT NOT NULL,
                    updated_at REAL NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                );
            """)

    def _hash_password(self, password: str, salt: str) -> str:
        return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

    def register_user(self, username: str, password: str) -> Tuple[bool, str]:
        """Register a new user account with hashed credentials."""
        user_id = f"usr_{secrets.token_hex(8)}"
        salt = secrets.token_hex(16)
        pw_hash = self._hash_password(password, salt)
        now = time.time()

        try:
            with self.transaction() as conn:
                conn.execute(
                    "INSERT INTO users (id, username, password_hash, salt, created_at, last_login) VALUES (?, ?, ?, ?, ?, ?)",
                    (user_id, username, pw_hash, salt, now, now)
                )
                conn.execute(
                    "INSERT INTO profiles (user_id, xp, total_games, storms_survived, days_survived) VALUES (?, 0, 0, 0, 0)",
                    (user_id,)
                )
            return True, user_id
        except sqlite3.IntegrityError:
            return False, "Username already exists."

    def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Verify user credentials and create an active session token."""
        with self.transaction() as conn:
            cursor = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
            row = cursor.fetchone()
            if not row:
                return None

            expected_hash = self._hash_password(password, row["salt"])
            if row["password_hash"] != expected_hash:
                return None

            now = time.time()
            conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (now, row["id"]))
            
            # Create session token
            token = f"tok_{secrets.token_urlsafe(24)}"
            expires_at = now + 86400.0 # 24 hours
            conn.execute(
                "INSERT INTO active_sessions (token, user_id, room_id, character_id, created_at, expires_at) VALUES (?, ?, NULL, NULL, ?, ?)",
                (token, row["id"], now, expires_at)
            )

            return {
                "user_id": row["id"],
                "username": row["username"],
                "token": token
            }

    def validate_session(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate session token and return user profile information."""
        now = time.time()
        with self.transaction() as conn:
            cursor = conn.execute(
                """
                SELECT s.token, s.user_id, s.room_id, s.character_id, u.username, p.xp, p.storms_survived
                FROM active_sessions s
                JOIN users u ON s.user_id = u.id
                JOIN profiles p ON s.user_id = p.user_id
                WHERE s.token = ? AND s.expires_at > ?
                """,
                (token, now)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row)

    def update_session_room(self, token: str, room_id: Optional[str], character_id: Optional[str]):
        """Sync session with assigned room and character lock."""
        with self.transaction() as conn:
            conn.execute(
                "UPDATE active_sessions SET room_id = ?, character_id = ? WHERE token = ?",
                (room_id, character_id, token)
            )

    def unlock_achievement(self, user_id: str, key: str, title: str, description: str) -> bool:
        """Atomically award achievement if not previously unlocked."""
        now = time.time()
        try:
            with self.transaction() as conn:
                conn.execute(
                    "INSERT INTO achievements (user_id, achievement_key, title, description, unlocked_at) VALUES (?, ?, ?, ?, ?)",
                    (user_id, key, title, description, now)
                )
                conn.execute("UPDATE profiles SET xp = xp + 100 WHERE user_id = ?", (user_id,))
            return True
        except sqlite3.IntegrityError:
            return False # Already unlocked

    def record_storm_survival(self, user_id: str):
        """Increment storm survival stats and grant survival achievement."""
        with self.transaction() as conn:
            conn.execute(
                "UPDATE profiles SET storms_survived = storms_survived + 1, xp = xp + 250 WHERE user_id = ?",
                (user_id,)
            )
        self.unlock_achievement(
            user_id,
            "STORM_SURVIVOR",
            "Pacific Tempest Survivor",
            "Kept The Sloughi afloat and breached the reef barrier of Chairman Island."
        )

    def save_campaign(self, user_id: str, save_name: str, game_mode: str, day: int, time_of_day: str, camp_data: dict, roster_data: dict) -> str:
        """Serialize and persist campaign snapshot."""
        save_id = f"sav_{secrets.token_hex(6)}"
        now = time.time()
        camp_json = json.dumps(camp_data)
        roster_json = json.dumps(roster_data)

        with self.transaction() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO campaign_saves 
                (id, user_id, save_name, game_mode, day, time_of_day, camp_data_json, roster_data_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (save_id, user_id, save_name, game_mode, day, time_of_day, camp_json, roster_json, now)
            )
        return save_id

    def load_campaign(self, save_id: str) -> Optional[Dict[str, Any]]:
        """Load and deserialize campaign snapshot."""
        with self.transaction() as conn:
            cursor = conn.execute("SELECT * FROM campaign_saves WHERE id = ?", (save_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "user_id": row["user_id"],
                "save_name": row["save_name"],
                "game_mode": row["game_mode"],
                "day": row["day"],
                "time_of_day": row["time_of_day"],
                "camp_data": json.loads(row["camp_data_json"]),
                "roster_data": json.loads(row["roster_data_json"]),
                "updated_at": row["updated_at"]
            }

    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch complete player profile with unlocked achievements."""
        with self.transaction() as conn:
            u_cur = conn.execute("SELECT id, username, created_at FROM users WHERE id = ?", (user_id,))
            u_row = u_cur.fetchone()
            if not u_row:
                return None

            p_cur = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
            p_row = p_cur.fetchone()

            ach_cur = conn.execute("SELECT achievement_key, title, description, unlocked_at FROM achievements WHERE user_id = ?", (user_id,))
            ach_rows = [dict(r) for r in ach_cur.fetchall()]

            return {
                "user_id": u_row["id"],
                "username": u_row["username"],
                "created_at": u_row["created_at"],
                "stats": dict(p_row) if p_row else {},
                "achievements": ach_rows
            }

