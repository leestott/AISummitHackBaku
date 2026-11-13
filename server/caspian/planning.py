"""Deterministic, offline planning shared by the API and hosted-agent read-only tools."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import date, timedelta
from hashlib import sha256
import json
import math
from typing import Any

from .catalog import (
    BASELINE_DATE, EXCHANGE_RATES, INTERESTS, SCORE_WEIGHTS, activity_context,
    destination_coordinates, distance_km, gabala_rail_day, get_activities,
    get_destinations, get_facts, get_hotels, integer, novruz_event, parse_date,
    seeded_random, stay_dates,
)


_ROAD_MINUTES = {"sheki": 300, "gabala": 240, "guba": 180, "shahdag": 210, "ganja": 300, "gobustan": 75, "absheron": 60, "shamakhi": 120}
_ROAD_FARES = {"sheki": 45, "gabala": 35, "guba": 30, "shahdag": 40, "ganja": 45, "gobustan": 22, "absheron": 18, "shamakhi": 25}
_PACE = {
    "relaxed": {"items": 2, "active": 300, "start": 570, "end": 1200, "excursion": 600},
    "balanced": {"items": 3, "active": 540, "start": 540, "end": 1260, "excursion": 900},
    "packed": {"items": 5, "active": 720, "start": 510, "end": 1320, "excursion": 960},
}
_SHEKI_START = date(2026, 11, 20)


def normalize_search(params: dict) -> dict:
    if not isinstance(params, dict):
        raise ValueError("Search parameters must be an object.")
    origin = params.get("origin", "London")
    if not isinstance(origin, str) or not origin.strip() or len(origin.strip()) > 100:
        raise ValueError("origin must be a city or airport name of 1–100 characters.")
    arrival, departure = params.get("arrival"), params.get("departure")
    stay_dates(arrival, departure)
    adults = integer(params.get("adults", 2), "adults", 1, 12)
    children = integer(params.get("children", 0), "children", 0, 11)
    if adults + children > 12:
        raise ValueError("The demo supports at most 12 travellers per trip.")
    budget, pace = params.get("budget", "mid-range"), params.get("pace", "balanced")
    if budget not in ("economy", "mid-range", "premium"):
        raise ValueError("budget must be economy, mid-range or premium.")
    if not isinstance(pace, str) or pace not in _PACE:
        raise ValueError("pace must be relaxed, balanced or packed.")
    interests = params.get("interests", ["history", "food"])
    if not isinstance(interests, list) or any(not isinstance(item, str) or item not in INTERESTS for item in interests):
        raise ValueError(f"interests must be a list drawn from: {', '.join(INTERESTS)}.")
    regions = params.get("regions", [])
    allowed = {item["id"] for item in get_destinations()}
    if not isinstance(regions, list) or any(not isinstance(item, str) or item not in allowed for item in regions):
        raise ValueError("regions must contain only baku, sheki, gabala, guba, shahdag or ganja. Other regions and cross-border routes are not approved.")
    return {
        "origin": origin.strip(), "arrival": arrival, "departure": departure,
        "adults": adults, "children": children, "budget": budget,
        "interests": list(dict.fromkeys(interests)), "regions": list(dict.fromkeys(["baku", *regions])),
        "pace": pace, "seed": integer(params.get("seed", 42), "seed", 0, 2**32 - 1),
    }


def _minutes(clock: str) -> int:
    hour, minute = map(int, clock.split(":"))
    return hour * 60 + minute


def _clock(minutes: int) -> str:
    if not 0 <= minutes < 24 * 60:
        raise ValueError("A visit cannot spill into an unrepresented itinerary day.")
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _last_sunday(year: int, month: int) -> date:
    last = date(year, month + 1, 1) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() + 1) % 7)


def _london_utc_offset(day: date) -> int:
    # All seeded departures are after the clock-change hour; no tzdata install is needed.
    return int(_last_sunday(day.year, 3) <= day < _last_sunday(day.year, 10))


def get_flights(origin: str, depart: str, return_date: str, seed: int = 42) -> list[dict]:
    if not isinstance(origin, str) or not origin.strip():
        raise ValueError("origin must be a non-empty city or airport.")
    departure_day, return_day = parse_date(depart, "depart"), parse_date(return_date, "return_date")
    if return_day <= departure_day:
        raise ValueError("return_date must follow depart.")
    seed = integer(seed, "seed", 0, 2**32 - 1)
    query = origin.strip().casefold()
    london = {"london", "lon", "london (lon)", "london, uk", "london uk"}
    heathrow = {"lhr", "heathrow", "london heathrow", "london heathrow (lhr)"}
    gatwick = {"lgw", "gatwick", "london gatwick", "london gatwick (lgw)"}
    if query not in london | heathrow | gatwick:
        return []
    patterns = []
    if query not in gatwick:
        patterns.append(("FLT-AZAL-LHR", "LHR", "Azerbaijan Airlines (AZAL)", "22:05", 330, None, "LHR Terminal 4 → GYD Terminal 1", 255, 405, "3 nonstops weekly in the specification; weekdays not provided", "https://www.azal.az/en/", "flight-lhr"))
    if query not in heathrow:
        patterns.append(("FLT-AZAL-LGW", "LGW", "Azerbaijan Airlines (AZAL)", "10:25", 330, None, "LGW North Terminal → GYD Terminal 1", 240, 385, "4 nonstops weekly; baseline departure range 10:25–11:25, not a confirmed date-specific departure", "https://www.azal.az/en/", "flight-lgw"))
    connection_origin = "LGW" if query in gatwick else "LHR"
    terminal = "LGW South Terminal" if query in gatwick else "LHR Terminal 2"
    patterns.append(("FLT-TK-IST", connection_origin, "Turkish Airlines", "09:00", 535, "Istanbul (IST)", f"{terminal} → IST main terminal → GYD Terminal 1", 285, 465, "Daily one-stop route pattern; illustrative connection within the baseline 8h50–9h15 range", "https://www.turkishairlines.com/", "flight-connections"))
    if query not in gatwick:
        patterns.extend([
            ("FLT-LOT-WAW", "LHR", "LOT Polish Airlines", "08:20", 570, "Warsaw (WAW)", "LHR Terminal 2 → WAW main terminal → GYD Terminal 1", 270, 450, "Indicative known-route connection via Warsaw; no operating weekdays or connection availability asserted", "https://www.lot.com/", "flight-connections"),
            ("FLT-LH-FRA", "LHR", "Lufthansa", "09:30", 540, "Frankfurt (FRA)", "LHR Terminal 2 → FRA Terminal 1 → GYD Terminal 1", 295, 485, "Indicative known-route connection via Frankfurt; reconfirm carrier, terminals and connection", "https://www.lufthansa.com/", "flight-connections"),
        ])
    flights = []
    for flight_id, airport, carrier, departure_time, duration, via, terminals, low, high, note, airline, fact in patterns:
        arrival_minutes = _minutes(departure_time) + duration + (4 - _london_utc_offset(departure_day)) * 60
        offset, local_minutes = divmod(arrival_minutes, 24 * 60)
        fare_adjustment = seeded_random(seed, flight_id, depart, return_date, "fare").randint(-15, 25)
        flights.append({
            "id": flight_id, "origin": airport, "destination": "GYD", "carrier": carrier,
            "depart_local": departure_time, "arrive_local": _clock(local_minutes),
            "arrival_day_offset": offset, "duration_min": duration, "stops": 0 if via is None else 1,
            "via": via, "terminals": terminals, "fare_min_gbp": low + fare_adjustment,
            "fare_max_gbp": high + fare_adjustment,
            "schedule_note": f"{note}. Example outbound date {depart}; reconfirm actual operating days, local times, terminals and return flights on the airline site. Baseline {BASELINE_DATE}, not independently reverified. Fares are synthetic GBP return estimates per traveller, not a quote.",
            "is_indicative": True, "is_synthetic": True, "airline_url": airline,
            "early_checkin_note": "Overnight arrival: request early check-in directly; it is not guaranteed or booked. The first itinerary day is light with time to rest." if offset else None,
            "grounding_refs": [fact, "synthetic-flights"], "departure_date": depart,
            "arrival_date": (departure_day + timedelta(days=offset)).isoformat(),
        })
    return flights


def _arrival_flights(params: dict) -> list[dict]:
    flights = get_flights(params["origin"], params["arrival"], params["departure"], params["seed"])
    arrival_day = parse_date(params["arrival"], "arrival")
    shifted: dict[str, list[dict]] = {}
    for index, flight in enumerate(flights):
        if flight["arrival_day_offset"]:
            departure_day = (arrival_day - timedelta(days=flight["arrival_day_offset"])).isoformat()
            if departure_day not in shifted:
                shifted[departure_day] = get_flights(params["origin"], departure_day, params["departure"], params["seed"])
            flights[index] = next(item for item in shifted[departure_day] if item["id"] == flight["id"])
    return flights


def _approved_hotel(params: dict, hotel: dict) -> dict:
    if not isinstance(hotel, dict) or not isinstance(hotel.get("id"), str):
        raise ValueError("A catalogue hotel is required.")
    known = next((item for item in get_hotels(params) if item["id"] == hotel["id"]), None)
    if known is None:
        raise ValueError("Selected hotel is unknown or outside the requested regions.")
    return known


def _eligible(activity: dict, day: date, params: dict) -> bool:
    context = activity_context(activity["id"])
    return (
        activity["destination_id"] in params["regions"]
        and (not context.get("strict_season") or day.month in activity["season_months"])
        and day.weekday() not in context.get("closed_weekdays", [])
        and not (params["children"] and context.get("adults_only"))
        and params["adults"] + params["children"] <= activity["capacity_per_slot"]
    )


def _point_region(point: dict) -> str:
    return activity_context(point["id"])["travel_region"] if point["id"].startswith("ACT-") else point["destination_id"]


def _point_coordinates(point: dict) -> tuple[float, float]:
    if point["id"] == "ACT-013":
        return destination_coordinates("guba")
    return point["lat"], point["lon"]


def _travel_minutes(origin: dict, target: dict) -> int:
    from_region, to_region = _point_region(origin), _point_region(target)
    origin_lat, origin_lon = _point_coordinates(origin)
    target_lat, target_lon = _point_coordinates(target)
    if from_region != to_region and "baku" in (from_region, to_region):
        remote = to_region if from_region == "baku" else from_region
        city_point = origin if from_region == "baku" else target
        city_distance = distance_km(city_point["lat"], city_point["lon"], 40.3796, 49.8488)
        city_extra = max(0, math.ceil((city_distance - 5) * 1.5))
        return _ROAD_MINUTES[remote] + city_extra
    km = distance_km(origin_lat, origin_lon, target_lat, target_lon)
    if km <= 1.1:
        return max(5, math.ceil(km * 1.3 / 4.5 * 60))
    return math.ceil(km * (1.3 if from_region == to_region else 1.6) / (25 if from_region == to_region else 50) * 60 + 10)


def _season_score(activity: dict, day: date) -> float:
    if activity["id"] == "ACT-014":
        return 100.0 if day.month in (12, 1, 2, 3) else 0.0
    heavy = day.month in (11, 12, 1, 2)
    if activity["indoor"]:
        score = 100 if heavy else 85
    elif heavy:
        score = 25 if activity_context(activity["id"])["travel_region"] in ("guba", "gabala", "gobustan", "shahdag") else 40
    elif day.month in (6, 7, 8):
        score = 95 if activity_context(activity["id"])["travel_region"] in ("guba", "gabala") or activity["id"] == "ACT-007" else 65
    else:
        score = 100 if day.month in activity["season_months"] else 65
    if day.month in (9, 10, 11) and "wine" in activity["categories"]:
        score = 100
    if novruz_event(day) and set(activity["categories"]) & {"history", "food", "architecture"}:
        score = min(100, score + 10)
    return float(score)


def recommend_activities(params: dict, hotel: dict) -> list[dict]:
    params = normalize_search(params)
    hotel = _approved_hotel(params, hotel)
    dates = stay_dates(params["arrival"], params["departure"])
    candidates = [activity for activity in get_activities() if any(_eligible(activity, day, params) for day in dates)]
    primary_counts = Counter(activity["categories"][0] for activity in candidates)
    limit = {"economy": 35, "mid-range": 90, "premium": 180}[params["budget"]]
    result = []
    for activity in candidates:
        eligible_dates = [day for day in dates if _eligible(activity, day, params)]
        travel = _travel_minutes(hotel, activity) * 2
        feasible = activity["duration_min"] + travel <= _PACE[params["pace"]]["excursion"]
        score = {
            "season_fit": round(sum(_season_score(activity, day) for day in eligible_dates) / len(eligible_dates), 2),
            "interest_match": round(100 * len(set(params["interests"]) & set(activity["categories"])) / len(params["interests"]), 2) if params["interests"] else 50.0,
            "budget_fit": round(min(100.0, 100 * limit / max(1, activity["price_azn"])), 2),
            "travel_feasibility": round(max(10.0, 100 - travel / 8), 2) if feasible else 0.0,
            "diversity": round(100 / math.sqrt(primary_counts[activity["categories"][0]]), 2),
        }
        score["total"] = round(sum(score[key] * weight for key, weight in SCORE_WEIGHTS.items()), 2)
        activity["score"] = score
        result.append(activity)
    return sorted(result, key=lambda activity: (-activity["score"]["total"], seeded_random(params["seed"], "ranking", activity["id"]).random(), activity["id"]))


def _arrival_ready(params: dict, hotel: dict, flight: dict | None) -> tuple[int, bool]:
    if flight is None:
        return 9 * 60, False
    transfer = 30 + (25 if hotel["destination_id"] == "baku" else _ROAD_MINUTES[hotel["destination_id"]] + 20)
    if hotel["id"] == "HTL-BAK-007":
        transfer = 35
    overnight = bool(flight["arrival_day_offset"])
    ready = _minutes(flight["arrive_local"]) + 90 + transfer + (90 if overnight else 0)
    return max(11 * 60, ready) if overnight else ready, overnight


def _schedule_day(
    day: date, activities: list[dict], params: dict, hotel: dict, flight: dict | None,
) -> list[dict]:
    if not activities:
        return []
    config = _PACE[params["pace"]]
    first_day = day.isoformat() == params["arrival"]
    ready, overnight = _arrival_ready(params, hotel, flight) if first_day else (0, False)
    if len(activities) > (1 if overnight else config["items"]):
        raise ValueError(f"{day}: selected activities exceed the {params['pace']} pace or light-arrival limit.")
    if any(not _eligible(activity, day, params) for activity in activities):
        raise ValueError(f"{day}: an activity is closed, out of season, unsuitable for the party or outside an approved selected region.")
    if overnight and any(not activity_context(activity["id"]).get("low_intensity") or activity["duration_min"] > 180 or _travel_minutes(hotel, activity) > 45 for activity in activities):
        raise ValueError(f"{day}: an overnight arrival requires a light first day; move this activity to a later day.")
    excursion = any(_point_region(activity) != hotel["destination_id"] or activity["duration_min"] >= 300 for activity in activities)
    if excursion and len(activities) != 1:
        raise ValueError(f"{day}: a full-day or out-of-town excursion needs its own day, including return travel.")
    if not excursion and sum(activity["duration_min"] for activity in activities) > config["active"]:
        raise ValueError(f"{day}: activity duration exceeds the {params['pace']} pace.")
    start_of_day = max(ready, 6 * 60 if excursion else config["start"])
    clock = start_of_day
    previous = hotel
    items = []
    for activity in activities:
        travel = _travel_minutes(previous, activity)
        start = max(clock + travel, _minutes(activity["opening_hours"]["open"]))
        note = "Approximate travel from the hotel or previous stop; allow extra time for access, traffic and breaks."
        if excursion:
            note = "Dedicated excursion; approximate outbound and return road travel is allowed separately from the experience."
        if excursion and hotel["destination_id"] == "baku" and _point_region(activity) == "gabala" and gabala_rail_day(day):
            station_minutes = max(15, math.ceil(distance_km(hotel["lat"], hotel["lon"], 40.3796, 49.8488) * 3 + 10))
            train_leave_hotel = 450 - station_minutes - 15
            if ready > train_leave_hotel:
                raise ValueError(f"{day}: the 07:30 Gabala train cannot be reached after arrival; choose a later day or a local hotel.")
            start_of_day = train_leave_hotel
            travel = station_minutes + 15 + 216 + 30
            start = max(705, start_of_day + travel)
            note = "Outbound weekend/confirmed-holiday rail 07:30–11:06, station approach and approximately 30-minute onward transfer; return by road because no return train time is confirmed."
        if not excursion and not activity["indoor"] and day.month in (6, 7, 8) and start < 960 and start + activity["duration_min"] > 720:
            start = max(start, 960)
            note += " Avoids peak midday heat using seasonal assumptions, not a live forecast."
        end = start + activity["duration_min"]
        home_travel = _travel_minutes(activity, hotel)
        latest_return = 1320 if excursion else config["end"]
        if end > _minutes(activity["opening_hours"]["close"]) or end + home_travel > latest_return:
            raise ValueError(f"{day}: {activity['name']} cannot fit its opening hours and return travel; choose a local hotel, a different day or fewer stops.")
        if excursion and end + home_travel - start_of_day > config["excursion"]:
            raise ValueError(f"{day}: {activity['name']} plus outbound/return travel is too long for this pace; a local hotel or separate overnight stay is required.")
        note += f" Return to {hotel['name']}: allow {home_travel} minutes, by {_clock(end + home_travel)} if this is the last stop."
        if excursion and end + home_travel - start_of_day > 12 * 60:
            note += " This is a long day of more than 12 hours; an overnight regional stay is less tiring."
        items.append({
            "activity_id": activity["id"], "title": activity["name"],
            "start_time": _clock(start), "end_time": _clock(end), "travel_minutes": travel,
            "price_azn": round(activity["price_azn"] * (params["adults"] + params["children"]), 2),
            "transport_note": note, "return_travel_minutes": home_travel, "return_time": _clock(end + home_travel),
            "is_synthetic": True, "grounding_refs": list(dict.fromkeys([*activity["grounding_refs"], "road-routes"])),
        })
        clock, previous = end + 15, activity
    return items


def _selected_activities(ids: Any, eligible: list[dict]) -> list[dict]:
    if not isinstance(ids, list) or any(not isinstance(item, str) for item in ids):
        raise ValueError("activity_ids must be a list of catalogue IDs.")
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate activity IDs are not allowed in a trip.")
    known = {activity["id"]: activity for activity in get_activities()}
    available = {activity["id"]: activity for activity in eligible}
    for activity_id in ids:
        if activity_id not in known:
            raise ValueError(f"Unknown activity ID: {activity_id}.")
        if activity_id not in available:
            raise ValueError(f"Activity {activity_id} is unavailable for the selected dates, party or regions.")
    return [available[activity_id] for activity_id in ids]


def _itinerary(
    params: dict, hotel: dict, flight: dict | None, ranked: list[dict],
    selected_ids: list[str] | None, override: list[dict] | None,
) -> tuple[list[dict], list[str]]:
    dates = stay_dates(params["arrival"], params["departure"])
    remaining = _selected_activities(selected_ids, ranked) if selected_ids is not None else list(ranked)
    by_date: dict[str, list[dict]] = {}
    if override is not None:
        if not isinstance(override, list):
            raise ValueError("itinerary_override must be a list of days.")
        allowed_dates, all_ids = {day.isoformat() for day in dates}, []
        for entry in override:
            if not isinstance(entry, dict) or "date" not in entry or "activity_ids" not in entry:
                raise ValueError("Each itinerary day needs date and activity_ids.")
            parsed = parse_date(entry["date"], "itinerary date").isoformat()
            if parsed not in allowed_dates or parsed in by_date:
                raise ValueError("Itinerary dates must be unique and fall within the stay, excluding checkout day.")
            by_date[parsed] = _selected_activities(entry["activity_ids"], ranked)
            all_ids.extend(entry["activity_ids"])
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("An activity cannot be selected on multiple itinerary days.")
        if selected_ids is not None and set(all_ids) != set(selected_ids):
            raise ValueError("itinerary_override and selected_activity_ids must name exactly the same activities.")
        remaining = []
    itinerary = []
    for day in dates:
        if override is not None:
            items = _schedule_day(day, by_date.get(day.isoformat(), []), params, hotel, flight)
        else:
            choices: list[dict] = []
            items = []
            for activity in list(remaining):
                try:
                    trial = _schedule_day(day, [*choices, activity], params, hotel, flight)
                except ValueError:
                    continue
                choices.append(activity)
                items = trial
                remaining.remove(activity)
        first_light = day == dates[0] and flight is not None and bool(flight["arrival_day_offset"])
        title = "Light arrival day — rest and an easy introduction" if first_light else f"Day {len(itinerary) + 1} — {hotel['destination_id'].title()} base"
        if not items:
            title += " · free time / rest (no activity charge)"
        elif len(items) == 1 and _point_region(next(activity for activity in ranked if activity["id"] == items[0]["activity_id"])) != hotel["destination_id"]:
            title += " · regional excursion with return travel"
        itinerary.append({
            "date": day.isoformat(), "title": title, "items": items,
            "total_azn": round(sum(item["price_azn"] for item in items), 2),
            "is_synthetic": True, "grounding_refs": ["synthetic-activities", "road-routes"],
        })
    if selected_ids is not None and remaining:
        raise ValueError(f"Cannot fit all selected activities with opening hours, pace and travel: {', '.join(item['id'] for item in remaining)}. Add days, change pace, or select a suitable regional hotel.")
    return itinerary, [item["id"] for item in remaining]


def build_transport(params: dict, hotel: dict) -> list[dict]:
    itinerary = params.get("_itinerary_days") if isinstance(params, dict) else None
    flight = params.get("_selected_flight") if isinstance(params, dict) else None
    params = normalize_search(params)
    hotel = _approved_hotel(params, hotel)
    party = params["adults"] + params["children"]
    vehicles = math.ceil(party / 4)
    nights = len(stay_dates(params["arrival"], params["departure"]))
    base = hotel["destination_id"]
    legs: list[dict] = []

    def add(
        leg_id: str, origin: str, target: str, mode: str, duration: int, fare: float, quantity: int,
        facts: list[str], note: str, *, approximate: bool = True, alternative: str | None = None,
        per_vehicle: bool = False,
    ) -> None:
        operator = "BakuBus" if leg_id.startswith("h1-") else "Baku Metro" if mode == "metro" else "Azerbaijan Railways (ADY)" if mode == "rail" else "Fictional Caspian Demo Transfers" if mode == "road" else "BakiKart"
        booking = "https://ticket.ady.az" if mode == "rail" else "Airport/metro machine; no purchase in this demo" if mode in ("metro", "transit-card") else "https://www.bakubus.az/quality" if leg_id.startswith("h1-") else "Illustrative road estimate only; obtain an actual quote separately"
        legs.append({
            "id": leg_id, "from": origin, "to": target, "mode": mode, "operator": operator,
            "duration_min": duration, "fare_azn": fare, "total_azn": round(fare * quantity, 2),
            "schedule_note": f"{note} Budget arithmetic: {quantity} × {fare:.2f} AZN ({'vehicle journeys' if per_vehicle else 'traveller journeys/cards'}). Baseline {BASELINE_DATE}; not independently reverified; confirm before travel.",
            "booking_channel": booking, "last_verified": BASELINE_DATE, "fact_refs": facts,
            "alternative": alternative, "approximate": approximate, "is_synthetic": True,
            "grounding_refs": facts, "quantity": quantity, "fare_basis": "per_vehicle" if per_vehicle else "per_traveller",
        })

    if hotel["id"] == "HTL-BAK-007":
        for suffix, origin, target in (("in", "GYD airport", hotel["name"]), ("out", hotel["name"], "GYD airport")):
            add(f"airport-road-{suffix}", origin, target, "road", 35, 35, vehicles, ["road-routes"], "Direct synthetic airport transfer; H1 via central Baku would be an unnecessary detour.", per_vehicle=True)
        add("coast-city-transfers", hotel["name"], "Central Baku and return", "road", 120 * nights, 25, 2 * vehicles * nights, ["road-routes"], "Illustrative city-commuting allowance for the remote coastal hotel; one outbound and return vehicle journey per itinerary day.", per_vehicle=True)
    else:
        for suffix, origin, target in (("in", "GYD airport Terminal 1", "28 May interchange"), ("out", "28 May interchange", "GYD airport Terminal 1")):
            add(f"h1-{suffix}", origin, target, "bus", 30, 1.30, party, ["h1"], "H1 baseline: 24/7, around every 15 minutes, via Koroglu. All travellers budgeted at the published baseline fare; no child discount assumed.", approximate=False, alternative="Direct taxi/ride-hailing: obtain a current quote; not included in this H1 budget.")
        if base == "baku":
            late_connection = flight is not None and _minutes(flight["arrive_local"]) + 120 >= 23 * 60
            if hotel["distance_to_metro_m"] is not None and hotel["distance_to_metro_m"] <= 1200 and hotel["id"] != "HTL-BAK-004" and not late_connection:
                add("hotel-metro-transfers", "28 May", hotel["nearest_metro"], "metro", 40, 0.60, 2 * party, ["metro", "geography"], "Airport-arrival and departure connections, followed by an approximate walk; metro operating hours must be reconfirmed.")
            else:
                add("hotel-road-transfers", "28 May", hotel["name"], "road", 50, 12, 2 * vehicles, ["road-routes", "geography"], "Synthetic short road connection in each direction; avoids a distant/steep walk or assuming late-night metro service.", per_vehicle=True)
    if base == "baku":
        add("bakikart", "Airport/metro sales machine", "One BakiKart per traveller", "transit-card", 0, 2, party, ["bakikart"], "Card purchase only; rides are budgeted separately.", approximate=False)
        city_days = nights if itinerary is None else sum(any(_point_region(activity_context(item["activity_id"])) == "baku" for item in day["items"]) for day in itinerary)
        if city_days:
            add("city-metro", "Baku city network", hotel["nearest_metro"] or "City attractions", "metro", 40 * city_days, 0.60, 2 * city_days * party, ["metro"], "Approximate city allowance of two metro rides per traveller per active city day. Additional taxis are not included; walk where feasible and top up as needed.")
    else:
        add("regional-local", hotel["name"], f"{base.title()} local transport allowance", "road", 30 * nights, 8, vehicles * nights, ["road-routes"], "Synthetic daily local vehicle allowance; no Baku Metro is claimed at this regional hotel.", per_vehicle=True)

    scheduled: dict[str, str] = {}
    if itinerary is not None:
        for day in itinerary:
            for item in day["items"]:
                region = activity_context(item["activity_id"])["travel_region"]
                if region != base:
                    scheduled.setdefault(region, day["date"])

    def regional_pair(region: str, outbound: str, returning: str, origin_region: str = "baku", accommodation_transfer: bool = False) -> None:
        for suffix, when in (("out", outbound), ("return", returning)):
            day = parse_date(when, "transport date")
            origin_label = "28 May / Baku" if origin_region == "baku" else f"{origin_region.title()} hotel base"
            target_label = f"{region.title()} station / town"
            if suffix == "return":
                origin_label, target_label = target_label, origin_label
            mode, fare, duration = "road", _ROAD_FARES.get(region, 35), _ROAD_MINUTES.get(region, 180)
            facts, note = ["road-routes"], f"{when}: synthetic road estimate, not a confirmed departure."
            alternative = "Road transfer estimate; reconfirm route, price and conditions locally."
            if origin_region != "baku":
                target_lat, target_lon = destination_coordinates(region)
                destination_point = {"id": f"PLACE-{region}", "destination_id": region, "lat": target_lat, "lon": target_lon}
                duration = _travel_minutes(hotel, destination_point)
                fare = _ROAD_FARES[origin_region] if region == "baku" else round(max(15, duration * 0.13), 2)
            elif region == "ganja":
                mode, fare, duration, facts = "rail", 12.80, 240, ["rail-ganja", "rail-tickets"]
                note = f"{when}: daily baseline service pattern; exact departure and seat availability not asserted."
            elif region == "gabala":
                facts = ["rail-gabala", "road-routes", "rail-tickets"]
                same_day_excursion_return = suffix == "return" and outbound == returning and not accommodation_transfer
                if gabala_rail_day(day) and not same_day_excursion_return:
                    mode, fare, duration = "rail", 12, 216
                    note = f"{when}: weekend/confirmed-holiday service. " + ("Baseline outbound 07:30–11:06; allow an onward road transfer." if suffix == "out" else "Return operating time is not provided in the baseline: reconfirm before choosing this connection.")
                else:
                    note = f"{when}: road fallback. " + ("No confirmed return train time; a road return keeps this full-day excursion feasible." if same_day_excursion_return and gabala_rail_day(day) else "Gabala rail is weekend/confirmed-holiday only; no service is assumed for this weekday.")
            elif region == "sheki":
                facts = ["rail-sheki", "rail-tickets", "road-routes"]
                if day >= _SHEKI_START and itinerary is None:
                    mode, fare, duration = "rail", 14.80, 600
                    note = f"{when}: ANNOUNCED night train from 2026-11-20; timetable UNCONFIRMED. Ten hours is a synthetic overnight allowance, not a published duration. Do not assume a same-day arrival."
                    alternative = "Road fallback: approximately five hours and 45 AZN per traveller; synthetic estimate, reconfirm locally."
                elif day >= _SHEKI_START:
                    note = f"{when}: road selected for a timed itinerary. Night rail is announced from 2026-11-20 but the timetable is unconfirmed, so it cannot establish a feasible same-day connection."
                    alternative = "Check ADY for the announced overnight train, from approximately 14.80 AZN; never assume its departure or arrival time."
                else:
                    note = f"{when}: road only in this dataset; the announced Sheki night train does not start before 2026-11-20."
            add(f"{origin_region}-{region}-{suffix}", origin_label, target_label, mode, duration, fare, party, facts, note, alternative=alternative)
            if mode == "rail":
                add(f"{origin_region}-{region}-{suffix}-station", f"{region.title()} station", f"{region.title()} hotel / activity", "road", 30, 10, vehicles, ["road-routes"], "Synthetic station-to-town connection; reverse direction on the return journey.", per_vehicle=True)

    if base != "baku":
        regional_pair(base, params["arrival"], params["departure"], accommodation_transfer=True)
    destinations = [region for region in params["regions"] if region not in ("baku", base)]
    destinations.extend(region for region in scheduled if region not in destinations and region not in ("baku", base))
    for region in destinations:
        visit_date = scheduled.get(region)
        regional_pair(region, visit_date or params["arrival"], visit_date or params["departure"], origin_region=base)
    if base != "baku" and "baku" in scheduled:
        regional_pair("baku", scheduled["baku"], scheduled["baku"], origin_region=base)
    return legs


def build_checklist(params: dict, nationality: str = "GB", today: date | None = None) -> list[dict]:
    params = normalize_search(params)
    if not isinstance(nationality, str) or not nationality.strip() or len(nationality) > 80:
        raise ValueError("nationality must be a country code or name.")
    nationality = nationality.strip().upper()
    uk = nationality in ("GB", "GBR", "UK", "UNITED KINGDOM", "BRITISH")
    nights = len(stay_dates(params["arrival"], params["departure"]))
    facts = {item["id"]: item for item in get_facts(today)}
    result = []

    def add(item_id: str, title: str, description: str, refs: list[str], warning: bool = False) -> None:
        fact = facts[refs[0]]
        result.append({
            "id": item_id, "title": title, "description": description,
            "severity": "warning" if warning else "info", "fact_refs": refs,
            "source_url": fact["source_url"], "last_verified": fact["last_verified"],
        })

    if nights > 30:
        add("evisa", "Stay exceeds the standard e-visa limit", f"This {nights}-night stay exceeds the baseline 30-day e-visa stay. Seek official advice on suitable permission before travel; this application cannot establish eligibility or issue a visa.", ["visa-stay", "visa-route"], True)
    else:
        eligibility = "The specification lists UK nationals as eligible to apply, but approval is not guaranteed." if uk else f"Eligibility for nationality {nationality} is not established by this catalogue; do not assume all nationalities qualify."
        add("evisa", "Check ASAN e-visa eligibility before travel", f"{eligibility} This {nights}-night stay is within the baseline 30-day limit. Standard fee: USD 20 + USD 9 service fee; standard processing within 3 working days or urgent within 3 hours (urgent fees differ). Confirm all rules at the official portal.", ["visa-route", "visa-stay", "visa-fee", "visa-processing"], not uk)
    add("passport", "Check passport validity against e-visa expiry", "Passport expiry must be at least 3 calendar months after the e-visa expiry date, NOT merely 3 months after checkout. Use the actual issued e-visa expiry; no assumed e-visa validity is used. Any document-date validation in this demo is transient, not an immigration approval.", ["passport"])
    add("registration", "Registration required for stays over 15 days" if nights > 15 else "Check the visitor registration threshold", f"The selected stay is {nights} nights. " + ("The specification's more-than-15-day registration threshold is exceeded: arrange registration with the State Migration Service and confirm applicable deadlines and exceptions." if nights > 15 else "The selected night count does not exceed the specification's 15-day threshold; confirm official counting rules and any nationality-specific requirements."), ["registration"], nights > 15)
    add("insurance", "Arrange suitable travel insurance", "Confirm medical cover and any exclusions. Add winter-sports or mountain-activity coverage where needed; the demo has not assessed your insurance.", ["insurance"])
    add("currency", "Plan AZN cash and card use", "AZN is the local currency. Carry cash for regional stops and a backup card. Display conversions use illustrative rates dated 2026-11-13, NOT live or historically verified market rates.", ["currency", "exchange-rates"])
    add("bakikart", "Allow for a BakiKart and top-up", "Baseline card cost: AZN 2, before rides. Metro rides are approximately AZN 0.60 and must be reconfirmed; H1 is budgeted separately at AZN 1.30 per traveller per journey.", ["bakikart", "metro", "h1"])
    add("mosques", "Respect mosques and memorials", "Dress modestly and follow local guidance at places of worship; treat Martyrs' Lane respectfully.", ["mosques"])
    add("land-borders", "Plan international arrival by air", "The early-November-2026 specification records foreign-tourist land and ferry entry closures. This is not live-verified. No Tbilisi or other cross-border railway connection is recommended.", ["land-border"], True)
    add("safety", "Read official FCDO travel advice", facts["safety"]["statement"], ["safety"], True)
    add("data-baseline", "Dated specification, not a live verification", f"All factual claims retain the user specification baseline {BASELINE_DATE}. We have not independently reverified these facts; opening windows, prices and bookings are fictional, and airline/rail patterns need reconfirmation.", ["synthetic-activities", "synthetic-pricing"])
    if any(fact["reverify_required"] for fact in facts.values()):
        add("reverify-facts", "Facts are more than 90 days old", "The baseline is older than 90 days relative to today's date. Reverify fares, entry rules, safety advice and timetables at the linked sources before relying on them.", ["safety", "h1", "visa-route"], True)
    return result


def build_trip(
    params: dict, trip_id: str | None = None, selected_hotel_id: str | None = None,
    selected_flight_id: str | None = None, selected_activity_ids: list[str] | None = None,
    itinerary_override: list[dict] | None = None,
) -> dict:
    params = normalize_search(params)
    dates = stay_dates(params["arrival"], params["departure"])
    hotels = get_hotels(params)
    target_rate = {"economy": 100, "mid-range": 180, "premium": 390}[params["budget"]]
    hotels.sort(key=lambda hotel: (hotel["destination_id"] != "baku", abs(hotel["base_rate_azn"] - target_rate), hotel["id"]))
    if selected_hotel_id is not None:
        hotel = next((item for item in hotels if item["id"] == selected_hotel_id), None)
        if hotel is None:
            raise ValueError("Selected hotel ID is unknown or outside the requested regions.")
        if not hotel["available"]:
            raise ValueError("The selected hotel has insufficient synthetic room inventory for this party and stay.")
    else:
        hotel = next((item for item in hotels if item["available"]), None)
        if hotel is None:
            raise ValueError("No synthetic hotel has enough rooms for the requested stay and party.")
    flights = _arrival_flights(params)
    if selected_flight_id is not None:
        flight = next((item for item in flights if item["id"] == selected_flight_id), None)
        if flight is None:
            raise ValueError("Selected flight ID is unknown or inconsistent with the selected origin.")
    else:
        flight = flights[0] if flights else None
    if trip_id is not None and (not isinstance(trip_id, str) or not trip_id.strip() or len(trip_id) > 128):
        raise ValueError("trip_id must be a non-empty string of at most 128 characters.")
    activities = recommend_activities(params, hotel)
    itinerary, unscheduled = _itinerary(params, hotel, flight, activities, selected_activity_ids, itinerary_override)
    transport = build_transport({**params, "_itinerary_days": itinerary, "_selected_flight": flight}, hotel)
    activity_total = round(sum(day["total_azn"] for day in itinerary), 2)
    transport_total = round(sum(leg["total_azn"] for leg in transport), 2)
    total = round(hotel["price_total_azn"] + activity_total + transport_total, 2)
    notices = [
        "DEMONSTRATION ONLY — fictional hotels, synthetic availability, prices and activity slots. No real booking, payment, ticket or reservation is made.",
        f"Facts are the user specification baseline dated {BASELINE_DATE}, not newly verified by us. Confirm all entry rules, safety advice, fares and schedules before travel.",
        "Currency conversion uses illustrative dated rates (2026-11-13), not live or historically verified market data.",
        "Ranking weights: season 35%, interest 30%, budget 15%, travel feasibility 10%, diversity 10%. Score components are visible on every recommendation.",
        "Museum and outdoor rankings use seasonal climate assumptions, not live wind, rain, snow or forecasts. Demo opening windows and capacities are synthetic, not official opening hours.",
        "Totals cover the selected hotel's complete stay, scheduled activities for all travellers and the displayed transport budget. Flights, visa fees, insurance, meals outside activities and unquoted extras are excluded.",
        "This plan has one selected hotel base for all nights. No extra regional accommodation is silently booked or charged; infeasible full-day visits need a local hotel or a separate overnight arrangement.",
        "The safety boundary is a static approved catalogue, not a live FCDO assessment. No disputed-area, Armenia-border or cross-border Tbilisi itinerary is included.",
        "For deterministic demo replay, created_at is the seeded dataset timestamp, not the time of a real reservation.",
    ]
    if not flights:
        notices.append(f"No grounded route is available in the offline catalogue for '{params['origin']}'. No live route was invented; check airlines separately. The first-day schedule assumes arrival before 09:00 and must be adjusted to the actual flight.")
    else:
        notices.append("Flight options are route-pattern examples, not confirmed weekday availability. Reconfirm on airline sites; outbound dates are adjusted so each displayed option arrives on the requested arrival date.")
        if flight["arrival_day_offset"]:
            notices.append(f"Overnight flight: depart {flight['departure_date']} to arrive {params['arrival']}. Early check-in is not guaranteed; a light first day and rest buffer are included.")
        else:
            notices.append(f"Selected flight arrives about {flight['arrive_local']} on the requested arrival date; immigration and airport transfer time limit the first day's activities.")
    if len(dates) > 15:
        notices.append("Registration notice: this stay exceeds 15 nights; confirm State Migration Service requirements and counting rules.")
    if len(dates) > 30:
        notices.append("E-visa limit warning: this stay exceeds the standard 30-day permission; obtain official advice before travel.")
    if any(novruz_event(day) for day in dates):
        notices.append("Novruz event overlay: tentative 20–26 March dates, not confirmed. Synthetic hotel uplift 1.35–1.60; this overlay does not establish holiday train availability.")
    if unscheduled:
        notices.append(f"{len(unscheduled)} recommended activities are not scheduled because of available days, opening windows, pace, arrival rest or travel feasibility. Only itinerary items are charged.")
        if "ACT-011" in unscheduled:
            notices.append("Sheki's seven-hour experience plus the Baku return drive is not feasible as a day trip. Select a Sheki hotel or arrange a separate overnight stay; no Sheki experience has been charged.")
    if any(region not in ("baku", hotel["destination_id"]) for region in params["regions"]):
        notices.append("Requested add-on transport is budgeted in both directions even when its activity cannot fit the itinerary; unscheduled regional legs are planning options, not confirmed connections.")
    if "shahdag" in params["regions"] and not any(day.month in (12, 1, 2, 3) for day in dates):
        notices.append("Shahdag skiing is excluded: none of the itinerary dates is in December–March. Actual snow and lift operation are never guaranteed.")
    if any(item["reverify_required"] for item in get_facts()):
        notices.append("The specification facts are more than 90 days old and require re-verification.")
    fingerprint = json.dumps({"params": params, "hotel": hotel["id"], "flight": flight["id"] if flight else None, "days": itinerary}, sort_keys=True, separators=(",", ":"))
    return {
        "id": trip_id or f"TRIP-{sha256(fingerprint.encode('utf-8')).hexdigest()[:16].upper()}",
        "search_params": params, "nights": len(dates), "hotels": hotels, "flights": flights,
        "activities": activities, "itinerary_days": itinerary, "transport_legs": transport,
        "checklist": build_checklist(params),
        "totals": {
            "hotel_azn": hotel["price_total_azn"], "activities_azn": activity_total,
            "transport_azn": transport_total, "total_azn": total,
            "total_gbp": round(total * EXCHANGE_RATES["rates"]["GBP"], 2),
        },
        "selected_hotel_id": hotel["id"], "selected_flight_id": flight["id"] if flight else None,
        "notices": notices, "is_synthetic": True, "exchange_rates": deepcopy(EXCHANGE_RATES),
        "planning_mode": "deterministic", "created_at": f"{BASELINE_DATE}T00:00:00+00:00",
    }
