"""
Pydantic models for output validation.

Rules (from specs/architecture.md):
- Used by tools/ for output validation only.
- Not imported by database.py.
- Spec: specs/architecture.md → models.py
"""

from pydantic import BaseModel


class Room(BaseModel):
    id: int
    name: str
    floor: int
    capacity: int
    features: list[str]
    description: str | None = None


class BookingSummary(BaseModel):
    booking_id: int
    title: str
    booked_by: str
    start_time: str
    end_time: str


class RoomDetail(Room):
    upcoming_bookings: list[BookingSummary] = []


class BookingResult(BaseModel):
    booking_id: int
    room_id: int
    room_name: str
    floor: int
    title: str
    booked_by: str
    start_time: str
    end_time: str
