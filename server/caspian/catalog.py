"""Dated, offline catalogue for a synthetic travel demonstration, never a supplier feed."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from functools import lru_cache
from hashlib import sha256
import json
import math
from pathlib import Path
import random
import re
from typing import Any


BASELINE_DATE = "2026-11-13"
INTERESTS = ["history", "architecture", "food", "nature", "adventure", "wine", "family", "nightlife"]
EXCHANGE_RATES = {
    "base": "AZN",
    "as_of": BASELINE_DATE,
    "is_indicative": True,
    "rates": {"AZN": 1.0, "GBP": 0.46, "USD": 0.59, "EUR": 0.54},
}
SCORE_WEIGHTS = {
    "season_fit": 0.35,
    "interest_match": 0.30,
    "budget_fit": 0.15,
    "travel_feasibility": 0.10,
    "diversity": 0.10,
}
FACT_CONFIDENCE = (
    "User specification baseline, 2026-11-13; not independently verified by this application. "
    "Confirm with the linked source before travel."
)


@lru_cache(maxsize=1)
def _seed_data() -> dict:
    return json.loads((Path(__file__).parent / "data" / "seed.json").read_text(encoding="utf-8"))


def seeded_random(seed: int, *parts: Any) -> random.Random:
    payload = json.dumps([seed, *parts], separators=(",", ":"), ensure_ascii=True, sort_keys=True)
    return random.Random(int.from_bytes(sha256(payload.encode("utf-8")).digest(), "big"))


def parse_date(value: Any, name: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"{name} must be a date in YYYY-MM-DD format.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} is not a valid calendar date.") from exc


def integer(value: Any, name: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not (
        isinstance(value, int) or (isinstance(value, str) and re.fullmatch(r"-?\d+", value))
    ):
        raise ValueError(f"{name} must be an integer.")
    result = int(value)
    if not minimum <= result <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return result


def stay_dates(checkin: str, checkout: str) -> list[date]:
    start, end = parse_date(checkin, "arrival/checkin"), parse_date(checkout, "departure/checkout")
    nights = (end - start).days
    if not 1 <= nights <= 60:
        raise ValueError("Departure must follow arrival by 1–60 nights.")
    return [start + timedelta(days=offset) for offset in range(nights)]


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    chord = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(chord)))


def novruz_event(day: date) -> dict | None:
    event = _seed_data()["novruz"]
    return deepcopy(event) if day.month == event["month"] and event["first_day"] <= day.day <= event["last_day"] else None


def gabala_rail_day(day: date) -> bool:
    # Tentative Novruz overlays are deliberately not evidence of a holiday train.
    return day.weekday() >= 5 or day.isoformat() in _seed_data()["confirmed_rail_holidays"]


def get_facts(today: date | None = None) -> list[dict]:
    reference_day = date.today() if today is None else today
    if type(reference_day) is not date:
        raise ValueError("today must be a date.")
    stale = (reference_day - date.fromisoformat(BASELINE_DATE)).days > 90
    evisa = "https://evisa.gov.az/en/information"
    advice = "https://www.gov.uk/foreign-travel-advice/azerbaijan"
    rail = "https://ticket.ady.az"
    places = "https://www.lonelyplanet.com/articles/best-things-to-do-in-baku-azerbaijan"
    rows = [
        ("visa-route", "Entry", "The specification records UK eligibility for ASAN e-visas; other nationalities must check the official eligibility list. Eligibility is not a visa approval.", None, None, evisa),
        ("visa-processing", "Entry", "Baseline ASAN processing: standard within 3 working days or urgent within 3 hours; reconfirm service and fees.", "3 working days / 3 hours", None, evisa),
        ("visa-fee", "Entry", "Baseline standard e-visa: USD 20 state fee plus USD 9 service fee, not an urgent-service quote.", 29, "USD", evisa),
        ("visa-stay", "Entry", "Baseline single-entry e-visa permits a stay of up to 30 days. Longer stays require official advice and a different permission; the demo does not issue visas.", 30, "days", evisa),
        ("passport", "Entry", "Passport expiry must be at least 3 months after the e-visa expiry date, not merely after the planned departure from Azerbaijan.", 3, "calendar months", evisa),
        ("registration", "Entry", "The specification states that visitors staying more than 15 days must register with the State Migration Service; reconfirm current rules and nationality-specific exceptions.", 15, "days", "https://entryrules.com/countries/azerbaijan/gb"),
        ("land-border", "Entry and safety", "The early-November-2026 specification states that foreign-tourist entry by land and ferry is closed. This is not live-verified. Plan arrival by air; no Tbilisi or other cross-border rail itinerary is recommended.", None, None, "https://4ttransfer.com/trains-azerbaijan/"),
        ("h1", "Transport", "Baseline H1 Airport Express: GYD–Koroglu–28 May, 24/7, about every 15 minutes and about 30 minutes; AZN 1.30 per traveller per journey. Listed payment options include bank card, Apple Pay, Google Pay, BakiKart, m10 and Birbank.", 1.30, "AZN per traveller", "https://www.bakubus.az/quality"),
        ("bakikart", "Transport", "Baseline reusable BakiKart purchase is AZN 2, before top-up, at airport or metro machines. The demo budgets one card per traveller; discounts are not assumed.", 2, "AZN per card", "https://www.bakubus.az/quality"),
        ("metro", "Transport", "Baku Metro fare is approximately AZN 0.60 per ride on BakiKart in the specification. Sources disagree; this is approximate, not a live fare guarantee.", 0.60, "AZN per ride (approximate)", "https://metro.gov.az/en"),
        ("rail-ganja", "Transport", "Baseline Baku–Ganja rail is daily, around 4 hours, from approximately AZN 12.80 one way. Specific departures and seats must be checked with ADY.", 12.80, "AZN per traveller, from", "https://4ttransfer.com/trains-azerbaijan/"),
        ("rail-gabala", "Transport", "Baseline Baku–Gabala rail runs on weekends and confirmed holidays, 07:30–11:06, from AZN 12 one way. No weekday holiday services or return departure times are inferred by the demo.", 12, "AZN per traveller, from", "https://4ttransfer.com/trains-azerbaijan/"),
        ("rail-sheki", "Transport", "The specification announces Baku–Sheki/Balakan night-train resumption from 20 November 2026, from about AZN 14.80. The timetable is unconfirmed; a road fallback is essential. No service is assumed before that date.", 14.80, "AZN per traveller, from", "https://4ttransfer.com/trains-azerbaijan/"),
        ("rail-tickets", "Transport", "Check ADY at ticket.ady.az, ADY Mobile or station offices; the specification says an original passport is needed. Nothing here reserves a seat.", None, None, rail),
        ("road-routes", "Transport", "Guba, Shahdag, Shamakhi and Gobustan require road travel. All road times, taxi fares and transfer prices in this demo are synthetic planning estimates, not operator quotes; traffic and mountain access can change them.", None, None, "https://4ttransfer.com/trains-azerbaijan/"),
        ("flight-lhr", "Flights", "Baseline AZAL LHR Terminal 4–GYD Terminal 1: 3 nonstops weekly, departure about 22:05, arrival about 07:35 next day in winter, duration about 5h30. Weekdays, seasonal clock changes and operating dates require airline confirmation.", 330, "minutes (approximate)", "https://www.directflights.com/LHR-GYD"),
        ("flight-lgw", "Flights", "Baseline AZAL LGW North–GYD Terminal 1: 4 nonstops weekly, departure around 10:25–11:25, duration about 5h30. The demo never asserts that a flight operates on a requested weekday.", 330, "minutes (approximate)", "https://www.directflights.com/LGW-GYD"),
        ("flight-connections", "Flights", "Baseline London one-stop options include Turkish Airlines via Istanbul, about 8h50–9h15, and indicative routings via Warsaw, Frankfurt or Vienna, about 8–11 hours. Connection times and terminals require reconfirmation.", None, None, "https://www.flightroutes.com/LHR-GYD"),
        ("old-city", "Places", "Baku's UNESCO-listed walled Old City, inscribed in 2000, contains the Maiden Tower and Palace of the Shirvanshahs.", 2000, "inscription year", "https://whc.unesco.org/en/list/958/"),
        ("baku-landmarks", "Places", "The Boulevard, Carpet Museum, Heydar Aliyev Center, Martyrs' Lane and Absheron fire landmarks are real places. Demo opening windows, operators and admission slots are not official schedules.", None, None, places),
        ("gobustan", "Places", "Gobustan's real rock-art landscape lies south-west of Baku. Mud-volcano access is by road and can be unsuitable after rain; the demo has no live conditions feed.", None, None, "https://whc.unesco.org/en/list/1076/"),
        ("sheki", "Places", "Sheki's historic centre and Khan's Palace are real landmarks. A full local day plus a Baku road return should not be treated as a short city excursion.", None, None, "https://whc.unesco.org/en/list/1549/"),
        ("regional-landmarks", "Places", "Gabala/Tufandag, Nohur Lake, Guba, Khinalig and Shamakhi are real destinations; this application supplies synthetic experiences, not real tour-operator products.", None, None, "https://azerbaijan.travel/"),
        ("shahdag-ski", "Seasonality", "The specification permits Shahdag ski recommendations only during December–March. Snow, lift operation, roads and individual skiing suitability are not verified.", "December–March", None, "https://azerbaijan.travel/"),
        ("seasonal-weather", "Seasonality", "Specification climate heuristic, not a forecast: winter is windier, mountain conditions harsher, summers hot, and spring/autumn often more comfortable. Indoor museum boosts use these seasonal assumptions, not invented current weather.", None, None, places),
        ("novruz", "Events", "The demo applies a tentative 20–26 March Novruz overlay, with a synthetic 1.35–1.60 hotel multiplier. Dates are explicitly unconfirmed and cannot establish holiday rail services.", "Tentative; confirm dates", None, "https://azerbaijan.travel/"),
        ("geography", "Geography", "Hotel coordinates are fictional points in approximate real districts. Nearest seeded metro stations and straight-line distances are computed using approximate station coordinates, not a surveyed or accessible walking route.", None, None, "https://metro.gov.az/en"),
        ("synthetic-pricing", "Demonstration data", "All twelve hotels are fictional. Seeded rates apply weekend ×1.10, low season ×0.80, tentative event ×1.35–1.60, family room ×1.40 and suite ×2.20. No availability or rate comes from a real supplier.", None, None, "https://azerbaijan.travel/"),
        ("synthetic-activities", "Demonstration data", "Real landmark names ground the catalogue only. Activity prices, opening windows, capacities, slots and operators are synthetic per-traveller demo data; verify actual access separately.", None, None, places),
        ("synthetic-flights", "Demonstration data", "Flight fare bands are seeded illustrative GBP return-fare estimates per traveller, not a quote. Only an indicative outbound pattern is displayed; return schedules are not asserted. Flights are never booked.", None, None, "https://www.flightroutes.com/LHR-GYD"),
        ("currency", "Money", "The currency is AZN. The specification describes broad card acceptance in Baku and greater need for cash in the regions; carry a backup payment method.", "AZN", None, "https://azerbaijan.travel/"),
        ("exchange-rates", "Demonstration data", "Illustrative conversion table dated 2026-11-13: 1 AZN = 0.46 GBP, 0.59 USD or 0.54 EUR. These are invented demo rates, not live or historically verified market rates.", "Illustrative, not market data", None, "https://www.cbar.az/"),
        ("insurance", "Preparation", "Check suitable travel insurance, including mountain activities and winter sports where relevant; the demo does not assess coverage.", None, None, advice),
        ("mosques", "Preparation", "Dress modestly and respect local guidance when visiting mosques and places of worship.", None, None, advice),
        ("safety", "Safety", "Static PoC allow-list only: Baku/Absheron, Gobustan, Shamakhi, Sheki, Gabala, Guba/Khinalig, Shahdag and Ganja corridors. No Armenia-border, disputed-territory or cross-border routes are offered. This is not live FCDO verification or a guarantee of safety; check official advice before travel.", None, None, advice),
    ]
    return [
        {
            "id": fact_id, "topic": topic, "statement": statement, "value": value, "unit": unit,
            "source_url": url, "last_verified": BASELINE_DATE, "confidence": FACT_CONFIDENCE,
            "reverify_required": stale,
        }
        for fact_id, topic, statement, value, unit, url in rows
    ]


def get_destinations() -> list[dict]:
    return [{"id": item["id"], "name": item["name"]} for item in _seed_data()["destinations"]]


def destination_coordinates(destination_id: str) -> tuple[float, float]:
    for item in _seed_data()["destinations"]:
        if item["id"] == destination_id:
            return item["lat"], item["lon"]
    extra = {"gobustan": (40.11, 49.378), "absheron": (40.4154, 50.0085), "shamakhi": (40.632, 48.637)}
    if destination_id in extra:
        return extra[destination_id]
    raise ValueError(f"Destination is outside the static approved catalogue: {destination_id}.")


def activity_context(activity_id: str) -> dict:
    for item in _seed_data()["activities"]:
        if item["id"] == activity_id:
            return deepcopy(item)
    raise ValueError(f"Unknown activity ID: {activity_id}.")


def get_activities() -> list[dict]:
    internal = {"closed_weekdays", "low_intensity", "strict_season", "travel_region", "adults_only"}
    return [
        {
            **{key: deepcopy(value) for key, value in item.items() if key not in internal},
            "is_synthetic": True,
            "score": {**{key: 0.0 for key in SCORE_WEIGHTS}, "total": 0.0},
        }
        for item in _seed_data()["activities"]
    ]


def _room_types() -> list[dict]:
    rooms = [
        {"id": "standard", "name": "Standard double", "max_occupancy": 2, "rate_multiplier": 1.0, "inventory": 12},
        {"id": "family", "name": "Family room", "max_occupancy": 4, "rate_multiplier": 1.4, "inventory": 6},
        {"id": "suite", "name": "Suite", "max_occupancy": 3, "rate_multiplier": 2.2, "inventory": 3},
    ]
    return [{**room, "is_synthetic": True, "grounding_refs": ["synthetic-pricing"]} for room in rooms]


def _hotel(hotel_id: str) -> dict:
    for item in _seed_data()["hotels"]:
        if item["id"] == hotel_id:
            return deepcopy(item)
    raise ValueError(f"Unknown hotel ID: {hotel_id}.")


def availability(
    hotel_id: str, checkin: str, checkout: str, guests: int = 2,
    room_type_id: str | None = None, seed: int = 42,
) -> dict:
    hotel = _hotel(hotel_id)
    dates = stay_dates(checkin, checkout)
    guests = integer(guests, "guests", 1, 12)
    seed = integer(seed, "seed", 0, 2**32 - 1)
    room_id = room_type_id if room_type_id is not None else ("standard" if guests <= 2 else "family")
    room = next((item for item in _room_types() if item["id"] == room_id), None)
    if room is None:
        raise ValueError(f"Unknown room type ID: {room_id}.")
    rooms_required = math.ceil(guests / room["max_occupancy"])
    if room_type_id is not None and guests <= 4 and rooms_required > 1:
        raise ValueError(f"{room['name']} accommodates at most {room['max_occupancy']} guests; choose a suitable room.")
    variation = seeded_random(seed, hotel_id, "base-rate").uniform(0.96, 1.04)
    nights = []
    for day in dates:
        weekend = 1.10 if day.weekday() >= 5 else 1.0
        low_season = day.month in ((4, 5, 6, 7, 8, 9, 10, 11) if hotel["destination_id"] == "shahdag" else (11, 12, 1, 2))
        event = novruz_event(day)
        event_multiplier = round(seeded_random(seed, hotel_id, day.isoformat(), "event").uniform(1.35, 1.60), 4) if event else 1.0
        nightly = round(hotel["base_rate_azn"] * variation * weekend * (0.80 if low_season else 1.0) * event_multiplier * room["rate_multiplier"], 2)
        inventory = room["inventory"]
        reserved = seeded_random(seed, hotel_id, room_id, day.isoformat(), "inventory").randint(0, max(1, inventory // 2))
        remaining = max(0, inventory - reserved - (math.ceil(inventory * 0.35) if event else 0))
        nights.append({
            "date": day.isoformat(), "price_azn": round(nightly * rooms_required, 2),
            "available": remaining, "event": "Novruz — tentative 20–26 March; confirm dates" if event else None,
            "unit_price_azn": nightly, "is_synthetic": True,
            "grounding_refs": ["synthetic-pricing", "novruz"] if event else ["synthetic-pricing"],
        })
    return {
        "hotel_id": hotel_id, "room_type_id": room_id, "nights": nights,
        "available": all(item["available"] >= rooms_required for item in nights),
        "total_azn": round(sum(item["price_azn"] for item in nights), 2),
        "is_synthetic": True, "grounding_refs": ["synthetic-pricing", "novruz"],
        "rooms_required": rooms_required,
    }


def _number(value: Any, name: str) -> float:
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{name} must be a finite number.") from exc
    if isinstance(value, bool) or not math.isfinite(result) or result < 0:
        raise ValueError(f"{name} must be a non-negative finite number.")
    return result


def get_hotels(params: dict | None = None) -> list[dict]:
    if params is not None and not isinstance(params, dict):
        raise ValueError("Hotel filters must be an object.")
    params = params or {}
    checkin, checkout = params.get("checkin", params.get("arrival")), params.get("checkout", params.get("departure"))
    if (checkin is None) != (checkout is None):
        raise ValueError("Both checkin and checkout are required for dated prices.")
    if checkin is not None:
        stay_dates(checkin, checkout)
    guests = integer(params.get("guests", integer(params.get("adults", 2), "adults", 1, 12) + integer(params.get("children", 0), "children", 0, 11)), "guests", 1, 12)
    seed = integer(params.get("seed", 42), "seed", 0, 2**32 - 1)
    allowed = {item["id"] for item in get_destinations()}
    destination = params.get("destination", params.get("destination_id"))
    regions = params.get("regions")
    if destination is not None and (not isinstance(destination, str) or destination not in allowed):
        raise ValueError(f"Unknown or unapproved destination: {destination}.")
    if regions is not None and (not isinstance(regions, list) or any(not isinstance(region, str) or region not in allowed for region in regions)):
        raise ValueError("regions must contain only approved destination IDs.")
    if params.get("room_type_id") is not None and params["room_type_id"] not in [room["id"] for room in _room_types()]:
        raise ValueError("Unknown room type ID.")
    currency = str(params.get("currency", "AZN")).upper()
    if currency not in EXCHANGE_RATES["rates"]:
        raise ValueError("Unknown currency.")
    thresholds = {key: _number(params[key], key) for key in ("price_min", "price_max", "min_price", "max_price", "price_min_gbp", "price_max_gbp", "guest_score", "min_guest_score", "distance_to_metro_m", "max_distance_to_metro_m", "max_metro_distance") if params.get(key) is not None}
    min_price = thresholds.get("price_min", thresholds.get("min_price", 0)) / EXCHANGE_RATES["rates"][currency]
    max_price = thresholds.get("price_max", thresholds.get("max_price", float("inf"))) / EXCHANGE_RATES["rates"][currency]
    min_price = max(min_price, thresholds.get("price_min_gbp", 0) / EXCHANGE_RATES["rates"]["GBP"])
    max_price = min(max_price, thresholds.get("price_max_gbp", float("inf")) / EXCHANGE_RATES["rates"]["GBP"])
    if min_price > max_price:
        raise ValueError("Minimum nightly price cannot exceed maximum price.")
    required_amenities = params.get("amenities", [])
    if isinstance(required_amenities, str):
        required_amenities = [item.strip() for item in required_amenities.split(",") if item.strip()]
    if not isinstance(required_amenities, list) or any(not isinstance(item, str) for item in required_amenities):
        raise ValueError("amenities must be a list of strings.")
    stars = params.get("stars")
    if stars is not None:
        stars = integer(stars, "stars", 1, 5)
    min_stars = integer(params.get("min_stars", 1), "min_stars", 1, 5)
    family = params.get("family_friendly", params.get("family"))
    if isinstance(family, str):
        if family.lower() not in ("true", "false", "1", "0"):
            raise ValueError("family_friendly must be a boolean.")
        family = family.lower() in ("true", "1")
    if family is not None and not isinstance(family, bool):
        raise ValueError("family_friendly must be a boolean.")
    results = []
    for raw in _seed_data()["hotels"]:
        hotel = deepcopy(raw)
        if destination and hotel["destination_id"] != destination:
            continue
        if regions is not None and hotel["destination_id"] not in {"baku", *regions}:
            continue
        if params.get("district") and str(params["district"]).casefold() not in hotel["district"].casefold():
            continue
        if (stars is not None and hotel["stars"] != stars) or hotel["stars"] < min_stars:
            continue
        if family is not None and hotel["family_friendly"] != family:
            continue
        if hotel["guest_score"] < thresholds.get("min_guest_score", thresholds.get("guest_score", 0)):
            continue
        if not set(required_amenities).issubset(hotel["amenities"]):
            continue
        metro = None
        distance = None
        walking = None
        if hotel["destination_id"] == "baku":
            metro = min(_seed_data()["metro"], key=lambda station: distance_km(hotel["lat"], hotel["lon"], station["lat"], station["lon"]))
            distance = round(distance_km(hotel["lat"], hotel["lon"], metro["lat"], metro["lon"]) * 1000)
            old_city_km = distance_km(hotel["lat"], hotel["lon"], 40.3667, 49.8372)
            walking = math.ceil(old_city_km * 1.3 / 4.5 * 60) if old_city_km <= 8 else None
        maximum_distance = thresholds.get("max_distance_to_metro_m", thresholds.get("max_metro_distance", thresholds.get("distance_to_metro_m")))
        if maximum_distance is not None and (distance is None or distance > maximum_distance):
            continue
        quote = availability(hotel["id"], checkin, checkout, guests, params.get("room_type_id"), seed) if checkin is not None else None
        rooms = math.ceil(guests / (2 if guests <= 2 else 4))
        total = quote["total_azn"] if quote else round(hotel["base_rate_azn"] * (1.4 if guests > 2 else 1) * rooms, 2)
        price = round(total / len(quote["nights"]), 2) if quote else total
        if not min_price <= price <= max_price:
            continue
        hotel.update({
            "price_per_night_azn": price, "price_total_azn": total,
            "nearest_metro": metro["name"] if metro else None, "distance_to_metro_m": distance,
            "walking_min_to_old_city": walking,
            "airport_stop": "Direct road transfer from GYD (Mardakan)" if hotel["id"] == "HTL-BAK-007" else "28 May",
            "cancellation_policy": "Demonstration only: a simulated reservation can be cancelled without a real fee. No supplier reservation exists.",
            "room_types": _room_types(), "is_synthetic": True,
            "grounding_refs": ["geography", "synthetic-pricing", "h1", "novruz"],
            "available": quote["available"] if quote else True,
            "rooms_required": quote["rooms_required"] if quote else rooms,
        })
        results.append(hotel)
    return results
