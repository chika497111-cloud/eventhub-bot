import aiosqlite
import logging
import string
import random
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "eventhub.db"
logger = logging.getLogger(__name__)


def _generate_checkin_code(length: int = 6) -> str:
    """Generate a random alphanumeric check-in code."""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=length))


async def init_db() -> None:
    """Create tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        # --- Categories ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                emoji TEXT NOT NULL DEFAULT '',
                sort_order INTEGER NOT NULL DEFAULT 0
            )
        """)

        # --- Events (expanded) ---
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
                category_id INTEGER,
                recurrence_type TEXT,
                recurrence_parent_id INTEGER,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (category_id) REFERENCES categories(id),
                FOREIGN KEY (recurrence_parent_id) REFERENCES events(id)
            )
        """)

        # --- Ticket types ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL DEFAULT 0,
                max_count INTEGER NOT NULL,
                sold_count INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (event_id) REFERENCES events(id)
            )
        """)

        # --- Registrations (expanded) ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT,
                registered_at TEXT NOT NULL DEFAULT (datetime('now')),
                status TEXT NOT NULL DEFAULT 'registered',
                checkin_code TEXT,
                ticket_type_id INTEGER,
                FOREIGN KEY (event_id) REFERENCES events(id),
                FOREIGN KEY (ticket_type_id) REFERENCES ticket_types(id),
                UNIQUE(event_id, user_id)
            )
        """)

        # --- Reviews ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
                comment TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (event_id) REFERENCES events(id),
                UNIQUE(event_id, user_id)
            )
        """)

        # --- Event photos ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS event_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                photo_id TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (event_id) REFERENCES events(id)
            )
        """)

        # --- Broadcasts ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                message TEXT NOT NULL,
                sent_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        await db.commit()

        # --- Migrate existing tables (add columns if missing) ---
        await _migrate(db)

    logger.info("Database initialized")


async def _migrate(db: aiosqlite.Connection) -> None:
    """Add new columns to existing tables if they are missing."""
    # Check events columns
    cursor = await db.execute("PRAGMA table_info(events)")
    event_cols = {row[1] for row in await cursor.fetchall()}

    if "category_id" not in event_cols:
        await db.execute("ALTER TABLE events ADD COLUMN category_id INTEGER")
    if "recurrence_type" not in event_cols:
        await db.execute("ALTER TABLE events ADD COLUMN recurrence_type TEXT")
    if "recurrence_parent_id" not in event_cols:
        await db.execute("ALTER TABLE events ADD COLUMN recurrence_parent_id INTEGER")

    # Check registrations columns
    cursor = await db.execute("PRAGMA table_info(registrations)")
    reg_cols = {row[1] for row in await cursor.fetchall()}

    if "checkin_code" not in reg_cols:
        await db.execute("ALTER TABLE registrations ADD COLUMN checkin_code TEXT")
    if "ticket_type_id" not in reg_cols:
        await db.execute("ALTER TABLE registrations ADD COLUMN ticket_type_id INTEGER")
    if "full_name" not in reg_cols:
        await db.execute("ALTER TABLE registrations ADD COLUMN full_name TEXT")

    await db.commit()


# ══════════════════════════════════════════════════════════════════════
# Categories
# ══════════════════════════════════════════════════════════════════════

async def create_category(name: str, emoji: str = "", sort_order: int = 0) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO categories (name, emoji, sort_order) VALUES (?, ?, ?)",
            (name, emoji, sort_order),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]


async def get_categories() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM categories ORDER BY sort_order, name")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_category(category_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def delete_category(category_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE events SET category_id = NULL WHERE category_id = ?", (category_id,))
        await db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        await db.commit()


# ══════════════════════════════════════════════════════════════════════
# Ticket Types
# ══════════════════════════════════════════════════════════════════════

async def create_ticket_type(event_id: int, name: str, price: float, max_count: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO ticket_types (event_id, name, price, max_count) VALUES (?, ?, ?, ?)",
            (event_id, name, price, max_count),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]


async def get_ticket_types(event_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM ticket_types WHERE event_id = ? ORDER BY price ASC",
            (event_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_ticket_type(ticket_type_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM ticket_types WHERE id = ?", (ticket_type_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def increment_ticket_sold(ticket_type_id: int) -> bool:
    """Increment sold count. Returns False if sold out."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT sold_count, max_count FROM ticket_types WHERE id = ?",
            (ticket_type_id,),
        )
        row = await cursor.fetchone()
        if not row or row[0] >= row[1]:
            return False
        await db.execute(
            "UPDATE ticket_types SET sold_count = sold_count + 1 WHERE id = ?",
            (ticket_type_id,),
        )
        await db.commit()
        return True


async def decrement_ticket_sold(ticket_type_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE ticket_types SET sold_count = MAX(0, sold_count - 1) WHERE id = ?",
            (ticket_type_id,),
        )
        await db.commit()


# ══════════════════════════════════════════════════════════════════════
# Events
# ══════════════════════════════════════════════════════════════════════

async def create_event(
    title: str,
    description: str,
    event_date: str,
    event_time: str,
    location: str,
    max_participants: int,
    photo_id: str | None = None,
    category_id: int | None = None,
    recurrence_type: str | None = None,
    recurrence_parent_id: int | None = None,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO events
               (title, description, date, time, location, max_participants,
                photo_id, category_id, recurrence_type, recurrence_parent_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, description, event_date, event_time, location,
             max_participants, photo_id, category_id, recurrence_type,
             recurrence_parent_id),
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


async def get_active_events_by_category(category_id: int, offset: int = 0, limit: int = 5) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM events
               WHERE status = 'active' AND category_id = ?
               ORDER BY date ASC, time ASC
               LIMIT ? OFFSET ?""",
            (category_id, limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def count_active_events_by_category(category_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM events WHERE status = 'active' AND category_id = ?",
            (category_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def search_events(query: str, offset: int = 0, limit: int = 10) -> list[dict]:
    """Search active events by title or description."""
    pattern = f"%{query}%"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM events
               WHERE status = 'active'
               AND (title LIKE ? OR description LIKE ?)
               ORDER BY date ASC, time ASC
               LIMIT ? OFFSET ?""",
            (pattern, pattern, limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def search_events_by_date_range(
    date_from: str, date_to: str, offset: int = 0, limit: int = 10
) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM events
               WHERE status = 'active' AND date >= ? AND date <= ?
               ORDER BY date ASC, time ASC
               LIMIT ? OFFSET ?""",
            (date_from, date_to, limit, offset),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_popular_events(limit: int = 10) -> list[dict]:
    """Events sorted by registration count (popularity)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT e.*, COUNT(r.id) as reg_count
               FROM events e
               LEFT JOIN registrations r ON e.id = r.event_id AND r.status = 'registered'
               WHERE e.status = 'active'
               GROUP BY e.id
               ORDER BY reg_count DESC
               LIMIT ?""",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


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
    allowed = {
        "title", "description", "date", "time", "location",
        "max_participants", "photo_id", "status", "category_id",
        "recurrence_type",
    }
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


async def get_completed_events_needing_review() -> list[dict]:
    """Get completed events that ended within the last 7 days."""
    cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM events
               WHERE status = 'completed' AND date >= ?
               ORDER BY date DESC""",
            (cutoff,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_recurring_completed_events() -> list[dict]:
    """Get completed recurring events that need a next occurrence created."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM events
               WHERE status = 'completed'
               AND recurrence_type IS NOT NULL
               AND recurrence_type != ''"""
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def has_next_occurrence(parent_id: int) -> bool:
    """Check if a recurring event already has a future occurrence."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT COUNT(*) FROM events
               WHERE recurrence_parent_id = ? AND status = 'active'""",
            (parent_id,),
        )
        row = await cursor.fetchone()
        return (row[0] if row else 0) > 0


# ══════════════════════════════════════════════════════════════════════
# Registrations
# ══════════════════════════════════════════════════════════════════════

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


async def register_user(
    event_id: int,
    user_id: int,
    username: str | None,
    full_name: str | None = None,
    ticket_type_id: int | None = None,
) -> str:
    """Register user for event.
    Returns 'registered', 'waitlist', 'already', 'event_not_found', or 'ticket_sold_out'.
    """
    event = await get_event(event_id)
    if not event or event["status"] != "active":
        return "event_not_found"

    # Check ticket availability
    if ticket_type_id:
        tt = await get_ticket_type(ticket_type_id)
        if tt and tt["sold_count"] >= tt["max_count"]:
            return "ticket_sold_out"

    existing = await get_user_registration(event_id, user_id)
    checkin_code = _generate_checkin_code()

    if existing:
        if existing["status"] in ("registered", "waitlist"):
            return "already"
        # Re-register after cancellation
        async with aiosqlite.connect(DB_PATH) as db:
            count = await get_registration_count(event_id)
            new_status = "registered" if count < event["max_participants"] else "waitlist"
            await db.execute(
                """UPDATE registrations
                   SET status = ?, registered_at = datetime('now'),
                       username = ?, full_name = ?, checkin_code = ?,
                       ticket_type_id = ?
                   WHERE id = ?""",
                (new_status, username, full_name, checkin_code,
                 ticket_type_id, existing["id"]),
            )
            await db.commit()
            if new_status == "registered" and ticket_type_id:
                await increment_ticket_sold(ticket_type_id)
            return new_status

    count = await get_registration_count(event_id)
    status = "registered" if count < event["max_participants"] else "waitlist"

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO registrations
               (event_id, user_id, username, full_name, status, checkin_code, ticket_type_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (event_id, user_id, username, full_name, status, checkin_code, ticket_type_id),
        )
        await db.commit()

    if status == "registered" and ticket_type_id:
        await increment_ticket_sold(ticket_type_id)

    return status


async def cancel_registration(event_id: int, user_id: int) -> dict | None:
    """Cancel registration, promote first waitlisted user. Returns promoted user dict or None."""
    # Get the registration to decrement ticket
    reg = await get_user_registration(event_id, user_id)
    if reg and reg.get("ticket_type_id") and reg["status"] == "registered":
        await decrement_ticket_sold(reg["ticket_type_id"])

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """UPDATE registrations SET status = 'cancelled'
               WHERE event_id = ? AND user_id = ?
               AND status IN ('registered', 'waitlist')""",
            (event_id, user_id),
        )
        await db.commit()

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
            if promoted.get("ticket_type_id"):
                await increment_ticket_sold(promoted["ticket_type_id"])
            return promoted
    return None


async def get_user_registrations(user_id: int) -> list[dict]:
    """Get all active registrations for a user, joined with event data."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT r.id as reg_id, r.status as reg_status, r.registered_at,
                      r.checkin_code, r.ticket_type_id,
                      e.id as event_id, e.title, e.date, e.time, e.location,
                      e.status as event_status
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
            """SELECT r.*, t.name as ticket_name, t.price as ticket_price
               FROM registrations r
               LEFT JOIN ticket_types t ON r.ticket_type_id = t.id
               WHERE r.event_id = ? AND r.status IN ('registered', 'attended')
               ORDER BY r.registered_at ASC""",
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


async def get_all_registered_user_ids(event_id: int) -> list[int]:
    """Get user IDs of registered + attended users."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id FROM registrations WHERE event_id = ? AND status IN ('registered', 'attended')",
            (event_id,),
        )
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


# ── Check-in ──────────────────────────────────────────────────────────

async def checkin_by_code(code: str) -> dict | None:
    """Check in a participant by their code. Returns registration+event info or None."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT r.*, e.title as event_title
               FROM registrations r
               JOIN events e ON r.event_id = e.id
               WHERE r.checkin_code = ? AND r.status = 'registered'""",
            (code.upper(),),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        result = dict(row)
        await db.execute(
            "UPDATE registrations SET status = 'attended' WHERE id = ?",
            (result["id"],),
        )
        await db.commit()
        return result


async def get_checkin_stats(event_id: int) -> dict:
    """Return check-in stats: registered, attended, total."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """SELECT status, COUNT(*) as cnt
               FROM registrations
               WHERE event_id = ? AND status IN ('registered', 'attended')
               GROUP BY status""",
            (event_id,),
        )
        rows = await cursor.fetchall()
        stats = {"registered": 0, "attended": 0}
        for row in rows:
            stats[row[0]] = row[1]
        stats["total"] = stats["registered"] + stats["attended"]
        return stats


# ══════════════════════════════════════════════════════════════════════
# Reviews
# ══════════════════════════════════════════════════════════════════════

async def create_review(event_id: int, user_id: int, rating: int, comment: str | None = None) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO reviews (event_id, user_id, rating, comment) VALUES (?, ?, ?, ?)",
            (event_id, user_id, rating, comment),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]


async def get_user_review(event_id: int, user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM reviews WHERE event_id = ? AND user_id = ?",
            (event_id, user_id),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_event_reviews(event_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM reviews WHERE event_id = ? ORDER BY created_at DESC",
            (event_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_event_avg_rating(event_id: int) -> float | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT AVG(rating), COUNT(*) FROM reviews WHERE event_id = ?",
            (event_id,),
        )
        row = await cursor.fetchone()
        if row and row[1] > 0:
            return round(row[0], 1)
        return None


# ══════════════════════════════════════════════════════════════════════
# Event Photos
# ══════════════════════════════════════════════════════════════════════

async def add_event_photo(event_id: int, photo_id: str, sort_order: int = 0) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO event_photos (event_id, photo_id, sort_order) VALUES (?, ?, ?)",
            (event_id, photo_id, sort_order),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]


async def get_event_photos(event_id: int) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM event_photos WHERE event_id = ? ORDER BY sort_order ASC",
            (event_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def count_event_photos(event_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM event_photos WHERE event_id = ?",
            (event_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


# ══════════════════════════════════════════════════════════════════════
# Broadcasts
# ══════════════════════════════════════════════════════════════════════

async def save_broadcast(event_id: int | None, message: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO broadcasts (event_id, message) VALUES (?, ?)",
            (event_id, message),
        )
        await db.commit()
        return cursor.lastrowid  # type: ignore[return-value]


# ══════════════════════════════════════════════════════════════════════
# User Profile / Analytics
# ══════════════════════════════════════════════════════════════════════

async def get_user_profile_stats(user_id: int) -> dict:
    """Get user profile statistics."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Events attended
        cursor = await db.execute(
            "SELECT COUNT(*) FROM registrations WHERE user_id = ? AND status = 'attended'",
            (user_id,),
        )
        attended = (await cursor.fetchone())[0]

        # Upcoming events
        now_date = datetime.now().strftime("%Y-%m-%d")
        cursor = await db.execute(
            """SELECT COUNT(*) FROM registrations r
               JOIN events e ON r.event_id = e.id
               WHERE r.user_id = ? AND r.status = 'registered'
               AND e.status = 'active' AND e.date >= ?""",
            (user_id, now_date),
        )
        upcoming = (await cursor.fetchone())[0]

        # Average rating given
        cursor = await db.execute(
            "SELECT AVG(rating), COUNT(*) FROM reviews WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        avg_rating = round(row[0], 1) if row[0] else None
        reviews_count = row[1]

        # Favorite category
        cursor = await db.execute(
            """SELECT c.name, c.emoji, COUNT(*) as cnt
               FROM registrations r
               JOIN events e ON r.event_id = e.id
               JOIN categories c ON e.category_id = c.id
               WHERE r.user_id = ? AND r.status IN ('registered', 'attended')
               GROUP BY c.id
               ORDER BY cnt DESC LIMIT 1""",
            (user_id,),
        )
        fav_row = await cursor.fetchone()
        favorite_category = f"{fav_row[1]} {fav_row[0]}" if fav_row else None

        # Total registrations
        cursor = await db.execute(
            "SELECT COUNT(*) FROM registrations WHERE user_id = ? AND status != 'cancelled'",
            (user_id,),
        )
        total_regs = (await cursor.fetchone())[0]

        return {
            "attended": attended,
            "upcoming": upcoming,
            "avg_rating": avg_rating,
            "reviews_count": reviews_count,
            "favorite_category": favorite_category,
            "total_registrations": total_regs,
        }


async def get_user_attended_events(user_id: int, limit: int = 10) -> list[dict]:
    """Get events the user has attended."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT e.*, r.status as reg_status
               FROM registrations r
               JOIN events e ON r.event_id = e.id
               WHERE r.user_id = ? AND r.status = 'attended'
               ORDER BY e.date DESC LIMIT ?""",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_user_upcoming_events(user_id: int) -> list[dict]:
    now_date = datetime.now().strftime("%Y-%m-%d")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT e.*, r.status as reg_status, r.checkin_code
               FROM registrations r
               JOIN events e ON r.event_id = e.id
               WHERE r.user_id = ? AND r.status = 'registered'
               AND e.status = 'active' AND e.date >= ?
               ORDER BY e.date ASC""",
            (user_id, now_date),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════════
# Admin Analytics
# ══════════════════════════════════════════════════════════════════════

async def get_analytics() -> dict:
    """Get overall analytics for admin."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Total events
        cursor = await db.execute("SELECT COUNT(*) FROM events")
        total_events = (await cursor.fetchone())[0]

        # Events by status
        cursor = await db.execute(
            "SELECT status, COUNT(*) FROM events GROUP BY status"
        )
        events_by_status = {row[0]: row[1] for row in await cursor.fetchall()}

        # Total registrations
        cursor = await db.execute(
            "SELECT COUNT(*) FROM registrations WHERE status IN ('registered', 'attended')"
        )
        total_registrations = (await cursor.fetchone())[0]

        # Attendance rate
        cursor = await db.execute(
            "SELECT COUNT(*) FROM registrations WHERE status = 'attended'"
        )
        total_attended = (await cursor.fetchone())[0]

        cursor = await db.execute(
            """SELECT COUNT(*) FROM registrations
               WHERE status IN ('registered', 'attended')
               AND event_id IN (SELECT id FROM events WHERE status = 'completed')"""
        )
        total_for_completed = (await cursor.fetchone())[0]
        attendance_rate = (
            round(total_attended / total_for_completed * 100, 1)
            if total_for_completed > 0
            else 0
        )

        # Popular categories
        cursor = await db.execute(
            """SELECT c.emoji, c.name, COUNT(r.id) as cnt
               FROM categories c
               JOIN events e ON e.category_id = c.id
               LEFT JOIN registrations r ON r.event_id = e.id AND r.status IN ('registered', 'attended')
               GROUP BY c.id
               ORDER BY cnt DESC
               LIMIT 5"""
        )
        popular_categories = [
            {"emoji": row[0], "name": row[1], "count": row[2]}
            for row in await cursor.fetchall()
        ]

        # Revenue by ticket type
        cursor = await db.execute(
            """SELECT t.name, SUM(t.price) as revenue, COUNT(r.id) as sold
               FROM ticket_types t
               JOIN registrations r ON r.ticket_type_id = t.id
               AND r.status IN ('registered', 'attended')
               GROUP BY t.name
               ORDER BY revenue DESC"""
        )
        revenue_by_type = [
            {"name": row[0], "revenue": row[1], "sold": row[2]}
            for row in await cursor.fetchall()
        ]

        return {
            "total_events": total_events,
            "events_by_status": events_by_status,
            "total_registrations": total_registrations,
            "total_attended": total_attended,
            "attendance_rate": attendance_rate,
            "popular_categories": popular_categories,
            "revenue_by_type": revenue_by_type,
        }


async def get_event_analytics(event_id: int) -> dict:
    """Get per-event analytics."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT status, COUNT(*) FROM registrations WHERE event_id = ? GROUP BY status",
            (event_id,),
        )
        status_counts = {row[0]: row[1] for row in await cursor.fetchall()}

        avg_rating = await get_event_avg_rating(event_id)
        reviews = await get_event_reviews(event_id)

        # Revenue
        cursor = await db.execute(
            """SELECT COALESCE(SUM(t.price), 0)
               FROM registrations r
               JOIN ticket_types t ON r.ticket_type_id = t.id
               WHERE r.event_id = ? AND r.status IN ('registered', 'attended')""",
            (event_id,),
        )
        revenue = (await cursor.fetchone())[0]

        return {
            "registered": status_counts.get("registered", 0),
            "attended": status_counts.get("attended", 0),
            "cancelled": status_counts.get("cancelled", 0),
            "waitlist": status_counts.get("waitlist", 0),
            "avg_rating": avg_rating,
            "reviews_count": len(reviews),
            "revenue": revenue,
        }


# ══════════════════════════════════════════════════════════════════════
# Events needing reminders
# ══════════════════════════════════════════════════════════════════════

async def get_events_for_reminder(hours_before: int) -> list[dict]:
    """Get active events happening in approximately `hours_before` hours."""
    now = datetime.now()
    target = now + timedelta(hours=hours_before)
    # Window: +/- 30 minutes
    window_start = (target - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M")
    window_end = (target + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM events
               WHERE status = 'active'
               AND (date || ' ' || time) >= ?
               AND (date || ' ' || time) <= ?""",
            (window_start, window_end),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════════
# CSV Export helper
# ══════════════════════════════════════════════════════════════════════

async def get_event_participants_for_export(event_id: int) -> list[dict]:
    """Get participants with ticket info for CSV export."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT r.user_id, r.username, r.full_name, r.status,
                      r.checkin_code, r.registered_at,
                      COALESCE(t.name, 'Без типа') as ticket_name,
                      COALESCE(t.price, 0) as ticket_price
               FROM registrations r
               LEFT JOIN ticket_types t ON r.ticket_type_id = t.id
               WHERE r.event_id = ? AND r.status != 'cancelled'
               ORDER BY r.registered_at ASC""",
            (event_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
