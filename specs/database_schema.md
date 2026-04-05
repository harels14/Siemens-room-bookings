# Database Schema Specification — Siemens Room Bookings

## Overview

The backing store is **SQLite** (`data/bookings.db`).  
SQLite was chosen for portability (zero setup, single file, ships with Python) while still supporting full SQL semantics.

> **Spec-Driven Development note:** This document is the source of truth for the data model.  
> The SQL DDL in `src/mcp_server/database.py` and seed data in `scripts/seed_db.py` must conform to this spec.

---

## Entity Relationship Diagram

```
rooms ─────────────────< room_features >──────────── features
  │  (1)                   (many-to-many)                (1)
  │
  │ (1-to-many)
  ▼
bookings
```

---

## Tables

### `rooms`

Represents a physical meeting room.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `INTEGER` | PK, AUTOINCREMENT | Unique room identifier |
| `name` | `TEXT` | NOT NULL, UNIQUE | Human-readable name (e.g. `"Einstein"`) |
| `floor` | `INTEGER` | NOT NULL | Floor number (1–4) |
| `capacity` | `INTEGER` | NOT NULL | Maximum number of people |
| `description` | `TEXT` | nullable | Free-text description |

```sql
CREATE TABLE rooms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    floor       INTEGER NOT NULL,
    capacity    INTEGER NOT NULL,
    description TEXT
);
```

---

### `features`

Lookup table of possible room equipment/amenities.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `INTEGER` | PK, AUTOINCREMENT | Unique feature identifier |
| `name` | `TEXT` | NOT NULL, UNIQUE | Feature key (lowercase, snake_case) |

**Seeded values:** `projector`, `whiteboard`, `video_conferencing`, `tv_screen`

```sql
CREATE TABLE features (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT    NOT NULL UNIQUE
);
```

---

### `room_features`

Junction table linking rooms to their features (many-to-many).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `room_id` | `INTEGER` | FK → `rooms.id`, CASCADE DELETE | Room reference |
| `feature_id` | `INTEGER` | FK → `features.id`, CASCADE DELETE | Feature reference |

```sql
CREATE TABLE room_features (
    room_id    INTEGER NOT NULL REFERENCES rooms(id)    ON DELETE CASCADE,
    feature_id INTEGER NOT NULL REFERENCES features(id) ON DELETE CASCADE,
    PRIMARY KEY (room_id, feature_id)
);
```

---

### `bookings`

Represents a single room reservation.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `INTEGER` | PK, AUTOINCREMENT | Unique booking identifier |
| `room_id` | `INTEGER` | NOT NULL, FK → `rooms.id` | The reserved room |
| `booked_by` | `TEXT` | NOT NULL | Name or email of the booker |
| `title` | `TEXT` | NOT NULL | Meeting title |
| `start_time` | `TEXT` | NOT NULL | ISO 8601 local datetime |
| `end_time` | `TEXT` | NOT NULL | ISO 8601 local datetime |
| `created_at` | `TEXT` | DEFAULT `datetime('now')` | Audit timestamp |

```sql
CREATE TABLE bookings (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id    INTEGER NOT NULL REFERENCES rooms(id),
    booked_by  TEXT    NOT NULL,
    title      TEXT    NOT NULL,
    start_time TEXT    NOT NULL,
    end_time   TEXT    NOT NULL,
    created_at TEXT    DEFAULT (datetime('now'))
);
```

---

## Indexes

```sql
-- Fast lookup by room + time (used in overlap check and availability query)
CREATE INDEX idx_bookings_room_time
    ON bookings(room_id, start_time, end_time);

-- Fast lookup by user (used in get_my_bookings)
CREATE INDEX idx_bookings_user
    ON bookings(booked_by);
```

---

## Constraints & Business Rules

### Double-booking prevention

Overlap check is done in application code before insert.  
Two bookings on the same room overlap when:

```
existing.start_time < new.end_time  AND  existing.end_time > new.start_time
```

This covers all overlap cases (partial, full containment, exact match).

### Booking in the past

`start_time` must be ≥ current datetime. Enforced at application layer (not DB).

### Authorization

`booked_by` is a plain string (no auth system). Cancellation requires the caller to supply the same `booked_by` value that was used when booking. This is intentionally simple for a demo.

---

## Seed Data

Defined in `scripts/seed_db.py`. Provides realistic demo data for 8 rooms across 4 floors.

### Rooms

| id | name | Floor | Capacity | Features |
|----|------|-------|----------|----------|
| 1 | Curie | 1 | 4 | whiteboard |
| 2 | Darwin | 1 | 6 | projector, whiteboard |
| 3 | Einstein | 2 | 10 | projector, whiteboard, video_conferencing |
| 4 | Feynman | 2 | 8 | projector, tv_screen |
| 5 | Lovelace | 3 | 12 | projector, whiteboard, video_conferencing, tv_screen |
| 6 | Newton | 3 | 6 | whiteboard, video_conferencing |
| 7 | Turing | 4 | 20 | projector, whiteboard, video_conferencing, tv_screen |
| 8 | Tesla | 4 | 16 | projector, video_conferencing, tv_screen |

### Sample bookings

Several pre-created bookings to demonstrate conflict detection:
- Einstein booked for "Sprint Review" (tomorrow 09:30–10:30)
- Turing booked for "All-Hands Meeting" (next Monday 14:00–16:00)
- Curie booked for "1:1 with Manager" (today 15:00–15:30)

---

## Migration Strategy

This project uses plain SQL DDL (no ORM migrations). Schema changes are applied by:
1. Updating this spec
2. Updating `src/mcp_server/database.py` → `init_db()`
3. Re-running `scripts/seed_db.py` (drops and recreates `data/bookings.db`)

For production use, a migration tool such as [Alembic](https://alembic.sqlalchemy.org/) would be introduced.
