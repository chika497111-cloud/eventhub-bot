import aiosqlite
import logging
from datetime import datetime, date, time as dt_time
from pathlib import Path

DB_PATH = Path(__file__).parent / "eventhub.db"
logger = logging.getLogger(__name__)


async def init_db() -> None:
    """Create tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                location TEXT NOT NULL,
                max_participants INTEGER NOT NULL,
                photo_id TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                registered_at TEXT NOT NULL DEFAULT (datetime('now')),
                status TEXT NOT NULL DEFAULT 'registered',
                FOREIGN KEY (event_id) REFERENCES events(id),
                UNIQUE(event_id, user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                message TEXT NOT NULL,
                sent_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await db.commit()
    logger.info("Database initialized")


# ── Events ──────────────────────────────────────────────────────────

async def create_event(
    title: str,
    description: str,
    event_date: str,
    event_time: str,
    location: str,
    max_participants: int,
    photo_id: str | None = None,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO events (title, description, date, time, location, max_participants, photo_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (title, description, event_date, event_time, location, max_participants, photo_id),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]


async def get_event(event_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_active_events(offset: int = 0, limit: int = 5) -> list[dict]:
    """Return upcoming active events, ordered by date/time."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM events
               WHERE status = 'active'
               ORDER BY date ASC, time ASC
               LIMIT ? OFFSET ?""",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def count_active_events() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM events WHERE status = 'active'")
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_all_events(offset: int = 0, limit: int = 10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM events ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def update_event_field(event_id: int, field: str, value) -> None:
    allowed = {"title", "description", "date", "time", "location", "max_participants", "photo_id", "status"}
    if field not in allowed:
        raise ValueError(f"Field {field} is not allowed")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE events SET {field} = ? WHERE id = ?", (value, event_id))
        await db.commit()


async def cancel_event(event_id: int) -> None:
    await update_event_field(event_id, "status", "cancelled")


async def mark_completed_events() -> list[int]:
    """Mark past active events as completed. Returns list of affected event IDs."""
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT id FROM events
               WHERE status = 'active'
               AND (date < ? OR (date = ? AND time < ?))""",
            (today_str, today_str, time_str),
        )
        rows = await cursor.fetchall()
        ids = [r[0] for r in rows]
        if ids:
            placeholders = ",".join("?" for _ in ids)
            await db.execute(
                f"UPDATE events SET status = 'completed' WHERE id IN ({placeholders})",
                ids,
            )
            await db.commit()
        return ids


# ── Registrations ───────────────────────────────────────────────────

async def get_registration_count(event_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM registrations WHERE event_id = ? AND status = 'registered'",
            (event_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_waitlist_count(event_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM registrations WHERE event_id = ? AND status = 'waitlist'",
            (event_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_user_registration(event_id: int, user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM registrations WHERE event_id = ? AND user_id = ?",
            (event_id, user_id),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def register_user(event_id: int, user_id: int, username: str | None) -> str:
    """Register user for event. Returns 'registered', 'waitlist', 'already', or 'full' (shouldn't happen with waitlist)."""
    event = await get_event(event_id)
    if not event or event["status"] != "active":
        return "event_not_found"

    existing = await get_user_registration(event_id, user_id)
    if existing:
        if existing["status"] in ("registered", "waitlist"):
            return "already"
        # Re-register after cancellation
        async with aiosqlite.connect(DB_PATH) as db:
            count = await get_registration_count(event_id)
            new_status = "registered" if count < event["max_participants"] else "waitlist"
            await db.execute(
                "UPDATE registrations SET status = ?, registered_at = datetime('now'), username = ? WHERE id = ?",
                (new_status, username, existing["id"]),
            )
            await db.commit()
            return new_status

    count = await get_registration_count(event_id)
    status = "registered" if count < event["max_participants"] else "waitlist"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO registrations (event_id, user_id, username, status) VALUES (?, ?, ?, ?)",
            (event_id, user_id, username, status),
        )
        await db.commit()
    return status


async def cancel_registration(event_id: int, user_id: int) -> dict | None:
    """Cancel registration, promote first waitlisted user. Returns promoted user dict or None."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE registrations SET status = 'cancelled' WHERE event_id = ? AND user_id = ? AND status IN ('registered', 'waitlist')",
            (event_id, user_id),
        )
        await db.commit()

    # Try to promote from waitlist
    promoted = await _promote_from_waitlist(event_id)
    return promoted


async def _promote_from_waitlist(event_id: int) -> dict | None:
    event = await get_event(event_id)
    if not event:
        return None
    count = await get_registration_count(event_id)
    if count >= event["max_participants"]:
        return None

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM registrations
               WHERE event_id = ? AND status = 'waitlist'
               ORDER BY registered_at ASC LIMIT 1""",
            (event_id,),
        )
        row = await cursor.fetchone()
        if row:
            promoted = dict(row)
            await db.execute(
                "UPDATE registrations SET status = 'registered' WHERE id = ?",
                (promoted["id"],),
            )
            await db.commit()
            return promoted
    return None


async def get_user_registrations(user_id: int) -> list[dict]:
    """Get all active registrations for a user, joined with event data."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT r.id as reg_id, r.status as reg_status, r.registered_at,
                      e.id as event_id, e.title, e.date, e.time, e.location, e.status as event_status
               FROM registrations r
               JOIN events e ON r.event_id = e.id
               WHERE r.user_id = ? AND r.status IN ('registered', 'waitlist')
               ORDER BY e.date ASC, e.time ASC""",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_event_participants(event_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM registrations
               WHERE event_id = ? AND status = 'registered'
               ORDER BY registered_at ASC""",
            (event_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_event_waitlist(event_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM registrations
               WHERE event_id = ? AND status = 'waitlist'
               ORDER BY registered_at ASC""",
            (event_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_event_registered_user_ids(event_id: int) -> list[int]:
    """Get user IDs of all registered (not waitlisted, not cancelled) users."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id FROM registrations WHERE event_id = ? AND status = 'registered'",
            (event_id,),
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


# ── Broadcasts ──────────────────────────────────────────────────────

async def save_broadcast(event_id: int | None, message: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO broadcasts (event_id, message) VALUES (?, ?)",
            (event_id, message),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]
