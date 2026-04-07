# Architecture Specification — Siemens Room Bookings MCP Server

## Overview

A Python MCP Server built with **FastMCP**, backed by **SQLite**, exposing meeting room management tools to Claude Code, GitHub Copilot, or any MCP-compatible client via the stdio transport.

> **Spec-Driven Development note:** This document is the source of truth for project structure and module contracts.  
> No code is written without a corresponding spec entry.

---

## Project Structure

```
Siemens-room-bookings/
├── specs/                        ← All specs (written before code)
│   ├── architecture.md           ← This file
│   ├── mcp_tools.md              ← MCP tool API contracts
│   └── database_schema.md        ← DB schema + seed data
│
├── src/
│   └── mcp_server/               ← Installable Python package
│       ├── __init__.py
│       ├── database.py           ← All SQLite logic. No SQL outside this file.
│       ├── models.py             ← Pydantic models (shared across tools)
│       ├── server.py             ← FastMCP entry point. Registers all tools.
│       └── tools/
│           ├── __init__.py
│           ├── rooms.py          ← list_available_rooms, get_room_details
│           ├── bookings.py       ← book_room, cancel_booking, get_my_bookings
│           ├── availability.py   ← check_room_availability
│           └── admin.py          ← reset_database (password-protected)
│
├── db/
│   └── schema.sql                ← DDL only (no data). Read by database.py at startup.
│
├── scripts/
│   └── seed_db.py                ← Inserts seed data (rooms + sample bookings). Run once.
│
├── data/
│   └── bookings.db               ← SQLite file (git-ignored)
│
├── tests/
│   ├── conftest.py               ← Shared fixtures (in-memory DB, test client)
│   ├── test_database.py          ← Unit tests for database.py functions
│   └── test_tools.py             ← Integration tests for MCP tools
│
├── .vscode/
│   └── mcp.json                  ← VS Code / GitHub Copilot integration
│
└── pyproject.toml                ← Package config + dependencies
```

---

## Layer Responsibilities

```
┌─────────────────────────────────┐
│         MCP Client              │  Claude Code / GitHub Copilot / CLI
│   (Claude Code / Copilot)       │
└────────────┬────────────────────┘
             │ JSON-RPC over stdio
┌────────────▼────────────────────┐
│         server.py               │  FastMCP instance. Registers tools.
│                                 │  No business logic here.
└────────────┬────────────────────┘
             │ function calls
┌────────────▼────────────────────┐
│     tools/ (rooms, bookings,    │  Business logic + input validation.
│            availability)        │  Returns dicts. Uses models.py.
└────────────┬────────────────────┘
             │ function calls
┌────────────▼────────────────────┐
│         database.py             │  All SQL. Connection management.
│                                 │  Returns dicts (sqlite3.Row → dict).
└────────────┬────────────────────┘
             │ reads schema
┌────────────▼────────────────────┐
│         schema.sql              │  DDL only. CREATE TABLE, indexes.
└─────────────────────────────────┘
```

**Rules:**
- SQL lives **only** in `database.py` and `schema.sql`. Never in tools.
- Business logic (validation, error messages, conflict resolution) lives **only** in `tools/`.
- `server.py` only registers tools — no logic.
- `models.py` is shared — imported by tools, not by database.py.

---

## Module Contracts

### `schema.sql`

Contains all `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS` statements.  
No seed data. No `DROP`. Idempotent — safe to run multiple times.  
Full DDL defined in `specs/database_schema.md`.

---

### `database.py`

**Configuration:**
```python
PROJECT_ROOT = Path(__file__).parent.parent.parent
DB_PATH      = PROJECT_ROOT / "data" / "bookings.db"
SCHEMA_PATH  = PROJECT_ROOT / "db" / "schema.sql"
```

**Public API:**

| Function | Parameters | Returns | Description |
|----------|-----------|---------|-------------|
| `init_db()` | — | `None` | Reads schema.sql, creates tables. Safe to call on every startup. |
| `get_rooms(...)` | `min_capacity, required_features, preferred_floor, start_time, end_time` | `list[dict]` | Rooms matching all filters. Excludes rooms with overlapping bookings when times given. |
| `get_room_by_id(room_id)` | `int` | `dict \| None` | Single room with features, or None. |
| `get_upcoming_bookings_for_room(room_id)` | `int` | `list[dict]` | Next 10 bookings for room (from now). |
| `get_overlapping_bookings(room_id, start_time, end_time)` | `int, str, str` | `list[dict]` | Bookings that overlap the window. Empty = available. |
| `create_booking(room_id, booked_by, title, start_time, end_time)` | — | `int` | Inserts booking, returns new `booking_id`. |
| `get_booking_by_id(booking_id)` | `int` | `dict \| None` | Booking with room name, or None. |
| `delete_booking(booking_id)` | `int` | `None` | Deletes booking row. |
| `get_bookings_by_user(booked_by, from_date, to_date)` | `str, str, str \| None` | `list[dict]` | User's bookings from date onwards. |
| `create_room(name, floor, capacity, description, features)` | `str, int, int, str \| None, list[str]` | `int` | Inserts room + features, returns new `room_id`. |
| `delete_room(room_id)` | `int` | `None` | Deletes room row (cascades to room_features and bookings). |

**Return shape for room dict:**
```python
{
    "id": int, "name": str, "floor": int,
    "capacity": int, "features": list[str], "description": str | None
}
```

**Return shape for booking dict:**
```python
{
    "id": int, "room_id": int, "room_name": str, "floor": int,
    "booked_by": str, "title": str, "start_time": str, "end_time": str
}
```

---

### `models.py`

Pydantic v2 models used for **output validation** in tools. Not used by `database.py`.

| Model | Fields | Used by |
|-------|--------|---------|
| `Room` | `id, name, floor, capacity, features, description` | `list_available_rooms`, `get_room_details` |
| `BookingSummary` | `booking_id, title, booked_by, start_time, end_time` | inside `RoomDetail` |
| `RoomDetail` | `Room` + `upcoming_bookings: list[BookingSummary]` | `get_room_details` |
| `BookingResult` | `booking_id, room_id, room_name, floor, title, booked_by, start_time, end_time` | `book_room`, `get_my_bookings` |

---

### `tools/rooms.py`

```python
def list_available_rooms(
    min_capacity: int,
    required_features: list[str] | None = None,
    preferred_floor: int | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict]: ...

def get_room_details(room_id: int) -> dict: ...
```

---

### `tools/bookings.py`

```python
def book_room(
    room_id: int,
    booked_by: str,
    title: str,
    start_time: str,
    end_time: str,
) -> dict: ...
# On conflict: returns error + list of alternative available rooms

def cancel_booking(booking_id: int, booked_by: str) -> dict: ...

def get_my_bookings(
    booked_by: str,
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[dict]: ...
```

---

### `tools/availability.py`

```python
def check_room_availability(
    room_id: int,
    start_time: str,
    end_time: str,
) -> dict: ...
```

---

### `server.py`

```python
mcp = FastMCP(
    name="Siemens Room Bookings",
    instructions="..."  # Shown to the LLM as system context
)

# Register all tools (imported from tools/)
# Register rooms://catalog resource (room list as background context)

if __name__ == "__main__":
    init_db()   # Ensure DB exists on startup
    mcp.run()   # stdio transport
```

---

## Error Handling Convention

All tools return a plain `dict`. On success:
```json
{ "success": true, ... }
```

On error:
```json
{ "error": "Human-readable message explaining what went wrong" }
```

Tools **never raise exceptions** to the MCP layer — all errors are caught and returned as `{"error": "..."}`.

---

## Input Validation Convention

Validated in tools (not in database.py):

| Validation | Where | Error message |
|-----------|-------|---------------|
| `start_time < end_time` | All time-taking tools | `"start_time must be before end_time"` |
| `start_time` not in the past | `book_room` | `"Cannot book a room in the past"` |
| Room exists | `book_room`, `get_room_details`, `check_room_availability` | `"Room with id {id} not found"` |
| Booking exists | `cancel_booking` | `"Booking with id {id} not found"` |
| Ownership check | `cancel_booking` | `"You are not authorized to cancel this booking"` |

---

## Configuration

| Setting | Value | Source |
|---------|-------|--------|
| DB path | `data/bookings.db` | Hardcoded in `database.py` via `Path(__file__)` |
| Transport | stdio | `mcp.run()` default |
| Log target | stderr | `logging.basicConfig(stream=sys.stderr)` |

---

## Integration

### Install (one-time):
```bash
pip install -e ".[dev]"
python scripts/seed_db.py
```

### Run via Claude Code:
```bash
claude mcp add --scope user --transport stdio room-bookings "c:/path/to/venv/Scripts/python" "c:/path/to/src/mcp_server/server.py"
```

### VS Code / GitHub Copilot — `.vscode/mcp.json`:
```json
{
  "servers": {
    "room-bookings": {
      "command": "${workspaceFolder}/venv/Scripts/python",
      "args": ["-m", "mcp_server.server"],
      "env": { "PYTHONPATH": "${workspaceFolder}/src" }
    }
  }
}
```
