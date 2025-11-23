"""
Database module for CryptoHack Discord Bot.
Uses SQLite with aiosqlite for async operations.
"""

import aiosqlite
from pathlib import Path
from typing import Optional

DATABASE_PATH = Path(__file__).parent / "cryptohack_bot.db"


async def init_db():
    """Initialize the database with required tables."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Table for tracking users per guild
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tracked_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                cryptohack_username TEXT NOT NULL,
                discord_user_id INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, cryptohack_username)
            )
        """)

        # Table for caching solved challenges (to detect new solves)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS solved_challenges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                cryptohack_username TEXT NOT NULL,
                challenge_name TEXT NOT NULL,
                challenge_category TEXT,
                challenge_points INTEGER,
                solved_date TEXT,
                first_blood BOOLEAN DEFAULT FALSE,
                announced BOOLEAN DEFAULT FALSE,
                UNIQUE(guild_id, cryptohack_username, challenge_name)
            )
        """)

        # Table for guild settings
        await db.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                announcement_channel_id INTEGER,
                check_interval_minutes INTEGER DEFAULT 10
            )
        """)

        # Table for tracking first bloods within a guild
        await db.execute("""
            CREATE TABLE IF NOT EXISTS guild_first_bloods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                challenge_name TEXT NOT NULL,
                first_solver_username TEXT NOT NULL,
                solved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, challenge_name)
            )
        """)

        await db.commit()


async def add_user(guild_id: int, username: str, discord_user_id: Optional[int] = None) -> bool:
    """Add a CryptoHack user to track for a guild. Returns True if added, False if already exists."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO tracked_users (guild_id, cryptohack_username, discord_user_id) VALUES (?, ?, ?)",
                (guild_id, username.lower(), discord_user_id)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def remove_user(guild_id: int, username: str) -> bool:
    """Remove a tracked user. Returns True if removed, False if not found."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM tracked_users WHERE guild_id = ? AND cryptohack_username = ?",
            (guild_id, username.lower())
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_tracked_users(guild_id: int) -> list[dict]:
    """Get all tracked users for a guild."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT cryptohack_username, discord_user_id FROM tracked_users WHERE guild_id = ?",
            (guild_id,)
        )
        rows = await cursor.fetchall()
        return [{"username": row["cryptohack_username"], "discord_user_id": row["discord_user_id"]} for row in rows]


async def get_all_tracked_users() -> list[dict]:
    """Get all tracked users across all guilds."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT guild_id, cryptohack_username, discord_user_id FROM tracked_users"
        )
        rows = await cursor.fetchall()
        return [{"guild_id": row["guild_id"], "username": row["cryptohack_username"], "discord_user_id": row["discord_user_id"]} for row in rows]


async def get_solved_challenges(guild_id: int, username: str) -> set[str]:
    """Get set of challenge names already solved by a user in a guild."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT challenge_name FROM solved_challenges WHERE guild_id = ? AND cryptohack_username = ?",
            (guild_id, username.lower())
        )
        rows = await cursor.fetchall()
        return {row[0] for row in rows}


async def add_solved_challenge(
    guild_id: int,
    username: str,
    challenge_name: str,
    category: str,
    points: int,
    solved_date: str,
    first_blood: bool = False
) -> bool:
    """Add a solved challenge. Returns True if new, False if already existed."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute(
                """INSERT INTO solved_challenges
                   (guild_id, cryptohack_username, challenge_name, challenge_category,
                    challenge_points, solved_date, first_blood)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (guild_id, username.lower(), challenge_name, category, points, solved_date, first_blood)
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def mark_challenge_announced(guild_id: int, username: str, challenge_name: str):
    """Mark a challenge as announced."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """UPDATE solved_challenges SET announced = TRUE
               WHERE guild_id = ? AND cryptohack_username = ? AND challenge_name = ?""",
            (guild_id, username.lower(), challenge_name)
        )
        await db.commit()


async def get_unannounced_solves(guild_id: int) -> list[dict]:
    """Get all unannounced solves for a guild."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT cryptohack_username, challenge_name, challenge_category,
                      challenge_points, solved_date, first_blood
               FROM solved_challenges
               WHERE guild_id = ? AND announced = FALSE
               ORDER BY solved_date DESC""",
            (guild_id,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def check_and_set_first_blood(guild_id: int, challenge_name: str, username: str) -> bool:
    """Check if this is the first solve in the guild. Returns True if first blood."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO guild_first_bloods (guild_id, challenge_name, first_solver_username) VALUES (?, ?, ?)",
                (guild_id, challenge_name, username.lower())
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def get_challenge_solvers(guild_id: int, challenge_name: str) -> list[dict]:
    """Get all users in the guild who solved a specific challenge."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT sc.cryptohack_username, sc.solved_date, sc.first_blood,
                      tu.discord_user_id
               FROM solved_challenges sc
               JOIN tracked_users tu ON sc.guild_id = tu.guild_id
                    AND sc.cryptohack_username = tu.cryptohack_username
               WHERE sc.guild_id = ? AND sc.challenge_name = ?
               ORDER BY sc.solved_date ASC""",
            (guild_id, challenge_name)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def set_announcement_channel(guild_id: int, channel_id: int):
    """Set the announcement channel for a guild."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """INSERT INTO guild_settings (guild_id, announcement_channel_id)
               VALUES (?, ?)
               ON CONFLICT(guild_id) DO UPDATE SET announcement_channel_id = ?""",
            (guild_id, channel_id, channel_id)
        )
        await db.commit()


async def get_announcement_channel(guild_id: int) -> Optional[int]:
    """Get the announcement channel for a guild."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute(
            "SELECT announcement_channel_id FROM guild_settings WHERE guild_id = ?",
            (guild_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def get_guild_ids() -> list[int]:
    """Get all unique guild IDs that have tracked users."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cursor = await db.execute("SELECT DISTINCT guild_id FROM tracked_users")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]
