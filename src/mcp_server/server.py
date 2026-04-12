"""
FastMCP entry point for the Siemens Room Bookings MCP Server.

Rules (from specs/architecture.md):
- Registers all tools. No business logic here.
- Calls init_db() on startup to ensure DB and schema exist.
- Runs with stdio transport (default) for Claude Code / GitHub Copilot integration.
- All logging goes to stderr — stdout is reserved for JSON-RPC.
"""

import logging
import sys

from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv()

from mcp_server.database import init_db, get_rooms
from mcp_server.tools.admin import reset_database
from mcp_server.tools.availability import check_room_availability
from mcp_server.tools.bookings import book_room, cancel_booking, get_my_bookings
from mcp_server.tools.rooms import get_room_details, list_available_rooms
from mcp_server.tools.schedule import list_all_bookings

logging.basicConfig(stream=sys.stderr, level=logging.INFO)

mcp = FastMCP(
    name="Siemens Room Bookings",
    instructions=(
        "You manage meeting room bookings. "
        "Use list_available_rooms to find free rooms, book_room to reserve one, "
        "cancel_booking to free a slot, check_room_availability to inspect a specific room, "
        "get_room_details for full room info, get_my_bookings to see a user's schedule, "
        "and list_all_bookings to see all bookings across every room for a given date or date range. "
        "Always confirm booking details (room, time, title) with the user before calling book_room."
    ),
)

# --- Register tools ---
mcp.tool()(list_available_rooms)
mcp.tool()(book_room)
mcp.tool()(cancel_booking)
mcp.tool()(check_room_availability)
mcp.tool()(get_room_details)
mcp.tool()(get_my_bookings)
mcp.tool()(reset_database)
mcp.tool()(list_all_bookings)


# --- Resource: room catalog as background context ---
@mcp.resource("rooms://catalog")
def rooms_catalog() -> str:
    """Full room catalog — loaded by the client as background context."""
    rooms = get_rooms(min_capacity=1)
    lines = ["# Available Meeting Rooms\n"]
    for r in rooms:
        features = ", ".join(r["features"]) or "none"
        lines.append(
            f"- **{r['name']}** (id={r['id']}) — floor {r['floor']}, "
            f"{r['capacity']} seats, features: {features}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    init_db()
    mcp.run()  # stdio transport
