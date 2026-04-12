"""
SQLite database layer.

Rules (from specs/architecture.md):
- All SQL lives here. No SQL in tools/.
- Returns plain dicts (sqlite3.Row converted). No Pydantic here.
- get_connection() is the only place a connection is opened.
"""

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_PATH      = PROJECT_ROOT / "data" / "bookings.db"
SCHEMA_PATH  = PROJECT_ROOT / "db" / "schema.sql"


@contextmanager
def get_connection():
    """Yields a committed-or-rolled-back SQLite connection."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Creates all tables and indexes from schema.sql. Safe to call on every startup."""
    with get_connection() as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    logger.info("Database ready at %s", DB_PATH)


# ---------------------------------------------------------------------------
# Rooms
# ---------------------------------------------------------------------------

def get_rooms(
    min_capacity: int,
    required_features: list[str] | None = None,
    preferred_floor: int | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict]:
    """
    Returns rooms matching all filters.
    Excludes rooms with overlapping bookings when start_time/end_time are given.
    Feature filtering is done in Python (simpler than dynamic SQL for AND-all logic).
    """
    params: list = [min_capacity]

    sql = """
        SELECT
            r.id, r.name, r.floor, r.capacity, r.description,
            COALESCE(GROUP_CONCAT(f.name), '') AS features
        FROM rooms r
        LEFT JOIN room_features rf ON r.id = rf.room_id
        LEFT JOIN features f       ON rf.feature_id = f.id
        WHERE r.capacity >= ?
    """

    if preferred_floor is not None:
        sql += " AND r.floor = ?"
        params.append(preferred_floor)

    if start_time and end_time:
        sql += """
            AND r.id NOT IN (
                SELECT room_id FROM bookings
                WHERE start_time < ? AND end_time > ?
            )
        """
        params.extend([end_time, start_time])

    sql += " GROUP BY r.id ORDER BY r.floor, r.capacity"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    rooms = []
    for row in rows:
        room_features = [f for f in row["features"].split(",") if f]
        if required_features and not all(f in room_features for f in required_features):
            continue
        rooms.append(_room_row_to_dict(row, room_features))

    return rooms


def get_room_by_id(room_id: int) -> dict | None:
    """Returns a single room dict with features list, or None if not found."""
    with get_connection() as conn:
        row = conn.execute("""
            SELECT
                r.id, r.name, r.floor, r.capacity, r.description,
                COALESCE(GROUP_CONCAT(f.name), '') AS features
            FROM rooms r
            LEFT JOIN room_features rf ON r.id = rf.room_id
            LEFT JOIN features f       ON rf.feature_id = f.id
            WHERE r.id = ?
            GROUP BY r.id
        """, [room_id]).fetchone()

    if row is None:
        return None
    room_features = [f for f in row["features"].split(",") if f]
    return _room_row_to_dict(row, room_features)


def get_upcoming_bookings_for_room(room_id: int, limit: int = 10) -> list[dict]:
    """Returns the next `limit` bookings for a room, from now onwards."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, title, booked_by, start_time, end_time
            FROM bookings
            WHERE room_id = ? AND end_time > datetime('now')
            ORDER BY start_time
            LIMIT ?
        """, [room_id, limit]).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------

def get_overlapping_bookings(
    room_id: int,
    start_time: str,
    end_time: str,
) -> list[dict]:
    """
    Returns bookings on room_id that overlap [start_time, end_time).
    Overlap condition: existing.start < new.end AND existing.end > new.start
    Empty list means the room is free.
    """
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT id, title, booked_by, start_time, end_time
            FROM bookings
            WHERE room_id = ?
              AND start_time < ?
              AND end_time   > ?
        """, [room_id, end_time, start_time]).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Bookings
# ---------------------------------------------------------------------------

def create_booking(
    room_id: int,
    booked_by: str,
    title: str,
    start_time: str,
    end_time: str,
) -> int:
    """Inserts a new booking and returns its ID."""
    with get_connection() as conn:
        cursor = conn.execute("""
            INSERT INTO bookings (room_id, booked_by, title, start_time, end_time)
            VALUES (?, ?, ?, ?, ?)
        """, [room_id, booked_by, title, start_time, end_time])
        return cursor.lastrowid


def get_booking_by_id(booking_id: int) -> dict | None:
    """Returns a booking dict with room name and floor, or None if not found."""
    with get_connection() as conn:
        row = conn.execute("""
            SELECT b.id, b.room_id, r.name AS room_name, r.floor,
                   b.booked_by, b.title, b.start_time, b.end_time
            FROM bookings b
            JOIN rooms r ON b.room_id = r.id
            WHERE b.id = ?
        """, [booking_id]).fetchone()
    return dict(row) if row else None


def delete_booking(booking_id: int) -> None:
    """Deletes a booking by ID."""
    with get_connection() as conn:
        conn.execute("DELETE FROM bookings WHERE id = ?", [booking_id])


def get_bookings_by_user(
    booked_by: str,
    from_date: str,
    to_date: str | None = None,
) -> list[dict]:
    """Returns all bookings for a user from from_date onwards, sorted by start_time."""
    sql = """
        SELECT b.id, b.room_id, r.name AS room_name, r.floor,
               b.title, b.booked_by, b.start_time, b.end_time
        FROM bookings b
        JOIN rooms r ON b.room_id = r.id
        WHERE b.booked_by = ? AND b.start_time >= ?
    """
    params: list = [booked_by, from_date]

    if to_date:
        sql += " AND b.start_time <= ?"
        params.append(to_date + "T23:59:59")

    sql += " ORDER BY b.start_time"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def get_all_bookings_in_range(start_time: str, end_time: str) -> list[dict]:
    """Returns all bookings across all rooms that overlap [start_time, end_time), sorted by start_time."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT b.id, b.room_id, r.name AS room_name, r.floor,
                   b.title, b.booked_by, b.start_time, b.end_time
            FROM bookings b
            JOIN rooms r ON b.room_id = r.id
            WHERE b.start_time < ? AND b.end_time > ?
            ORDER BY b.start_time, r.floor
        """, [end_time, start_time]).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

def clear_all_bookings() -> int:
    """Deletes all rows from the bookings table. Returns number of deleted rows."""
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM bookings")
        return cursor.rowcount


def create_room(
    name: str,
    floor: int,
    capacity: int,
    description: str | None,
    features: list[str],
) -> int:
    """
    Inserts a new room with its features. Returns the new room_id.

    Features that don't exist in the features table are inserted automatically.
    Not exposed as an MCP tool — intended for scripts and admin use only.
    """
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO rooms (name, floor, capacity, description) VALUES (?, ?, ?, ?)",
            [name, floor, capacity, description],
        )
        room_id = cursor.lastrowid

        for feature_name in features:
            conn.execute(
                "INSERT OR IGNORE INTO features (name) VALUES (?)",
                [feature_name],
            )
            row = conn.execute(
                "SELECT id FROM features WHERE name = ?", [feature_name]
            ).fetchone()
            conn.execute(
                "INSERT OR IGNORE INTO room_features (room_id, feature_id) VALUES (?, ?)",
                [room_id, row["id"]],
            )

    return room_id


def delete_room(room_id: int) -> None:
    """
    Deletes a room by ID. Cascades to room_features and bookings.

    Not exposed as an MCP tool — intended for scripts and admin use only.
    """
    with get_connection() as conn:
        conn.execute("DELETE FROM rooms WHERE id = ?", [room_id])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _room_row_to_dict(row: sqlite3.Row, features: list[str]) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "floor": row["floor"],
        "capacity": row["capacity"],
        "features": features,
        "description": row["description"],
    }
