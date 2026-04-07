"""
Tool: check_room_availability

Spec: specs/mcp_tools.md
"""

from mcp_server import database as db


def check_room_availability(room_id: int, start_time: str, end_time: str) -> dict:
    """
    Check whether a specific room is free during a given time window.

    Returns availability status and any conflicting bookings.

    Args:
        room_id: The numeric ID of the room to check.
        start_time: ISO 8601 start of the window, e.g. '2026-04-12T10:00:00'.
        end_time: ISO 8601 end of the window, e.g. '2026-04-12T11:00:00'.
    """
    if start_time >= end_time:
        return {"error": "start_time must be before end_time"}

    room = db.get_room_by_id(room_id)
    if room is None:
        return {"error": f"Room with id {room_id} not found"}

    conflicts = db.get_overlapping_bookings(room_id, start_time, end_time)

    return {
        "room_id": room_id,
        "room_name": room["name"],
        "available": len(conflicts) == 0,
        "conflicts": [
            {
                "booking_id": c["id"],
                "title": c["title"],
                "booked_by": c["booked_by"],
                "start_time": c["start_time"],
                "end_time": c["end_time"],
            }
            for c in conflicts
        ],
    }
