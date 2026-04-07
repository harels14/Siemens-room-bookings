-- Room Bookings Schema
-- Idempotent: safe to run multiple times (IF NOT EXISTS on all objects).
-- No seed data here — see scripts/seed_db.py.
-- Spec: specs/database_schema.md

CREATE TABLE IF NOT EXISTS rooms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    floor       INTEGER NOT NULL,
    capacity    INTEGER NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS features (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT    NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS room_features (
    room_id    INTEGER NOT NULL REFERENCES rooms(id)    ON DELETE CASCADE,
    feature_id INTEGER NOT NULL REFERENCES features(id) ON DELETE CASCADE,
    PRIMARY KEY (room_id, feature_id)
);

CREATE TABLE IF NOT EXISTS bookings (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id    INTEGER NOT NULL REFERENCES rooms(id),
    booked_by  TEXT    NOT NULL,
    title      TEXT    NOT NULL,
    start_time TEXT    NOT NULL,  -- ISO 8601 local datetime e.g. '2026-04-12T10:00:00'
    end_time   TEXT    NOT NULL,  -- ISO 8601 local datetime e.g. '2026-04-12T11:00:00'
    created_at TEXT    DEFAULT (datetime('now'))
);

-- Fast overlap check: WHERE room_id=? AND start_time < ? AND end_time > ?
CREATE INDEX IF NOT EXISTS idx_bookings_room_time
    ON bookings (room_id, start_time, end_time);

-- Fast user lookup: WHERE booked_by=?
CREATE INDEX IF NOT EXISTS idx_bookings_user
    ON bookings (booked_by);
