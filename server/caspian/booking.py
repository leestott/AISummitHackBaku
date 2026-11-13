"""Transactional simulated reservations. There are no payment or supplier clients."""

from __future__ import annotations

import calendar
import json
import math
import secrets
import sqlite3
import string
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from . import catalog
from .storage import ServiceError, Store, encode, timestamp

TEST_CARDS = ("4242424242424242", "5555555555554444")
WATERMARK = "SIMULATED - NOT A RESERVATION"
HOLD_MINUTES = 15
TRANSITIONS = {
    "draft": {"held", "expired", "cancelled_simulated"},
    "held": {"details_captured", "expired", "cancelled_simulated"},
    "details_captured": {"payment_simulated", "expired", "cancelled_simulated"},
    "payment_simulated": {"confirmed_simulated", "expired", "cancelled_simulated"},
    "confirmed_simulated": {"cancelled_simulated"},
    "expired": set(),
    "cancelled_simulated": set(),
}
HOLD_STATES = ("draft", "held", "details_captured", "payment_simulated")


def money(value: Decimal | float | int) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def add_calendar_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 + months
    year, zero_month = divmod(month_index, 12)
    month = zero_month + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


class BookingService:
    def __init__(self, store: Store) -> None:
        self.store = store

    @staticmethod
    def _load(connection: sqlite3.Connection, session_id: str, reference: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM bookings WHERE reference=? AND session_id=?", (reference, session_id)
        ).fetchone()
        if row is None:
            raise ServiceError(404, "not_found", "Simulated booking not found.")
        return row

    @staticmethod
    def _persist(connection: sqlite3.Connection, session_id: str, booking: dict) -> None:
        connection.execute(
            "UPDATE bookings SET state=?,booking_json=? WHERE reference=? AND session_id=?",
            (booking["state"], encode(booking), booking["reference"], session_id),
        )

    def _transition(
        self, connection: sqlite3.Connection, session_id: str, booking: dict, state: str, now: datetime
    ) -> None:
        previous = booking["state"]
        if state not in TRANSITIONS[previous]:
            raise ServiceError(
                409, "invalid_booking_state", "This operation is not allowed in the current booking state."
            )
        booking["state"] = state
        self._persist(connection, session_id, booking)
        connection.execute(
            "INSERT INTO booking_events(reference,from_state,to_state,occurred_at) VALUES(?,?,?,?)",
            (booking["reference"], previous, state, timestamp(now)),
        )

    @staticmethod
    def _release(connection: sqlite3.Connection, row: sqlite3.Row) -> None:
        if row["inventory_released"]:
            return
        reservations = connection.execute(
            "SELECT kind,resource_id,slot,quantity FROM booking_inventory "
            "WHERE reference=? AND session_id=?",
            (row["reference"], row["session_id"]),
        ).fetchall()
        for reservation in reservations:
            updated = connection.execute(
                "UPDATE inventory SET reserved=reserved-? "
                "WHERE session_id=? AND kind=? AND resource_id=? AND slot=? AND reserved>=?",
                (
                    reservation["quantity"], row["session_id"], reservation["kind"],
                    reservation["resource_id"], reservation["slot"], reservation["quantity"],
                ),
            )
            if updated.rowcount != 1:
                raise RuntimeError("Synthetic inventory invariant failed")
        connection.execute(
            "UPDATE bookings SET inventory_released=1 WHERE reference=? AND session_id=?",
            (row["reference"], row["session_id"]),
        )

    def _expire(self, connection: sqlite3.Connection, session_id: str, now: datetime) -> None:
        rows = connection.execute(
            "SELECT * FROM bookings WHERE session_id=? AND expires_at<=? "
            "AND state IN ('draft','held','details_captured','payment_simulated')",
            (session_id, timestamp(now)),
        ).fetchall()
        for row in rows:
            booking = json.loads(row["booking_json"])
            self._release(connection, row)
            self._transition(connection, session_id, booking, "expired", now)

    @contextmanager
    def _transaction(self, session_id: str) -> Iterator[tuple[sqlite3.Connection, datetime]]:
        failure = None
        with self.store.transaction() as connection:
            self.store.require_session(connection, session_id)
            now = self.store.now()
            self._expire(connection, session_id, now)
            # Expiration must commit even when the requested action subsequently fails.
            connection.execute("SAVEPOINT booking_action")
            try:
                yield connection, now
            except ServiceError as error:
                connection.execute("ROLLBACK TO booking_action")
                failure = error
            finally:
                connection.execute("RELEASE booking_action")
        if failure is not None:
            raise failure

    @staticmethod
    def _reserve(
        connection: sqlite3.Connection,
        session_id: str,
        reference: str,
        kind: str,
        resource_id: str,
        slot: str,
        capacity: int,
        quantity: int,
    ) -> None:
        connection.execute(
            "INSERT INTO inventory(session_id,kind,resource_id,slot,capacity) VALUES(?,?,?,?,?) "
            "ON CONFLICT(session_id,kind,resource_id,slot) DO NOTHING",
            (session_id, kind, resource_id, slot, capacity),
        )
        # Reusing another search seed cannot replenish an existing session's inventory.
        updated = connection.execute(
            "UPDATE inventory SET reserved=reserved+? "
            "WHERE session_id=? AND kind=? AND resource_id=? AND slot=? "
            "AND capacity-reserved>=?",
            (quantity, session_id, kind, resource_id, slot, quantity),
        )
        if updated.rowcount != 1:
            raise ServiceError(409, "inventory_unavailable", "The selected synthetic inventory is unavailable.")
        connection.execute(
            "INSERT INTO booking_inventory(reference,session_id,kind,resource_id,slot,quantity) "
            "VALUES(?,?,?,?,?,?)",
            (reference, session_id, kind, resource_id, slot, quantity),
        )

    def availability(
        self, session_id: str, hotel_id: str, checkin: str, checkout: str,
        guests: int = 2, room_type_id: str | None = None, seed: int = 42,
    ) -> dict:
        try:
            result = catalog.availability(hotel_id, checkin, checkout, guests, room_type_id, seed)
        except ValueError as error:
            raise ServiceError(422, "invalid_selection", str(error)) from error
        resource = f"{hotel_id}:{result['room_type_id']}"
        with self._transaction(session_id) as (connection, _):
            for night in result["nights"]:
                inventory = connection.execute(
                    "SELECT capacity,reserved FROM inventory "
                    "WHERE session_id=? AND kind='hotel' AND resource_id=? AND slot=?",
                    (session_id, resource, night["date"]),
                ).fetchone()
                if inventory is not None:
                    night["available"] = max(0, inventory["capacity"] - inventory["reserved"])
            result["available"] = all(
                night["available"] >= result["rooms_required"] for night in result["nights"]
            )
        return result

    def create(self, session_id: str, selection: dict) -> dict:
        with self._transaction(session_id) as (connection, now):
            trip = self.store.load_trip(connection, session_id, selection["trip_plan_id"])
            params = trip["search_params"]
            if date.fromisoformat(params["arrival"]) < now.date():
                raise ServiceError(422, "invalid_dates", "The arrival date is in the past.")
            hotel_id = selection["hotel_id"]
            if hotel_id != trip["selected_hotel_id"]:
                raise ServiceError(422, "invalid_selection", "Select this hotel in the trip before booking it.")
            hotel = next((hotel for hotel in trip["hotels"] if hotel["id"] == hotel_id), None)
            if hotel is None:
                raise ServiceError(422, "invalid_selection", "The hotel does not belong to this trip.")
            room = next(
                (room for room in hotel["room_types"] if room["id"] == selection["room_type_id"]), None
            )
            guests = params["adults"] + params["children"]
            if room is None or (guests <= 4 and guests > room["max_occupancy"]):
                raise ServiceError(422, "invalid_occupancy", "Choose a room that accommodates every traveller.")
            rooms_required = math.ceil(guests / room["max_occupancy"])
            flight_id = selection.get("flight_id")
            if flight_id is not None and (
                flight_id != trip["selected_flight_id"]
                or not any(flight["id"] == flight_id for flight in trip["flights"])
            ):
                raise ServiceError(422, "invalid_selection", "The flight does not match the planned flight.")
            activity_ids = selection.get("activity_ids", [])
            if len(set(activity_ids)) != len(activity_ids):
                raise ServiceError(422, "invalid_selection", "Activities must not be duplicated.")
            activities = {activity["id"]: activity for activity in trip["activities"]}
            scheduled = [
                (day["date"], item)
                for day in trip["itinerary_days"]
                for item in day["items"]
                if item["activity_id"] in activity_ids
            ]
            if set(activity_ids) - activities.keys() or (
                set(activity_ids) - {item["activity_id"] for _, item in scheduled}
            ):
                raise ServiceError(
                    422, "invalid_selection", "Only activities scheduled in this trip can be booked."
                )
            try:
                available = catalog.availability(
                    hotel_id, params["arrival"], params["departure"], guests, room["id"], params["seed"]
                )
            except ValueError as error:
                raise ServiceError(422, "invalid_selection", str(error)) from error
            items = []
            reservations = []
            for night in available["nights"]:
                items.append({
                    "id": f"{hotel_id}:{room['id']}:{night['date']}",
                    "kind": "hotel",
                    "name": f"{hotel['name']} - {room['name']}",
                    "date": night["date"], "quantity": rooms_required,
                    "unit_price_azn": money(night["unit_price_azn"]),
                    "total_azn": money(night["price_azn"]),
                })
                reservations.append((
                    "hotel", f"{hotel_id}:{room['id']}", night["date"], night["available"], rooms_required
                ))
            for day, item in scheduled:
                activity = activities[item["activity_id"]]
                amount = money(Decimal(str(activity["price_azn"])) * guests)
                items.append({
                    "id": f"{activity['id']}:{day}:{item['start_time']}",
                    "kind": "activity", "name": activity["name"], "date": day,
                    "quantity": guests, "unit_price_azn": money(activity["price_azn"]),
                    "total_azn": amount,
                })
                reservations.append((
                    "activity", activity["id"], f"{day}T{item['start_time']}",
                    activity["capacity_per_slot"], guests,
                ))
            alphabet = string.ascii_uppercase + string.digits
            reference = "SIM-BAK-" + "".join(secrets.choice(alphabet) for _ in range(6))
            while connection.execute(
                "SELECT 1 FROM bookings WHERE reference=?", (reference,)
            ).fetchone():
                reference = "SIM-BAK-" + "".join(secrets.choice(alphabet) for _ in range(6))
            total = sum((Decimal(str(item["total_azn"])) for item in items), Decimal(0))
            notices = [
                "Demonstration only. No supplier is contacted and no money is charged.",
                "Flights are planned, not booked. Transport is guidance, not a booking item.",
                "Use sample traveller details and the published test cards only.",
                "This synthetic hold lasts 15 minutes; demo sessions and inventory reset at midnight UTC.",
                hotel["cancellation_policy"],
            ]
            if rooms_required > 1:
                notices.append(f"The basket includes {rooms_required} rooms per night for {guests} travellers.")
            notices.extend(
                item["description"] for item in trip["checklist"] if item["severity"] == "warning"
            )
            booking = {
                "reference": reference, "trip_plan_id": trip["id"], "state": "draft",
                "items": items, "total_azn": money(total),
                "total_gbp": money(total * Decimal(str(trip["exchange_rates"]["rates"]["GBP"]))),
                "created_at": timestamp(now), "expires_at": timestamp(now + timedelta(minutes=HOLD_MINUTES)),
                "watermark": WATERMARK, "notices": notices, "is_synthetic": True,
            }
            connection.execute(
                "INSERT INTO bookings(reference,session_id,trip_plan_id,state,expires_at,booking_json,plan_json) "
                "VALUES(?,?,?,?,?,?,?)",
                (reference, session_id, trip["id"], "draft", booking["expires_at"], encode(booking), encode(trip)),
            )
            connection.execute(
                "INSERT INTO booking_events(reference,from_state,to_state,occurred_at) VALUES(?,NULL,?,?)",
                (reference, "draft", timestamp(now)),
            )
            for kind, resource_id, slot, capacity, quantity in reservations:
                self._reserve(connection, session_id, reference, kind, resource_id, slot, capacity, quantity)
            self._transition(connection, session_id, booking, "held", now)
            return booking

    def get(self, session_id: str, reference: str) -> dict:
        with self._transaction(session_id) as (connection, _):
            return json.loads(self._load(connection, session_id, reference)["booking_json"])

    def details(self, session_id: str, reference: str, details: dict) -> dict:
        with self._transaction(session_id) as (connection, now):
            row = self._load(connection, session_id, reference)
            booking = json.loads(row["booking_json"])
            if booking["state"] not in ("held", "details_captured"):
                raise ServiceError(409, "invalid_booking_state", "Traveller details cannot be changed in this state.")
            try:
                passport_expiry = date.fromisoformat(details["passport_expiry"])
                evisa_expiry = date.fromisoformat(details["evisa_expiry"]) if details.get("evisa_expiry") else None
            except (ValueError, TypeError):
                raise ServiceError(422, "invalid_documents", "Enter valid document expiry dates.") from None
            if passport_expiry < now.date():
                raise ServiceError(422, "invalid_documents", "The sample passport has expired.")
            if evisa_expiry is None:
                notice = (
                    "Passport validity cannot be verified without the e-visa expiry date. "
                    "It must extend at least three calendar months beyond the e-visa expiry; confirm at evisa.gov.az."
                )
            else:
                try:
                    required_expiry = add_calendar_months(evisa_expiry, 3)
                except ValueError:
                    raise ServiceError(422, "invalid_documents", "Enter a supported e-visa expiry date.") from None
                if evisa_expiry < now.date() or passport_expiry < required_expiry:
                    raise ServiceError(
                        422, "invalid_documents",
                        "The passport must remain valid at least three calendar months after the e-visa expiry date.",
                        {"passport_expiry": "Does not meet the e-visa passport validity rule."},
                    )
                notice = (
                    "Passport validity meets the three-calendar-month rule for the supplied sample e-visa expiry. "
                    "Expiry dates have not been saved; confirm official requirements before travel."
                )
            booking["notices"] = [
                item for item in booking["notices"] if not item.startswith("Passport validity")
            ] + [notice]
            # Only these sample fields are persisted; document and payment fields never reach SQLite.
            stored_details = {key: details[key] for key in ("name", "email", "nationality")}
            connection.execute(
                "UPDATE bookings SET details_json=? WHERE reference=? AND session_id=?",
                (encode(stored_details), reference, session_id),
            )
            if booking["state"] == "held":
                self._transition(connection, session_id, booking, "details_captured", now)
            else:
                self._persist(connection, session_id, booking)
            return booking

    def pay(self, session_id: str, reference: str, card_number: str) -> dict:
        with self._transaction(session_id) as (connection, now):
            booking = json.loads(self._load(connection, session_id, reference)["booking_json"])
            if card_number not in TEST_CARDS:
                raise ServiceError(
                    422, "test_card_required", "Real cards are not accepted in this demo"
                )
            if booking["state"] == "confirmed_simulated":
                return booking
            if booking["state"] != "details_captured":
                raise ServiceError(409, "invalid_booking_state", "An unexpired booking with traveller details is required.")
            self._transition(connection, session_id, booking, "payment_simulated", now)
            self._transition(connection, session_id, booking, "confirmed_simulated", now)
            return booking

    def cancel(self, session_id: str, reference: str) -> dict:
        with self._transaction(session_id) as (connection, now):
            row = self._load(connection, session_id, reference)
            booking = json.loads(row["booking_json"])
            if booking["state"] == "cancelled_simulated":
                return booking
            if booking["state"] == "expired":
                raise ServiceError(409, "invalid_booking_state", "An expired booking cannot be changed.")
            self._release(connection, row)
            self._transition(connection, session_id, booking, "cancelled_simulated", now)
            return booking

    def export(self, session_id: str, reference: str) -> tuple[dict, dict]:
        with self._transaction(session_id) as (connection, _):
            row = self._load(connection, session_id, reference)
            booking = json.loads(row["booking_json"])
            if booking["state"] != "confirmed_simulated":
                raise ServiceError(409, "confirmation_required", "Confirm the simulated booking before downloading.")
            return booking, json.loads(row["plan_json"])
