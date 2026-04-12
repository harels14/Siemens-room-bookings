"""
Tool: list_all_bookings

Returns all bookings across all rooms for a given date or time range.
"""

from datetime import date

from mcp_server import database as db
from mcp_server.models import BookingResult


def list_all_bookings(
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[dict]:
    """
    List all bookings across every room for a given date or date range.

    Returns results sorted by start time, then floor — giving a full picture
    of room usage without needing to check each room individually.

    Args:
        from_date: ISO 8601 date to start from, e.g. '2026-04-08'. Defaults to today.
        to_date: ISO 8601 date to end at (inclusive), e.g. '2026-04-08'. Defaults to from_date.
    """
    resolved_from = from_date or date.today().isoformat()
    resolved_to = to_date or resolved_from

    start_time = f"{resolved_from}T00:00:00"
    end_time = f"{resolved_to}T23:59:59"

    rows = db.get_all_bookings_in_range(start_time, end_time)

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
