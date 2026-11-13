from datetime import date, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from caspian.catalog import SCORE_WEIGHTS, get_activities, get_facts, get_hotels
from caspian.planning import build_checklist, build_transport, build_trip, get_flights, normalize_search


def search(**changes):
    return {
        "origin": "London", "arrival": "2027-04-10", "departure": "2027-04-14",
        "adults": 2, "children": 0, "budget": "mid-range", "interests": ["history", "food"],
        "regions": [], "pace": "balanced", "seed": 42, **changes,
    }


def minutes(clock):
    hours, mins = map(int, clock.split(":"))
    return hours * 60 + mins


def test_london_april_four_nights_returns_complete_grounded_plan():
    trip = build_trip(search())
    assert trip["nights"] == 4
    assert len(trip["hotels"]) >= 5
    assert len(trip["itinerary_days"]) == 4
    assert [flight["origin"] for flight in trip["flights"][:2]] == ["LHR", "LGW"]
    assert [flight["stops"] for flight in trip["flights"][:2]] == [0, 0]
    assert trip["flights"][2]["via"] == "Istanbul (IST)"
    assert any(leg["id"] == "h1-in" and leg["fare_azn"] == 1.3 for leg in trip["transport_legs"])
    assert trip["search_params"]["arrival"] == "2027-04-10"
    assert trip["search_params"]["departure"] == "2027-04-14"
    assert all(flight["arrival_date"] == "2027-04-10" for flight in trip["flights"])
    assert trip["planning_mode"] == "deterministic"
    assert trip["is_synthetic"] is True
    assert trip["flights"][0]["departure_date"] == "2027-04-09"
    assert trip["flights"][0]["early_checkin_note"]
    assert len(trip["itinerary_days"][0]["items"]) <= 1
    assert set(item["activity_id"] for item in trip["itinerary_days"][0]["items"]) <= {"ACT-004", "ACT-005", "ACT-007", "ACT-010"}
    assert all("reconfirm" in flight["schedule_note"].lower() for flight in trip["flights"])
    fact_ids = {fact["id"] for fact in get_facts()}
    for record in [*trip["flights"], *trip["transport_legs"]]:
        assert set(record["grounding_refs"]) <= fact_ids
    assert "Tbilisi" not in " ".join(leg["to"] for leg in trip["transport_legs"])


def test_deterministic_trip_is_repeatable_across_interpreter_hash_seeds():
    assert build_trip(search()) == build_trip(search())
    server = str(Path(__file__).resolve().parents[1])
    code = f"import json; from caspian.planning import build_trip; print(json.dumps(build_trip({search()!r}),sort_keys=True))"
    outputs = [
        subprocess.check_output([sys.executable, "-c", code], env={**os.environ, "PYTHONPATH": server, "PYTHONHASHSEED": str(seed)}, text=True)
        for seed in (2, 732)
    ]
    assert json.loads(outputs[0]) == json.loads(outputs[1])


def test_ski_is_in_december_and_excluded_in_july():
    winter = build_trip(search(arrival="2026-12-10", departure="2026-12-14", regions=["shahdag"], interests=["adventure", "nature"]))
    summer = build_trip(search(arrival="2027-07-10", departure="2027-07-14", regions=["shahdag"], interests=["adventure", "nature"]))
    assert "ACT-014" in {activity["id"] for activity in winter["activities"]}
    assert "ACT-014" in {item["activity_id"] for day in winter["itinerary_days"] for item in day["items"]}
    assert "ACT-014" not in {activity["id"] for activity in summer["activities"]}
    assert any("skiing is excluded" in notice for notice in summer["notices"])
    with pytest.raises(ValueError, match="unavailable"):
        build_trip(search(arrival="2027-07-10", departure="2027-07-14", regions=["shahdag"]), selected_activity_ids=["ACT-014"])


def test_ski_eligibility_is_checked_on_each_itinerary_day():
    params = search(origin="unseeded", arrival="2027-03-31", departure="2027-04-03", regions=["shahdag"])
    allowed = build_trip(params, selected_hotel_id="HTL-SHD-001", itinerary_override=[{"date": "2027-03-31", "activity_ids": ["ACT-014"]}])
    assert allowed["itinerary_days"][0]["items"][0]["activity_id"] == "ACT-014"
    with pytest.raises(ValueError, match="out of season"):
        build_trip(params, selected_hotel_id="HTL-SHD-001", itinerary_override=[{"date": "2027-04-01", "activity_ids": ["ACT-014"]}])


@pytest.mark.parametrize("nights,registration,visa_warning", [(15, False, False), (16, True, False), (30, True, False), (31, True, True)])
def test_registration_and_evisa_boundaries(nights, registration, visa_warning):
    start = date(2027, 4, 1)
    params = search(arrival=start.isoformat(), departure=(start + timedelta(days=nights)).isoformat())
    checklist = {item["id"]: item for item in build_checklist(params, today=date(2026, 11, 13))}
    assert (checklist["registration"]["severity"] == "warning") is registration
    assert (checklist["evisa"]["severity"] == "warning") is visa_warning
    assert len(build_trip(params)["itinerary_days"]) == nights
    assert "after the e-visa expiry date" in checklist["passport"]["description"]


def test_unknown_nationality_and_stale_facts_are_not_assumed_verified():
    checklist = {item["id"]: item for item in build_checklist(search(), nationality="ZZ", today=date(2027, 2, 13))}
    assert checklist["evisa"]["severity"] == "warning"
    assert "not established" in checklist["evisa"]["description"]
    assert checklist["reverify-facts"]["severity"] == "warning"
    assert "not live FCDO verification" in checklist["safety"]["description"]


def test_scores_show_exact_weights_and_seasonal_not_live_weather():
    params = search(arrival="2026-12-10", departure="2026-12-14")
    trip = build_trip(params)
    assert list(SCORE_WEIGHTS.values()) == [0.35, 0.30, 0.15, 0.10, 0.10]
    scores = {activity["id"]: activity["score"] for activity in trip["activities"]}
    for score in scores.values():
        assert score["total"] == round(sum(score[key] * weight for key, weight in SCORE_WEIGHTS.items()), 2)
    assert scores["ACT-005"]["season_fit"] > scores["ACT-008"]["season_fit"]
    assert any("not live wind" in notice for notice in trip["notices"])


def test_transport_and_trip_totals_are_summed_from_actual_items():
    trip = build_trip(search(adults=2, children=2))
    for leg in trip["transport_legs"]:
        assert leg["total_azn"] == round(leg["fare_azn"] * leg["quantity"], 2)
    legs = {leg["id"]: leg for leg in trip["transport_legs"]}
    assert legs["h1-in"]["total_azn"] == 5.2
    assert legs["h1-out"]["total_azn"] == 5.2
    assert legs["bakikart"]["total_azn"] == 8
    totals = trip["totals"]
    assert totals["transport_azn"] == round(sum(leg["total_azn"] for leg in trip["transport_legs"]), 2)
    assert totals["activities_azn"] == round(sum(item["price_azn"] for day in trip["itinerary_days"] for item in day["items"]), 2)
    assert totals["total_azn"] == round(totals["hotel_azn"] + totals["activities_azn"] + totals["transport_azn"], 2)
    assert totals["total_gbp"] == round(totals["total_azn"] * trip["exchange_rates"]["rates"]["GBP"], 2)


def test_gabala_weekday_fallback_weekend_outbound_and_road_return():
    hotel = get_hotels({"destination": "baku"})[0]
    weekday = build_transport(search(arrival="2027-04-05", departure="2027-04-09", regions=["gabala"]), hotel)
    assert all(leg["mode"] == "road" for leg in weekday if leg["id"] in ("baku-gabala-out", "baku-gabala-return"))
    weekend = build_transport(search(arrival="2027-04-10", departure="2027-04-11", regions=["gabala"]), hotel)
    assert next(leg for leg in weekend if leg["id"] == "baku-gabala-out")["mode"] == "rail"
    params = search(arrival="2027-05-14", departure="2027-05-18", regions=["gabala"], interests=["nature"])
    trip = build_trip(params, itinerary_override=[{"date": "2027-05-15", "activity_ids": ["ACT-012"]}])
    excursion = next(day for day in trip["itinerary_days"] if day["date"] == "2027-05-15")["items"][0]
    assert excursion["start_time"] >= "11:45"
    assert excursion["return_time"] <= "22:00"
    assert next(leg for leg in trip["transport_legs"] if leg["id"] == "baku-gabala-return")["mode"] == "road"


def test_sheki_announcement_threshold_and_road_fallback_are_explicit():
    hotel = get_hotels({"destination": "baku"})[0]
    before = build_transport(search(arrival="2026-11-18", departure="2026-11-19", regions=["sheki"]), hotel)
    after = build_transport(search(arrival="2026-11-20", departure="2026-11-22", regions=["sheki"]), hotel)
    assert next(leg for leg in before if leg["id"] == "baku-sheki-out")["mode"] == "road"
    announced = next(leg for leg in after if leg["id"] == "baku-sheki-out")
    assert announced["mode"] == "rail"
    assert "UNCONFIRMED" in announced["schedule_note"]
    assert "Road fallback" in announced["alternative"]
    assert next(leg for leg in build_transport(search(regions=["ganja"]), hotel) if leg["id"] == "baku-ganja-out")["mode"] == "rail"


@pytest.mark.parametrize("pace", ["relaxed", "balanced", "packed"])
def test_itinerary_respects_duration_opening_hours_travel_and_return(pace):
    trip = build_trip(search(pace=pace))
    catalogue = {activity["id"]: activity for activity in get_activities()}
    for day in trip["itinerary_days"]:
        previous_end = None
        for item in day["items"]:
            activity = catalogue[item["activity_id"]]
            start, end = minutes(item["start_time"]), minutes(item["end_time"])
            assert end - start == activity["duration_min"]
            assert start >= minutes(activity["opening_hours"]["open"])
            assert end <= minutes(activity["opening_hours"]["close"])
            if previous_end is not None:
                assert start >= previous_end + item["travel_minutes"]
            assert minutes(item["return_time"]) == end + item["return_travel_minutes"]
            assert minutes(item["return_time"]) <= 22 * 60
            previous_end = end


def test_full_day_sheki_requires_local_base_and_cannot_be_silently_dropped():
    params = search(regions=["sheki"])
    with pytest.raises(ValueError, match="Cannot fit"):
        build_trip(params, selected_activity_ids=["ACT-011"])
    trip = build_trip(params, selected_hotel_id="HTL-SHK-001", selected_activity_ids=["ACT-011"])
    assert any(item["activity_id"] == "ACT-011" for day in trip["itinerary_days"] for item in day["items"])
    assert all(leg["mode"] == "road" for leg in trip["transport_legs"] if leg["id"] in ("baku-sheki-out", "baku-sheki-return"))


def test_unknown_origin_never_gets_an_invented_flight():
    assert get_flights("Atlantis", "2027-04-10", "2027-04-14") == []
    trip = build_trip(search(origin="Atlantis"))
    assert trip["flights"] == []
    assert trip["selected_flight_id"] is None
    assert any("No live route was invented" in notice for notice in trip["notices"])
    with pytest.raises(ValueError, match="flight ID"):
        build_trip(search(origin="Atlantis"), selected_flight_id="FLT-AZAL-LHR")


def test_late_arrival_does_not_assume_a_metro_connection_or_activities():
    trip = build_trip(search(), selected_flight_id="FLT-LH-FRA")
    assert trip["itinerary_days"][0]["items"] == []
    assert any(leg["id"] == "hotel-road-transfers" for leg in trip["transport_legs"])
    assert not any(leg["id"] == "hotel-metro-transfers" for leg in trip["transport_legs"])
    flight = next(flight for flight in trip["flights"] if flight["id"] == trip["selected_flight_id"])
    regenerated = build_transport(
        {**trip["search_params"], "_itinerary_days": trip["itinerary_days"], "_selected_flight": flight},
        next(hotel for hotel in trip["hotels"] if hotel["id"] == trip["selected_hotel_id"]),
    )
    assert regenerated == trip["transport_legs"]


def test_empty_explicit_selection_means_no_activity_cost_and_overrides_are_preserved():
    trip = build_trip(search(), selected_activity_ids=[])
    assert all(not day["items"] for day in trip["itinerary_days"])
    assert trip["totals"]["activities_azn"] == 0
    edited = build_trip(search(), trip_id="trip-retained", itinerary_override=[{"date": "2027-04-11", "activity_ids": ["ACT-002", "ACT-003"]}])
    assert edited["id"] == "trip-retained"
    assert [item["activity_id"] for item in edited["itinerary_days"][1]["items"]] == ["ACT-002", "ACT-003"]


@pytest.mark.parametrize("change", [
    {"arrival": "2027-02-29"}, {"departure": "2027-04-10"}, {"departure": "2027-07-15"},
    {"adults": 0}, {"adults": True}, {"children": -1}, {"adults": 12, "children": 1},
    {"regions": ["tbilisi"]}, {"regions": ["karabakh"]}, {"interests": ["invented"]},
    {"seed": -1}, {"pace": "impossible"}, {"pace": []},
])
def test_invalid_search_rejected_without_changing_dates(change):
    with pytest.raises(ValueError):
        normalize_search(search(**change))


@pytest.mark.parametrize("selection", [
    {"selected_hotel_id": "missing"}, {"selected_hotel_id": "HTL-SHK-001"},
    {"selected_flight_id": "missing"}, {"selected_activity_ids": ["missing"]},
    {"selected_activity_ids": ["ACT-002", "ACT-002"]},
    {"itinerary_override": [{"date": "2027-04-14", "activity_ids": ["ACT-002"]}]},
    {"itinerary_override": [{"date": "2027-04-11", "activity_ids": ["ACT-006", "ACT-002"]}]},
    {"itinerary_override": [{"date": "2027-04-11", "activity_ids": ["ACT-002"]}], "selected_activity_ids": ["ACT-003"]},
])
def test_invalid_or_infeasible_selections_rejected(selection):
    with pytest.raises(ValueError):
        build_trip(search(), **selection)
