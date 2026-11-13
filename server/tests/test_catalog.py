from datetime import date, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from caspian.catalog import EXCHANGE_RATES, availability, get_activities, get_destinations, get_facts, get_hotels


def test_complete_catalogue_is_synthetic_and_grounded():
    facts = {fact["id"]: fact for fact in get_facts(date(2026, 11, 13))}
    hotels, activities = get_hotels(), get_activities()
    assert len(hotels) == 12
    assert len(activities) == 15
    assert len(get_destinations()) == 6
    for record in [*hotels, *activities]:
        assert record["is_synthetic"] is True
        assert record["grounding_refs"]
        assert set(record["grounding_refs"]) <= facts.keys()
    for fact in facts.values():
        assert fact["source_url"].startswith("https://")
        assert fact["last_verified"] == "2026-11-13"
        assert "not independently verified" in fact["confidence"]
    assert "invented demo rates" in facts["exchange-rates"]["statement"]
    assert EXCHANGE_RATES["as_of"] == "2026-11-13"
    assert EXCHANGE_RATES["is_indicative"] is True


def test_facts_only_become_stale_after_ninety_days():
    baseline = date(2026, 11, 13)
    assert not any(fact["reverify_required"] for fact in get_facts(baseline + timedelta(days=90)))
    assert all(fact["reverify_required"] for fact in get_facts(baseline + timedelta(days=91)))


def test_white_city_nearest_metro_is_computed_not_copied_from_bad_example():
    hotel = next(hotel for hotel in get_hotels() if hotel["id"] == "HTL-BAK-006")
    assert hotel["nearest_metro"] == "Shah Ismail Khatai"
    assert 1000 < hotel["distance_to_metro_m"] < 1600
    assert next(hotel for hotel in get_hotels() if hotel["id"] == "HTL-BAK-005")["distance_to_metro_m"] < 150
    assert all(hotel["nearest_metro"] is None for hotel in get_hotels({"destination": "sheki"}))


def test_prices_and_inventory_are_repeatable_and_hash_seed_independent():
    args = ("HTL-BAK-001", "2027-03-19", "2027-03-25")
    assert availability(*args, seed=42) == availability(*args, seed=42)
    assert availability(*args, seed=42) != availability(*args, seed=43)
    code = "import json; from caspian.catalog import availability; print(json.dumps(availability('HTL-BAK-001','2027-03-19','2027-03-25',seed=42),sort_keys=True))"
    server = str(Path(__file__).resolve().parents[1])
    outputs = []
    for hash_seed in ("1", "928"):
        env = {**os.environ, "PYTHONHASHSEED": hash_seed, "PYTHONPATH": server}
        outputs.append(subprocess.check_output([sys.executable, "-c", code], env=env, text=True))
    assert json.loads(outputs[0]) == json.loads(outputs[1])


def test_room_weekend_low_season_and_tentative_event_multipliers():
    def quote(start, end, guests=2, room=None):
        return availability("HTL-BAK-003", start, end, guests, room, 42)

    standard = quote("2027-04-12", "2027-04-13")["total_azn"]
    family = quote("2027-04-12", "2027-04-13", 4, "family")["total_azn"]
    suite = quote("2027-04-12", "2027-04-13", 2, "suite")["total_azn"]
    weekend = quote("2027-04-10", "2027-04-11")["total_azn"]
    sunday = quote("2027-04-11", "2027-04-12")["total_azn"]
    low = quote("2027-01-11", "2027-01-12")["total_azn"]
    assert family == pytest.approx(standard * 1.4, abs=0.02)
    assert suite == pytest.approx(standard * 2.2, abs=0.02)
    assert weekend == pytest.approx(standard * 1.1, abs=0.02)
    assert sunday == weekend
    assert low == pytest.approx(standard * 0.8, abs=0.02)
    event = quote("2027-03-20", "2027-03-21")
    assert 1.35 <= event["total_azn"] / weekend <= 1.60
    assert "tentative" in event["nights"][0]["event"]
    assert event["nights"][0]["available"] < 12


def test_group_quote_keeps_room_inventory_and_party_prices_distinct():
    quote = availability("HTL-BAK-001", "2027-04-10", "2027-04-14", 9)
    assert quote["room_type_id"] == "family"
    assert quote["rooms_required"] == 3
    assert quote["available"] is True
    for night in quote["nights"]:
        assert night["price_azn"] == round(night["unit_price_azn"] * 3, 2)
    assert quote["total_azn"] == round(sum(night["price_azn"] for night in quote["nights"]), 2)


def test_hotel_filters_use_computed_geography_and_dated_party_prices():
    hotels = get_hotels({
        "destination": "baku", "stars": 4, "price_max": 260, "guest_score": 8.5,
        "max_distance_to_metro_m": 900, "amenities": ["wifi"], "family_friendly": True,
        "checkin": "2027-04-10", "checkout": "2027-04-14",
    })
    assert hotels
    assert all(hotel["stars"] == 4 and hotel["distance_to_metro_m"] <= 900 for hotel in hotels)
    for hotel in hotels:
        assert hotel["price_total_azn"] == availability(hotel["id"], "2027-04-10", "2027-04-14")["total_azn"]
    assert get_hotels({"price_max": 60, "currency": "GBP"}) == get_hotels({"price_max_gbp": 60})
    assert {hotel["destination_id"] for hotel in get_hotels({"regions": ["gabala"]})} == {"baku", "gabala"}


@pytest.mark.parametrize("hotel,checkin,checkout,guests,room", [
    ("missing", "2027-04-10", "2027-04-14", 2, None),
    ("HTL-BAK-001", "2027-02-29", "2027-03-04", 2, None),
    ("HTL-BAK-001", "2027-4-10", "2027-04-14", 2, None),
    ("HTL-BAK-001", "2027-04-10", "2027-04-10", 2, None),
    ("HTL-BAK-001", "2027-04-10", "2027-07-10", 2, None),
    ("HTL-BAK-001", "2027-04-10", "2027-04-14", 0, None),
    ("HTL-BAK-001", "2027-04-10", "2027-04-14", 2, "invented"),
    ("HTL-BAK-001", "2027-04-10", "2027-04-14", 4, "standard"),
])
def test_invalid_availability_is_rejected(hotel, checkin, checkout, guests, room):
    with pytest.raises(ValueError):
        availability(hotel, checkin, checkout, guests, room)


@pytest.mark.parametrize("params", [
    {"destination": "tbilisi"}, {"regions": ["karabakh"]}, {"price_min": 300, "price_max": 200},
    {"checkin": "2027-04-10"}, {"price_max": float("nan")}, {"family_friendly": "maybe"},
    {"regions": [{}]}, {"destination": []}, {"room_type_id": "missing"},
])
def test_invalid_hotel_filters_are_rejected(params):
    with pytest.raises(ValueError):
        get_hotels(params)
