"""Exercise a real local API from search through simulated confirmation."""

import argparse
from datetime import date
import http.cookiejar
import json
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener


class DemoClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self, method: str, path: str, payload: dict | None = None):
        body = None if payload is None else json.dumps(payload).encode()
        request = Request(
            self.base_url + path,
            data=body,
            headers={"Content-Type": "application/json"} if body is not None else {},
            method=method,
        )
        try:
            with self.opener.open(request, timeout=30) as response:
                content = response.read()
                media_type = response.headers.get_content_type()
                return (
                    response.status,
                    json.loads(content) if media_type == "application/json" else content,
                )
        except HTTPError as exc:
            content = exc.read()
            return exc.code, json.loads(content) if content else None


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def smoke(base_url: str) -> None:
    client = DemoClient(base_url)
    stranger = DemoClient(base_url)
    year = date.today().year + (date.today() >= date(date.today().year, 4, 10))
    params = {
        "origin": "London",
        "arrival": f"{year}-04-10",
        "departure": f"{year}-04-14",
        "adults": 2,
        "children": 0,
        "budget": "mid-range",
        "interests": ["history", "food"],
        "regions": [],
        "pace": "balanced",
        "seed": 42,
    }
    status, trip = client.request("POST", "/api/search", params)
    require(status in (200, 201), f"Search failed: {status} {trip}")
    require(len(trip["hotels"]) >= 5, "April search returned fewer than five hotels.")
    require(len(trip["itinerary_days"]) == 4, "Four nights did not produce four days.")
    nonstop_origins = {flight["origin"] for flight in trip["flights"] if flight["stops"] == 0}
    require(
        any("LHR" in origin.upper() or "HEATHROW" in origin.upper() for origin in nonstop_origins)
        and any("LGW" in origin.upper() or "GATWICK" in origin.upper() for origin in nonstop_origins),
        "London search must include both Heathrow and Gatwick nonstop examples.",
    )
    status, _ = stranger.request("GET", f"/api/trip/{trip['id']}")
    require(status == 404, "A different session could access the trip.")
    hotel = next(item for item in trip["hotels"] if item["id"] == trip["selected_hotel_id"])
    room = next(item for item in hotel["room_types"] if item["max_occupancy"] >= 2)
    itinerary_ids = list(
        dict.fromkeys(
            item["activity_id"]
            for day in trip["itinerary_days"]
            for item in day["items"]
        )
    )
    status, booking = client.request(
        "POST",
        "/api/sim-bookings",
        {
            "trip_plan_id": trip["id"],
            "hotel_id": hotel["id"],
            "room_type_id": room["id"],
            "activity_ids": itinerary_ids[:2],
            "flight_id": trip["selected_flight_id"],
        },
    )
    require(status in (200, 201), f"Synthetic hold failed: {status} {booking}")
    reference = booking["reference"]
    require(reference.startswith("SIM-BAK-"), "Synthetic reference is not clearly labelled.")
    status, booking = client.request(
        "POST",
        f"/api/sim-bookings/{reference}/details",
        {
            "name": "Demo Traveller",
            "email": "traveller@example.test",
            "nationality": "GB",
            "passport_expiry": f"{year + 1}-12-31",
            "evisa_expiry": f"{year}-05-10",
        },
    )
    require(status == 200, f"Traveller details failed: {status} {booking}")
    status, rejected = client.request(
        "POST",
        f"/api/sim-bookings/{reference}/pay",
        {"card_number": "0000000000000000"},
    )
    require(
        status in (400, 422)
        and "Real cards are not accepted in this demo" in json.dumps(rejected),
        "Payment did not enforce the published test-card allow-list.",
    )
    status, booking = client.request(
        "POST",
        f"/api/sim-bookings/{reference}/pay",
        {"card_number": "4242424242424242"},
    )
    require(status == 200, f"Mock payment failed: {status} {booking}")
    require(booking["state"] == "confirmed_simulated", "Booking did not reach simulated confirmation.")
    require("NOT A RESERVATION" in booking["watermark"], "Confirmation watermark is missing.")
    status, pdf = client.request("GET", f"/api/sim-bookings/{reference}/itinerary.pdf")
    require(status == 200 and pdf.startswith(b"%PDF"), "Itinerary download is not a PDF.")
    status, calendar = client.request("GET", f"/api/sim-bookings/{reference}/itinerary.ics")
    require(
        status == 200
        and b"BEGIN:VCALENDAR" in calendar
        and b"BEGIN:VEVENT" in calendar
        and b"SIMULATED" in calendar,
        "Calendar export is incomplete or not marked as simulated.",
    )
    status, _ = stranger.request("GET", f"/api/sim-bookings/{reference}")
    require(status == 404, "A different session could access the confirmation.")
    print(
        json.dumps(
            {
                "result": "passed",
                "reference": reference,
                "hotels": len(trip["hotels"]),
                "itinerary_days": len(trip["itinerary_days"]),
                "pdf_bytes": len(pdf),
                "calendar_bytes": len(calendar),
                "checks": [
                    "London April trip",
                    "trip and booking session isolation",
                    "synthetic hold",
                    "test-card-only payment",
                    "simulated confirmation",
                    "PDF and calendar downloads",
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    smoke(args.base_url)
