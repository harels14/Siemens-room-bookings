"""
Seed script — creates the database and inserts demo data.

Run once after installation:
    python scripts/seed_db.py

Drops and recreates bookings.db on every run.
Seed data defined in: specs/database_schema.md → Seed Data section.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Allow imports from src/ without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcp_server.database import DB_PATH, get_connection, init_db

# ---------------------------------------------------------------------------
# Rooms — 8 rooms across 4 floors (from specs/database_schema.md)
# ---------------------------------------------------------------------------

ROOMS = [
    {"name": "Curie",    "floor": 1, "capacity": 4,  "description": "Quiet room, ideal for 1:1s"},
    {"name": "Darwin",   "floor": 1, "capacity": 6,  "description": "Ground floor, easy access"},
    {"name": "Einstein", "floor": 2, "capacity": 10, "description": "Corner room with natural light"},
    {"name": "Feynman",  "floor": 2, "capacity": 8,  "description": "Whiteboard wall, great for workshops"},
    {"name": "Lovelace", "floor": 3, "capacity": 12, "description": "Fully equipped, best for client meetings"},
    {"name": "Newton",   "floor": 3, "capacity": 6,  "description": "Cozy, good acoustics for calls"},
    {"name": "Turing",   "floor": 4, "capacity": 20, "description": "Main conference room, all amenities"},
    {"name": "Tesla",    "floor": 4, "capacity": 16, "description": "Open layout, flexible seating"},
]

FEATURES = ["projector", "whiteboard", "video_conferencing", "tv_screen"]

# room_name → list of features  (from specs/database_schema.md → Rooms table)
ROOM_FEATURES = {
    "Curie":    ["whiteboard"],
    "Darwin":   ["projector", "whiteboard"],
    "Einstein": ["projector", "whiteboard", "video_conferencing"],
    "Feynman":  ["projector", "tv_screen"],
    "Lovelace": ["projector", "whiteboard", "video_conferencing", "tv_screen"],
    "Newton":   ["whiteboard", "video_conferencing"],
    "Turing":   ["projector", "whiteboard", "video_conferencing", "tv_screen"],
    "Tesla":    ["projector", "video_conferencing", "tv_screen"],
}


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def seed(verbose: bool = True) -> None:
    # Drop and recreate the DB file for a clean slate
    if DB_PATH.exists():
        DB_PATH.unlink()
        if verbose:
            print(f"Removed existing database: {DB_PATH}")

    init_db()
    if verbose:
        print(f"Initialised database: {DB_PATH}")

    with get_connection() as conn:
        # Insert features
        for feature in FEATURES:
            conn.execute("INSERT INTO features (name) VALUES (?)", [feature])

        feature_ids: dict[str, int] = {
            row["name"]: row["id"]
            for row in conn.execute("SELECT id, name FROM features").fetchall()
        }

        # Insert rooms + room_features
        for room in ROOMS:
            cursor = conn.execute(
                "INSERT INTO rooms (name, floor, capacity, description) VALUES (?, ?, ?, ?)",
                [room["name"], room["floor"], room["capacity"], room["description"]],
            )
            room_id = cursor.lastrowid
            for feat_name in ROOM_FEATURES[room["name"]]:
                conn.execute(
                    "INSERT INTO room_features (room_id, feature_id) VALUES (?, ?)",
                    [room_id, feature_ids[feat_name]],
                )

        # Fetch room name→id map for bookings
        room_ids: dict[str, int] = {
            row["name"]: row["id"]
            for row in conn.execute("SELECT id, name FROM rooms").fetchall()
        }

        # --- Sample bookings (from specs/database_schema.md → Sample bookings) ---
        tomorrow = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        next_monday = tomorrow + timedelta(days=(7 - tomorrow.weekday()) % 7 or 7)
        today = datetime.now().replace(second=0, microsecond=0)

        sample_bookings = [
            # Einstein booked tomorrow morning — good for demoing conflict detection
            {
                "room_id": room_ids["Einstein"],
                "booked_by": "alice@siemens.com",
                "title": "Sprint Review",
                "start_time": _iso(tomorrow.replace(hour=9, minute=30)),
                "end_time":   _iso(tomorrow.replace(hour=10, minute=30)),
            },
            # Turing booked next Monday afternoon
            {
                "room_id": room_ids["Turing"],
                "booked_by": "bob@siemens.com",
                "title": "All-Hands Meeting",
                "start_time": _iso(next_monday.replace(hour=14, minute=0)),
                "end_time":   _iso(next_monday.replace(hour=16, minute=0)),
            },
            # Curie booked today (later today) — for get_my_bookings demo
            {
                "room_id": room_ids["Curie"],
                "booked_by": "harel@siemens.com",
                "title": "1:1 with Manager",
                "start_time": _iso((today + timedelta(hours=2)).replace(minute=0, second=0)),
                "end_time":   _iso((today + timedelta(hours=2, minutes=30)).replace(minute=30, second=0)),
            },
        ]

        for b in sample_bookings:
            conn.execute(
                "INSERT INTO bookings (room_id, booked_by, title, start_time, end_time) "
                "VALUES (:room_id, :booked_by, :title, :start_time, :end_time)",
                b,
            )

    if verbose:
        print(f"\nSeeded {len(ROOMS)} rooms, {len(FEATURES)} features, {len(sample_bookings)} bookings.")
        print("\nRooms:")
        for room in ROOMS:
            feats = ", ".join(ROOM_FEATURES[room["name"]])
            print(f"  [{room['floor']}F] {room['name']:<10} {room['capacity']:>2} seats  {feats}")
        print("\nSample bookings:")
        for b in sample_bookings:
            print(f"  {b['title']:<25} {b['start_time']} -> {b['end_time']}  ({b['booked_by']})")
        print("\nReady. Run the MCP server with:")
        print("  python -m mcp_server.server")


if __name__ == "__main__":
    seed()
