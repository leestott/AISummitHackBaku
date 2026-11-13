from __future__ import annotations

import http.client
import json
import re
import shutil
import socket
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from caspian import catalog
from caspian.api import create_app
from caspian.booking import BookingService, TEST_CARDS, WATERMARK
from caspian.exports import render_ics
from caspian.storage import ServiceError, Store


@pytest.fixture
def demo():
    directory = Path(".data").joinpath(f"booking-test-{uuid.uuid4().hex}")
    directory.mkdir(parents=True)
    application = create_app(str(directory / "test.sqlite3"))
    now = application.state.store.now().replace(hour=12, minute=0, second=0, microsecond=0)
    application.state.store.clock = lambda: now
    arrival = date(date.today().year + 1, 4, 12)
    try:
        with TestClient(application) as client:
            response = client.post("/api/search", json={
                "origin": "London", "arrival": arrival.isoformat(),
                "departure": (arrival + timedelta(days=4)).isoformat(),
                "adults": 2, "children": 0, "budget": "mid-range",
                "interests": ["history", "food"], "regions": ["baku"], "pace": "balanced", "seed": 42,
            })
            assert response.status_code == 200, response.text
            trip = response.json()
            scheduled = [item["activity_id"] for day in trip["itinerary_days"] for item in day["items"]]
            assert scheduled
            selection = {
                "trip_plan_id": trip["id"], "hotel_id": trip["selected_hotel_id"],
                "room_type_id": "standard", "activity_ids": scheduled[:1],
                "flight_id": trip["selected_flight_id"],
            }
            yield application, client, trip, selection, directory
    finally:
        application.state.store.close()
        shutil.rmtree(directory)


def hold(demo, **changes):
    _, client, _, selection, _ = demo
    response = client.post("/api/sim-bookings", json={**selection, **changes})
    assert response.status_code == 200, response.text
    return response.json()


def details(client, reference, **changes):
    return client.post(f"/api/sim-bookings/{reference}/details", json={
        "name": "Sample Traveller", "email": "sample@example.invalid", "nationality": "GB",
        "passport_expiry": "2049-06-30", "evisa_expiry": "2049-03-31", **changes,
    })


def pay(client, reference, card=TEST_CARDS[0]):
    return client.post(f"/api/sim-bookings/{reference}/pay", json={"card_number": card})


def hotel_availability(client, trip):
    return client.get(f"/api/hotels/{trip['selected_hotel_id']}/availability", params={
        "checkin": trip["search_params"]["arrival"], "checkout": trip["search_params"]["departure"],
        "guests": trip["search_params"]["adults"] + trip["search_params"]["children"],
        "room_type_id": "standard", "seed": 42,
    }).json()


def test_successful_simulation_has_no_booking_or_payment_network_calls(demo, monkeypatch):
    application, client, trip, _, _ = demo

    def no_network(*args, **kwargs):
        raise AssertionError("The booking flow attempted an outbound connection")

    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(http.client.HTTPConnection, "connect", no_network)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", no_network)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", no_network)
    available = hotel_availability(client, trip)
    booking = hold(demo)
    assert booking["state"] == "held"
    assert re.fullmatch(r"SIM-BAK-[A-Z0-9]{6}", booking["reference"])
    assert booking["watermark"] == WATERMARK
    assert all(item["kind"] != "flight" for item in booking["items"])
    assert sum(item["total_azn"] for item in booking["items"] if item["kind"] == "hotel") == pytest.approx(available["total_azn"])
    assert booking["total_azn"] == pytest.approx(sum(item["total_azn"] for item in booking["items"]))
    reference = booking["reference"]
    assert client.get(f"/api/sim-bookings/{reference}/itinerary.pdf").status_code == 409
    assert details(client, reference).status_code == 200
    paid = pay(client, reference)
    assert paid.status_code == 200 and paid.json()["state"] == "confirmed_simulated"
    with application.state.store.read() as connection:
        transitions = [
            row["to_state"] for row in connection.execute(
                "SELECT to_state FROM booking_events WHERE reference=? ORDER BY id", (reference,)
            )
        ]
    assert transitions == ["draft", "held", "details_captured", "payment_simulated", "confirmed_simulated"]


def test_non_test_cards_are_rejected_and_sensitive_values_never_persist(demo, caplog):
    application, client, _, _, directory = demo
    reference = hold(demo)["reference"]
    failed_passport = "2049-06-29"
    failed = details(client, reference, passport_expiry=failed_passport)
    assert failed.status_code == 422
    assert failed_passport not in failed.text
    assert details(client, reference).status_code == 200
    rejected_card = "4111111111111111"
    rejected = pay(client, reference, rejected_card)
    assert rejected.status_code == 422
    assert rejected.json()["error"]["message"] == "Real cards are not accepted in this demo"
    assert client.get(f"/api/sim-bookings/{reference}").json()["state"] == "details_captured"
    assert pay(client, reference).status_code == 200
    forbidden = [failed_passport, "2049-06-30", "2049-03-31", rejected_card, *TEST_CARDS]
    with application.state.store.read() as connection:
        content = "\n".join(
            json.dumps(tuple(row)) for row in connection.execute("SELECT * FROM bookings")
        )
        assert "passport_expiry" not in content and "card_number" not in content
        assert "evisa_expiry" not in content
        assert all(value not in content for value in forbidden)
    for database_file in directory.glob("test.sqlite3*"):
        raw = database_file.read_bytes()
        assert all(value.encode() not in raw for value in forbidden)
    assert all(value not in caplog.text for value in forbidden)


def test_calendar_month_rule_and_missing_evisa_warning(demo):
    _, client, _, _, _ = demo
    reference = hold(demo)["reference"]
    rejected = details(client, reference, evisa_expiry="2048-05-31", passport_expiry="2048-08-30")
    assert rejected.status_code == 422  # Ninety days is not three calendar months.
    accepted = details(client, reference, evisa_expiry="2048-05-31", passport_expiry="2048-08-31")
    assert accepted.status_code == 200
    clamped = details(client, reference, evisa_expiry="2048-11-30", passport_expiry="2049-02-28")
    assert clamped.status_code == 200
    missing = details(client, reference, evisa_expiry=None)
    assert missing.status_code == 200
    notices = " ".join(missing.json()["notices"])
    assert "cannot be verified without the e-visa expiry date" in notices
    assert "Passport validity meets" not in notices


def test_expired_payment_commits_expiration_and_releases_hold(demo):
    application, client, trip, _, _ = demo
    before = hotel_availability(client, trip)
    reference = hold(demo)["reference"]
    assert details(client, reference).status_code == 200
    now = application.state.store.now()
    application.state.store.clock = lambda: now + timedelta(minutes=16)
    assert pay(client, reference).status_code == 409
    with application.state.store.read() as connection:
        assert connection.execute("SELECT state FROM bookings WHERE reference=?", (reference,)).fetchone()[0] == "expired"
    assert client.get(f"/api/sim-bookings/{reference}").json()["state"] == "expired"
    assert hotel_availability(client, trip) == before
    assert client.post(f"/api/sim-bookings/{reference}/cancel").status_code == 409


def test_payment_replay_and_cancellation_never_double_consume_or_revive(demo):
    application, client, trip, _, _ = demo
    initial = hotel_availability(client, trip)
    reference = hold(demo)["reference"]
    assert pay(client, reference).status_code == 409
    assert details(client, reference).status_code == 200
    first = pay(client, reference)
    reserved = hotel_availability(client, trip)
    assert pay(client, reference).json() == first.json()
    now = application.state.store.now()
    application.state.store.clock = lambda: now + timedelta(minutes=16)
    assert pay(client, reference).json() == first.json()
    assert hotel_availability(client, trip) == reserved
    cancel_url = f"/api/sim-bookings/{reference}/cancel"
    assert client.post(cancel_url).json()["state"] == "cancelled_simulated"
    assert hotel_availability(client, trip) == initial
    assert client.post(cancel_url).json()["state"] == "cancelled_simulated"
    assert hotel_availability(client, trip) == initial
    assert pay(client, reference).status_code == 409
    assert details(client, reference).status_code == 409
    assert client.get(f"/api/sim-bookings/{reference}/itinerary.ics").status_code == 409


def test_inventory_is_atomic_and_private_to_each_session(demo):
    application, client, trip, selection, _ = demo
    session_id = client.cookies["session_id"]
    initial = hotel_availability(client, trip)
    capacity = min(night["available"] for night in initial["nights"])
    selection = {**selection, "activity_ids": []}

    def reserve(_):
        try:
            return application.state.bookings.create(session_id, selection)
        except ServiceError as error:
            return error

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(reserve, range(capacity + 4)))
    held = [result for result in results if isinstance(result, dict)]
    rejected = [result for result in results if isinstance(result, ServiceError)]
    assert len(held) == capacity
    assert all(result.status_code == 409 and result.code == "inventory_unavailable" for result in rejected)
    assert hotel_availability(client, trip)["available"] is False
    reseeded = client.post("/api/search", json={**trip["search_params"], "seed": 7})
    assert reseeded.status_code == 200
    assert client.post("/api/sim-bookings", json={
        **selection, "trip_plan_id": reseeded.json()["id"],
    }).status_code == 409
    with TestClient(application) as stranger:
        assert hotel_availability(stranger, trip) == initial
        reference = held[0]["reference"]
        for suffix in ("", "/itinerary.pdf", "/itinerary.ics"):
            assert stranger.get(f"/api/sim-bookings/{reference}{suffix}").status_code == 404
        assert pay(stranger, reference).status_code == 404
        assert stranger.post(f"/api/sim-bookings/{reference}/cancel").status_code == 404
    now = application.state.store.now()
    application.state.store.clock = lambda: now + timedelta(days=1)
    assert client.get(f"/api/sim-bookings/{held[0]['reference']}").status_code == 404
    with application.state.store.read() as connection:
        assert connection.execute("SELECT count(*) FROM inventory").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM bookings").fetchone()[0] == 0


def test_activity_capacity_failure_rolls_back_the_entire_basket(demo):
    application, client, trip, selection, _ = demo
    session_id = client.cookies["session_id"]
    activity_id = selection["activity_ids"][0]

    def two_places(plan):
        for activity in plan["activities"]:
            if activity["id"] == activity_id:
                activity["capacity_per_slot"] = 2
        return plan

    application.state.store.update_trip(session_id, trip["id"], two_places)
    reference = hold(demo)["reference"]
    before = hotel_availability(client, trip)
    failed = client.post("/api/sim-bookings", json=selection)
    assert failed.status_code == 409
    assert hotel_availability(client, trip) == before
    with application.state.store.read() as connection:
        assert connection.execute("SELECT count(*) FROM bookings").fetchone()[0] == 1
        assert connection.execute(
            "SELECT reserved FROM inventory WHERE kind='activity' AND resource_id=?", (activity_id,)
        ).fetchone()[0] == 2
    assert client.post(f"/api/sim-bookings/{reference}/cancel").status_code == 200
    assert client.post("/api/sim-bookings", json=selection).status_code == 200


def test_confirmed_booking_survives_database_reopen(demo):
    application, client, trip, _, directory = demo
    reference = hold(demo)["reference"]
    assert details(client, reference).status_code == 200
    confirmation = pay(client, reference).json()
    session_id = client.cookies["session_id"]
    application.state.store.close()
    restored = Store(str(directory / "test.sqlite3"))
    try:
        assert restored.get_trip(session_id, trip["id"]) == trip
        assert BookingService(restored).get(session_id, reference) == confirmation
        with restored.read() as connection:
            assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    finally:
        restored.close()


def test_selection_must_match_trip_and_prices_are_server_owned(demo):
    _, client, trip, selection, _ = demo
    other_hotel = next(hotel["id"] for hotel in trip["hotels"] if hotel["id"] != trip["selected_hotel_id"])
    for changes in (
        {"hotel_id": other_hotel}, {"room_type_id": "unknown"}, {"flight_id": "unknown"},
        {"activity_ids": ["ACT-NOT-REAL"]}, {"total_azn": 0}, {"activity_ids": selection["activity_ids"] * 2},
    ):
        response = client.post("/api/sim-bookings", json={**selection, **changes})
        assert response.status_code == 422, response.text
    held = hold(demo)
    assert held["total_azn"] > 0


def test_multiroom_basket_uses_room_units_and_checks_stock(demo):
    application, client, trip, _, _ = demo
    params = {**trip["search_params"], "adults": 6, "children": 0}
    group = client.post("/api/search", json=params)
    assert group.status_code == 200, group.text
    group = group.json()
    response = client.post("/api/sim-bookings", json={
        "trip_plan_id": group["id"], "hotel_id": group["selected_hotel_id"],
        "room_type_id": "family", "activity_ids": [],
    })
    assert response.status_code == 200, response.text
    booking = response.json()
    assert all(item["quantity"] == 2 for item in booking["items"])
    assert all(item["total_azn"] == pytest.approx(item["unit_price_azn"] * 2) for item in booking["items"])
    with application.state.store.read() as connection:
        assert all(row[0] == 2 for row in connection.execute(
            "SELECT reserved FROM inventory WHERE session_id=?", (client.cookies["session_id"],)
        ))


def test_confirmed_exports_are_real_pdf_and_safe_rfc5545_calendar(demo):
    application, client, _, _, _ = demo
    reference = hold(demo)["reference"]
    assert details(client, reference).status_code == 200
    assert pay(client, reference).status_code == 200
    pdf = client.get(f"/api/sim-bookings/{reference}/itinerary.pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF-") and b"%%EOF" in pdf.content
    assert WATERMARK.encode() in pdf.content
    assert b"Basket total:" in pdf.content and b"https://evisa.gov.az" in pdf.content
    calendar_response = client.get(f"/api/sim-bookings/{reference}/itinerary.ics")
    assert calendar_response.status_code == 200
    calendar = calendar_response.content
    assert calendar.startswith(b"BEGIN:VCALENDAR\r\n") and calendar.endswith(b"END:VCALENDAR\r\n")
    assert b"DTSTART:" in calendar and b"Z\r\n" in calendar
    assert all(len(line) <= 75 for line in calendar.split(b"\r\n"))
    assert b"STATUS:CONFIRMED" not in calendar
    booking, trip = application.state.bookings.export(client.cookies["session_id"], reference)
    original_count = calendar.count(b"BEGIN:VEVENT")
    for day in trip["itinerary_days"]:
        for item in day["items"]:
            item["title"] = "Injected, text;\\\r\nEND:VEVENT\r\nBEGIN:VEVENT\r\nSUMMARY:forged"
    escaped = render_ics(booking, trip, catalog.get_facts())
    assert escaped.count(b"\r\nBEGIN:VEVENT\r\n") == original_count
    assert b"\\, text\\;\\\\" in escaped
