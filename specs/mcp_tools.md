# MCP Tools Specification — Siemens Room Bookings

## Overview

This document defines the full API contract for the **Room Bookings MCP Server**.  
All tools are exposed via the [Model Context Protocol](https://modelcontextprotocol.io/) (stdio transport)  
and are available through Claude Code, GitHub Copilot, or any MCP-compatible client.

> **Spec-Driven Development note:** This spec is the source of truth.  
> Implementation in `src/mcp_server/tools/` must conform to the schemas defined here.

---

## Tools

### 1. `list_available_rooms`

Searches for meeting rooms that match capacity, equipment, and optional availability requirements.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `min_capacity` | `integer` | Yes | Minimum number of seats required |
| `required_features` | `string[]` | No | Equipment needed: `projector`, `whiteboard`, `video_conferencing`, `tv_screen` |
| `preferred_floor` | `integer` | No | Floor preference (1–4) |
| `start_time` | `string` (ISO 8601) | No | Start of desired time window, e.g. `2026-04-12T10:00:00` |
| `end_time` | `string` (ISO 8601) | No* | End of desired time window. Required if `start_time` is provided |

**Output** — array of room objects:

```json
[
  {
    "id": 3,
    "name": "Einstein",
    "floor": 2,
    "capacity": 10,
    "features": ["projector", "whiteboard"],
    "description": "Corner room with natural light"
  }
]
```

**Errors**

| Condition | Message |
|-----------|---------|
| `end_time` missing when `start_time` provided | `"end_time is required when start_time is provided"` |
| `start_time` >= `end_time` | `"start_time must be before end_time"` |

---

### 2. `book_room`

Books a specific room for a time slot. Prevents double-booking via DB constraint.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `room_id` | `integer` | Yes | ID of the room to book |
| `booked_by` | `string` | Yes | Name or email of the person booking |
| `title` | `string` | Yes | Meeting title (e.g. `"Team Standup"`) |
| `start_time` | `string` (ISO 8601) | Yes | Start time |
| `end_time` | `string` (ISO 8601) | Yes | End time |

**Output**

```json
{
  "success": true,
  "booking_id": 42,
  "message": "Room 'Einstein' booked for Harel from 10:00 to 11:00"
}
```

**Errors**

| Condition | Message |
|-----------|---------|
| Room doesn't exist | `"Room with id {room_id} not found"` |
| Time slot overlaps existing booking | `"Room is already booked during this time slot"` |
| `start_time` >= `end_time` | `"start_time must be before end_time"` |
| `start_time` in the past | `"Cannot book a room in the past"` |

---

### 3. `cancel_booking`

Cancels an existing booking. Only the original booker can cancel.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `booking_id` | `integer` | Yes | ID of the booking to cancel |
| `booked_by` | `string` | Yes | Must match the name/email used when booking |

**Output**

```json
{
  "success": true,
  "message": "Booking #42 ('Team Standup' in Einstein) has been cancelled"
}
```

**Errors**

| Condition | Message |
|-----------|---------|
| Booking not found | `"Booking with id {booking_id} not found"` |
| `booked_by` doesn't match | `"You are not authorized to cancel this booking"` |

---

### 4. `check_room_availability`

Checks whether a specific room is free during a given window.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `room_id` | `integer` | Yes | ID of the room |
| `start_time` | `string` (ISO 8601) | Yes | Start of the window |
| `end_time` | `string` (ISO 8601) | Yes | End of the window |

**Output**

```json
{
  "room_id": 3,
  "room_name": "Einstein",
  "available": true,
  "conflicts": []
}
```

If unavailable:

```json
{
  "room_id": 3,
  "room_name": "Einstein",
  "available": false,
  "conflicts": [
    {
      "booking_id": 7,
      "title": "Sprint Review",
      "booked_by": "alice@siemens.com",
      "start_time": "2026-04-12T09:30:00",
      "end_time": "2026-04-12T10:30:00"
    }
  ]
}
```

---

### 5. `get_room_details`

Returns complete information about a room, including upcoming bookings.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `room_id` | `integer` | Yes | ID of the room |

**Output**

```json
{
  "id": 3,
  "name": "Einstein",
  "floor": 2,
  "capacity": 10,
  "features": ["projector", "whiteboard"],
  "description": "Corner room with natural light",
  "upcoming_bookings": [
    {
      "booking_id": 7,
      "title": "Sprint Review",
      "booked_by": "alice@siemens.com",
      "start_time": "2026-04-12T09:30:00",
      "end_time": "2026-04-12T10:30:00"
    }
  ]
}
```

**Errors**

| Condition | Message |
|-----------|---------|
| Room not found | `"Room with id {room_id} not found"` |

---

### 6. `get_my_bookings`

Returns all upcoming bookings for a given user, sorted by start time.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `booked_by` | `string` | Yes | Name or email of the user |
| `from_date` | `string` (ISO 8601 date) | No | Filter from this date (default: today) |
| `to_date` | `string` (ISO 8601 date) | No | Filter until this date (default: no upper bound) |

**Output**

```json
[
  {
    "booking_id": 42,
    "room_id": 3,
    "room_name": "Einstein",
    "floor": 2,
    "title": "Team Standup",
    "start_time": "2026-04-12T09:00:00",
    "end_time": "2026-04-12T09:30:00"
  }
]
```

---

### 7. `reset_database`

Clears all bookings from the database. Requires an admin password for authorization.  
Rooms and features are preserved — only booking data is deleted.

> Intended for demo resets. Not exposed in production.

**Input**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `admin_password` | `string` | Yes | Must match the `MCP_ADMIN_PASSWORD` environment variable |

**Output**

```json
{ "success": true, "message": "All bookings have been cleared (42 rows deleted)" }
```

**Errors**

| Condition | Message |
|-----------|---------|
| Wrong password | `"Unauthorized: invalid admin password"` |
| `MCP_ADMIN_PASSWORD` not set | `"Admin password not configured on the server"` |

**Configuration**

Set in `.env` at the project root (git-ignored):
```bash
MCP_ADMIN_PASSWORD=your-secret-here
```
See `.env.example` for reference. The server loads this automatically on startup via `python-dotenv`.

---

## Common Conventions

- All timestamps are **ISO 8601** in local time (no timezone suffix assumed to be local).
- All tools return a JSON object or array.
- On error, tools return `{ "error": "<message>" }` with a human-readable description.
- Tool descriptions and docstrings in the implementation serve as the auto-generated schema description for the MCP client.

---

## Integration

### Claude Code (stdio)

```bash
claude mcp add --transport stdio room-bookings -- python src/mcp_server/server.py
```

### VS Code / GitHub Copilot

Configuration in `.vscode/mcp.json`:

```json
{
  "servers": {
    "room-bookings": {
      "command": "python",
      "args": ["src/mcp_server/server.py"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```
