"""
Tools: list_available_rooms, get_room_details

Spec: specs/mcp_tools.md
"""

from mcp_server import database as db
from mcp_server.models import BookingSummary, Room, RoomDetail


def list_available_rooms(
    min_capacity: int,
    required_features: list[str] | None = None,
    preferred_floor: int | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict]:
    """
    Search for available meeting rooms by capacity, equipment, floor, and time window.

    Returns rooms that match ALL criteria. When start_time and end_time are provided,
    only rooms free during that window are returned.

    Args:
        min_capacity: Minimum number of seats required.
        required_features: Equipment needed — any of: projector, whiteboard,
                           video_conferencing, tv_screen.
        preferred_floor: Restrict results to a specific floor (1–4).
        start_time: ISO 8601 start of desired slot, e.g. '2026-04-12T10:00:00'.
        end_time: ISO 8601 end of desired slot. Required when start_time is given.
    """
    if start_time and not end_time:
        return {"error": "end_time is required when start_time is provided"}

    if start_time and end_time and start_time >= end_time:
        return {"error": "start_time must be before end_time"}

    rooms = db.get_rooms(
        min_capacity=min_capacity,
        required_features=required_features,
        preferred_floor=preferred_floor,
        start_time=start_time,
        end_time=end_time,
    )

    return [Room(**r).model_dump() for r in rooms]


def get_room_details(room_id: int) -> dict:
    """
    Get full details for a specific room, including upcoming bookings.

    Args:
        room_id: The numeric ID of the room.
    """
    room = db.get_room_by_id(room_id)
    if room is None:
        return {"error": f"Room with id {room_id} not found"}

    upcoming_rows = db.get_upcoming_bookings_for_room(room_id)
    upcoming = [
        BookingSummary(
            booking_id=row["id"],
            title=row["title"],
            booked_by=row["booked_by"],
            start_time=row["start_time"],
            end_time=row["end_time"],
        )
        for row in upcoming_rows
    ]

    return RoomDetail(**room, upcoming_bookings=upcoming).model_dump()
