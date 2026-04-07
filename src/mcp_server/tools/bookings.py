"""
Tools: book_room, cancel_booking, get_my_bookings

Spec: specs/mcp_tools.md
"""

from datetime import date, datetime

from mcp_server import database as db
from mcp_server.models import BookingResult, Room


def book_room(
    room_id: int,
    booked_by: str,
    title: str,
    start_time: str,
    end_time: str,
) -> dict:
    """
    Book a meeting room for a specific time slot.

    Returns a booking confirmation with the new booking ID.
    If the room is already taken, returns an error and suggests alternative
    available rooms for the same time window.

    Args:
        room_id: The numeric ID of the room to book.
        booked_by: Your name or email (used for identification and cancellation).
        title: Meeting title, e.g. 'Team Standup' or 'Client Demo'.
        start_time: ISO 8601 start time, e.g. '2026-04-12T10:00:00'.
        end_time: ISO 8601 end time, e.g. '2026-04-12T11:00:00'.
    """
    # --- Input validation ---
    if start_time >= end_time:
        return {"error": "start_time must be before end_time"}

    try:
        if datetime.fromisoformat(start_time) < datetime.now():
            return {"error": "Cannot book a room in the past"}
    except ValueError:
        return {"error": f"Invalid start_time format: '{start_time}'. Use ISO 8601 e.g. '2026-04-12T10:00:00'"}

    room = db.get_room_by_id(room_id)
    if room is None:
        return {"error": f"Room with id {room_id} not found"}

    # --- Conflict check ---
    conflicts = db.get_overlapping_bookings(room_id, start_time, end_time)
    if conflicts:
        # Find alternative rooms with the same capacity for the same slot
        alternatives = db.get_rooms(
            min_capacity=room["capacity"],
            start_time=start_time,
            end_time=end_time,
        )
        # Exclude the requested room from suggestions
        alternatives = [r for r in alternatives if r["id"] != room_id]

        return {
            "error": f"Room '{room['name']}' is already booked during this time slot",
            "conflicts": [
                {
                    "title": c["title"],
                    "booked_by": c["booked_by"],
                    "start_time": c["start_time"],
                    "end_time": c["end_time"],
                }
                for c in conflicts
            ],
            "alternatives": [Room(**r).model_dump() for r in alternatives[:3]],
        }

    # --- Create booking ---
    booking_id = db.create_booking(room_id, booked_by, title, start_time, end_time)

    return {
        "success": True,
        "booking_id": booking_id,
        "message": (
            f"Room '{room['name']}' (floor {room['floor']}) booked for {booked_by} - "
            f"'{title}' from {start_time} to {end_time}"
        ),
    }


def cancel_booking(booking_id: int, booked_by: str) -> dict:
    """
    Cancel an existing booking. Only the person who made the booking can cancel it.

    Args:
        booking_id: The numeric ID of the booking to cancel.
        booked_by: Must match the name/email used when the booking was created.
    """
    booking = db.get_booking_by_id(booking_id)
    if booking is None:
        return {"error": f"Booking with id {booking_id} not found"}

    if booking["booked_by"].lower() != booked_by.lower():
        return {"error": "You are not authorized to cancel this booking"}

    db.delete_booking(booking_id)

    return {
        "success": True,
        "message": (
            f"Booking #{booking_id} ('{booking['title']}' in {booking['room_name']}) "
            f"has been cancelled"
        ),
    }


def get_my_bookings(
    booked_by: str,
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[dict]:
    """
    List all upcoming bookings for a specific user.

    Args:
        booked_by: Your name or email.
        from_date: ISO 8601 date to start from, e.g. '2026-04-12'. Defaults to today.
        to_date: ISO 8601 date to end at, e.g. '2026-04-20'. Optional.
    """
    resolved_from = from_date or date.today().isoformat()

    rows = db.get_bookings_by_user(booked_by, resolved_from, to_date)

    return [
        BookingResult(
            booking_id=row["id"],
            room_id=row["room_id"],
            room_name=row["room_name"],
            floor=row["floor"],
            title=row["title"],
            booked_by=row["booked_by"],
            start_time=row["start_time"],
            end_time=row["end_time"],
        ).model_dump()
        for row in rows
    ]
