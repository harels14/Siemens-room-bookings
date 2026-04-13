# Siemens Room Bookings — MCP Server

An MCP (Model Context Protocol) server for managing meeting room bookings, built with **FastMCP** and **SQLite**.  
Integrates natively with **Claude Code**, **GitHub Copilot (VS Code)**, and any MCP-compatible client.

---

## What It Does

Instead of opening a booking portal, you ask your AI assistant in plain English:

> *"Find me a room for 10 people with a projector tomorrow at 2pm"*  
> *"Book Einstein for the team standup tomorrow 9–9:30am"*  
> *"Show me all my bookings this week"*

The AI calls the MCP tools automatically and handles the details.

---

## Architecture

This project follows **Spec-Driven Development** — all specs were written before any code.

```
specs/
├── architecture.md       ← module structure & internal API contracts
├── mcp_tools.md          ← full API spec for all 7 MCP tools
└── database_schema.md    ← DB schema, indexes, seed data

src/mcp_server/
├── database.py           ← all SQL lives here
├── models.py             ← Pydantic output models
├── server.py             ← FastMCP entry point
└── tools/
    ├── rooms.py          ← list_available_rooms, get_room_details
    ├── bookings.py       ← book_room, cancel_booking, get_my_bookings
    ├── availability.py   ← check_room_availability
    └── admin.py          ← reset_database (password-protected)

db/
└── schema.sql            ← DDL only (no seed data)

tests/
├── conftest.py           ← shared fixtures
├── test_database.py      ← unit tests for database.py
└── test_tools.py         ← integration tests for MCP tools
```

```
MCP Client (Claude / Copilot)
        │  JSON-RPC over stdio
    server.py  ←  registers tools + rooms://catalog resource
        │
    tools/     ←  business logic + input validation
        │
    database.py  ←  all SQL queries
        │
    schema.sql + bookings.db
```

---

## Setup

**Requirements:** Python 3.12+

```bash
# 1. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# 2. Install the package
pip install -e ".[dev]"

# 3. Configure environment
copy .env.example .env         # then edit .env with your admin password

# 4. Seed the database (8 rooms, sample bookings)
python scripts/seed_db.py
```

---

## Docker

Without Docker, Claude Code stores the absolute path to `server.py` on your machine in `~/.claude.json`. If you move the project folder, the connection breaks — and sharing with teammates requires them to install Python 3.12, create a venv, and run `pip install`.

With Docker, the image contains everything (Python, code, dependencies). Claude Code just runs `docker run ...` — no paths, no local setup required. The image can also be pushed to Docker Hub and pulled by anyone on the team.

### Build

```bash
docker build -t siemens-room-bookings .
```

### Run (standalone test)

```bash
# First run: seeds the DB automatically and starts the server
docker run -i --rm -v room-bookings-data:/app/data siemens-room-bookings

# Force re-seed (resets all bookings + reloads sample data)
docker run -i --rm -e SEED_DB=1 -v room-bookings-data:/app/data siemens-room-bookings
```

The `-i` flag keeps stdin open — required because the MCP server communicates over stdio.  
The named volume `room-bookings-data` persists the SQLite database across container restarts.

### Integrate with Claude Code (Docker)

```bash
claude mcp add --scope user --transport stdio room-bookings \
    docker run -i --rm -v room-bookings-data:/app/data siemens-room-bookings
```

Or add manually to `~/.claude/claude_code_config.json`:

```json
{
  "mcpServers": {
    "room-bookings": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "-v", "room-bookings-data:/app/data", "siemens-room-bookings"]
    }
  }
}
```

---

## Integration

### Claude Code (CLI — local Python)

```bash
claude mcp add --scope user --transport stdio room-bookings "c:/path/to/venv/Scripts/python" "c:/path/to/src/mcp_server/server.py"
```

### VS Code / GitHub Copilot

The `.vscode/mcp.json` is already configured. Open the project in VS Code — Copilot Chat will automatically detect the server.

---

## Available Tools

| Tool | Description |
|------|-------------|
| `list_available_rooms` | Search by capacity, equipment, floor, and time window |
| `book_room` | Reserve a room — returns alternatives if already taken |
| `cancel_booking` | Cancel your own booking |
| `check_room_availability` | Check if a specific room is free in a given window |
| `get_room_details` | Full room info + upcoming bookings |
| `get_my_bookings` | All your upcoming reservations |
| `reset_database` | Clear all bookings (requires admin password from `.env`) |

Full API contracts in [`specs/mcp_tools.md`](specs/mcp_tools.md).

---

## Demo

### Find and book a room

```
You:     Find me a room for 8 people with video conferencing, free tomorrow 10–11am

Claude:  [calls list_available_rooms(min_capacity=8, required_features=["video_conferencing"],
                                     start_time="...", end_time="...")]

         Available rooms:
         • Einstein (floor 2, 10 seats) — projector, whiteboard, video_conferencing
         • Newton   (floor 3, 6 seats)  — whiteboard, video_conferencing
         • Turing   (floor 4, 20 seats) — fully equipped

         Want me to book one?

You:     Book Einstein for harel@siemens.com, "Product Review"

Claude:  [calls book_room(room_id=3, booked_by="harel@siemens.com",
                          title="Product Review", start_time="...", end_time="...")]

         Done! Einstein booked for harel@siemens.com — "Product Review"
         tomorrow 10:00–11:00. Booking #7.
```

### Conflict detection with alternatives

```
You:     Book Einstein tomorrow 9:30–10:00

Claude:  Einstein is already booked during that time (Sprint Review, alice@siemens.com).

         Available alternatives with similar capacity:
         • Lovelace (floor 3, 12 seats) — fully equipped
         • Tesla    (floor 4, 16 seats) — projector, video_conferencing
         • Turing   (floor 4, 20 seats) — fully equipped

         Want me to book one of these instead?
```

### Check your schedule

```
You:     Show me my bookings this week

Claude:  [calls get_my_bookings(booked_by="harel@siemens.com", from_date="...")]

         Your upcoming bookings:
         • Today 15:00–15:30  — Curie (floor 1) — "1:1 with Manager"
         • Mon   10:00–11:00  — Einstein (floor 2) — "Product Review"
```

---

## Rooms

| Room | Floor | Seats | Equipment |
|------|-------|-------|-----------|
| Curie | 1 | 4 | whiteboard |
| Darwin | 1 | 6 | projector, whiteboard |
| Einstein | 2 | 10 | projector, whiteboard, video_conferencing |
| Feynman | 2 | 8 | projector, tv_screen |
| Lovelace | 3 | 12 | projector, whiteboard, video_conferencing, tv_screen |
| Newton | 3 | 6 | whiteboard, video_conferencing |
| Tesla | 4 | 16 | projector, video_conferencing, tv_screen |
| Turing | 4 | 20 | projector, whiteboard, video_conferencing, tv_screen |

---

## Development

```bash
# Run tests
pytest

# Re-seed database (resets all bookings + re-inserts sample data)
python scripts/seed_db.py

# Run server directly (stdio)
python src/mcp_server/server.py
```

## Demo Reset

To clear all bookings between demo sessions without re-seeding:

```
You: Reset the database  (password: <your MCP_ADMIN_PASSWORD>)
```

To restore sample data:

```bash
python scripts/seed_db.py
```
