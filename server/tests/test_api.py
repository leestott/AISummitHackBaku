from __future__ import annotations

import logging
import shutil
import sys
import types
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import caspian.api as api_module
from caspian.api import MAX_REQUEST_BYTES, create_app


def search_body(**changes):
    arrival = date(date.today().year + 1, 4, 12)
    return {
        "origin": "London", "arrival": arrival.isoformat(),
        "departure": (arrival + timedelta(days=4)).isoformat(),
        "adults": 2, "children": 0, "budget": "mid-range",
        "interests": ["history", "food"], "regions": ["baku"], "pace": "balanced", "seed": 42,
        **changes,
    }


@pytest.fixture
def api(monkeypatch):
    directory = Path(".data").joinpath(f"api-test-{uuid.uuid4().hex}")
    directory.mkdir(parents=True)
    monkeypatch.setitem(
        sys.modules, "caspian.foundry",
        types.SimpleNamespace(get_agent_status=lambda: {"configured": False, "names": []}),
    )
    application = create_app(str(directory / "test.sqlite3"))
    application.state.frontend_dist = directory / "dist"
    try:
        with TestClient(application) as client:
            yield application, client, directory
    finally:
        application.state.store.close()
        shutil.rmtree(directory)


def new_trip(client, **changes):
    response = client.post("/api/search", json=search_body(**changes))
    assert response.status_code == 200, response.text
    return response.json()


def test_structured_search_and_every_planning_route(api):
    application, client, _ = api
    meta = client.get("/api/meta")
    assert meta.status_code == 200
    assert meta.json()["hosted_agents"]["configured"] is False
    cookie = meta.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=Strict" in cookie
    assert "Secure" not in cookie
    trip = new_trip(client)
    assert trip["planning_mode"] == "deterministic"
    assert trip["nights"] == 4
    assert len(trip["hotels"]) >= 5
    assert client.get(f"/api/trip/{trip['id']}").json() == trip
    assert client.get("/api/facts").json()
    for path in ("activities/recommendations", "transport/plan", "checklist"):
        response = client.get(f"/api/{path}", params={"trip_id": trip["id"]})
        assert response.status_code == 200, response.text
        assert response.json()
        if path == "transport/plan":
            assert response.json() == trip["transport_legs"]
    flights = client.get("/api/flights", params={
        "origin": "London", "depart": trip["search_params"]["arrival"],
        "return": trip["search_params"]["departure"],
    })
    assert flights.status_code == 200 and flights.json()
    hotel_id = trip["selected_hotel_id"]
    assert client.get(f"/api/hotels/{hotel_id}").json()["id"] == hotel_id
    hotel_list = client.get("/api/hotels", params={
        "destination": "baku", "checkin": trip["search_params"]["arrival"],
        "checkout": trip["search_params"]["departure"], "stars": 4, "currency": "GBP",
        "price_max": 1000, "guest_score": 1,
    })
    assert hotel_list.status_code == 200, hotel_list.text
    assert hotel_list.json() and all(hotel["stars"] == 4 for hotel in hotel_list.json())
    updated = client.patch(f"/api/trip/{trip['id']}", json={"hotel_id": hotel_id, "activity_ids": []})
    assert updated.status_code == 200, updated.text
    days = [{"date": day["date"], "activity_ids": []} for day in updated.json()["itinerary_days"]]
    itinerary = client.patch(f"/api/trip/{trip['id']}/itinerary", json={"days": days})
    assert itinerary.status_code == 200, itinerary.text
    assert itinerary.json()["created_at"] == trip["created_at"]
    assert all(not day["items"] for day in itinerary.json()["itinerary_days"])
    assert application.state.store.get_trip(client.cookies["session_id"], trip["id"]) == itinerary.json()


@pytest.mark.parametrize("changes", [
    {"adults": True}, {"adults": "2"}, {"adults": 13}, {"children": -1},
    {"arrival": "2027-02-30"}, {"seed": -1}, {"regions": ["tbilisi"]},
    {"interests": ["unknown"]}, {"unit_price_azn": 0},
])
def test_malformed_or_unbounded_search_is_rejected(api, changes):
    _, client, _ = api
    response = client.post("/api/search", json=search_body(**changes))
    assert response.status_code == 422
    assert "error" in response.json()


def test_cross_session_trips_are_not_visible_or_mutable(api):
    application, owner, _ = api
    trip = new_trip(owner)
    with TestClient(application) as stranger:
        assert stranger.get(f"/api/trip/{trip['id']}").status_code == 404
        assert stranger.patch(f"/api/trip/{trip['id']}", json={"pace": "relaxed"}).status_code == 404
        assert stranger.get("/api/checklist", params={"trip_id": trip["id"]}).status_code == 404
        assert stranger.post("/api/assistant", json={"message": "Explain this trip", "trip_id": trip["id"]}).status_code == 404
        assert stranger.cookies["session_id"] != owner.cookies["session_id"]


def test_identical_searches_get_independent_session_owned_trip_ids(api):
    application, owner, _ = api
    original = new_trip(owner)
    repeated = new_trip(owner)
    changed = owner.patch(f"/api/trip/{original['id']}", json={"activity_ids": []})
    assert changed.status_code == 200
    with TestClient(application) as stranger:
        other = new_trip(stranger)
        assert len({original["id"], repeated["id"], other["id"]}) == 3
        assert original["totals"] == repeated["totals"] == other["totals"]
        assert any(day["items"] for day in other["itinerary_days"])
        assert stranger.get(f"/api/trip/{original['id']}").status_code == 404
        assert owner.get(f"/api/trip/{other['id']}").status_code == 404


@pytest.mark.parametrize("change", [
    {"hotel_id": "HTL-BAK-001"},
    {"flight_id": "FLT-AZAL-LGW"},
    {"pace": "relaxed"},
])
def test_other_trip_changes_do_not_restore_removed_activities(api, change):
    _, client, _ = api
    trip = new_trip(client)
    path = f"/api/trip/{trip['id']}"
    assert client.patch(path, json={"activity_ids": []}).status_code == 200

    updated = client.patch(path, json=change)

    assert updated.status_code == 200, updated.text
    assert all(not day["items"] for day in updated.json()["itinerary_days"])
    assert updated.json()["totals"]["activities_azn"] == 0
    assert client.get(path).json() == updated.json()


def test_ai_is_explicitly_unavailable_not_faked(api):
    _, client, _ = api
    for path, body in [
        ("/api/search/parse", {"text": "A family trip in April"}),
        ("/api/assistant", {"message": "What is my visa allowance?"}),
    ]:
        response = client.post(path, json=body)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "ai_not_configured"


def test_missing_optional_agent_dependencies_do_not_break_the_api(api, monkeypatch):
    _, client, _ = api
    original = api_module.importlib.import_module

    def missing_dependency(name, *args, **kwargs):
        if name == "caspian.foundry":
            raise ModuleNotFoundError("Optional dependency is not installed", name="dotenv")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(api_module.importlib, "import_module", missing_dependency)
    assert client.get("/api/meta").json()["hosted_agents"]["configured"] is False
    assert new_trip(client)["planning_mode"] == "deterministic"
    response = client.post("/api/assistant", json={"message": "What is the visa allowance?"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ai_dependencies_missing"


def test_grounded_gateway_contract_is_validated(api, monkeypatch):
    _, client, _ = api
    seen = []

    async def parse(text):
        seen.append(text)
        return {
            "search_params": search_body(), "source": "foundry",
            "needs_confirmation": True, "explanation": "Check these proposed dates before searching.",
        }

    async def assistant(message, trip):
        seen.append(trip["id"])
        return {"message": "Use the official ASAN portal.", "source": "foundry", "agents": ["checklist"], "fact_refs": ["visa-route"]}

    monkeypatch.setitem(sys.modules, "caspian.foundry", types.SimpleNamespace(
        get_agent_status=lambda: {"configured": True, "names": ["checklist"]},
        parse_search=parse, ask_assistant=assistant,
    ))
    trip = new_trip(client)
    assert not seen
    parsed = client.post("/api/search/parse", json={"text": "Four nights in Baku"})
    assert parsed.status_code == 200, parsed.text
    assert parsed.json()["needs_confirmation"] is True
    reply = client.post("/api/assistant", json={"message": "Explain entry rules", "trip_id": trip["id"]})
    assert reply.status_code == 200 and reply.json()["source"] == "foundry"
    assert seen == ["Four nights in Baku", trip["id"]]


def test_request_limits_security_headers_and_private_logs(api, caplog):
    application, client, _ = api
    caplog.set_level(logging.INFO, logger="caspian.api")
    application.state.rate_limiter.limits["session"]["search"] = 2
    new_trip(client)
    new_trip(client)
    limited = client.post("/api/search", json=search_body())
    assert limited.status_code == 429 and limited.headers["retry-after"] == "60"
    response = client.post("/api/search", content=b"x" * (MAX_REQUEST_BYTES + 1), headers={"content-type": "application/json"})
    assert response.status_code == 413
    response = client.post("/api/assistant", json={"message": "Private sample phrase"}, headers={"origin": "https://other.example"})
    assert response.status_code == 403
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-request-id"]
    assert "Private sample phrase" not in caplog.text
    assert client.cookies["session_id"] not in caplog.text
    assert '"duration_ms"' in caplog.text


def test_secure_cookie_and_daily_purge(api):
    application, client, _ = api
    trip = new_trip(client)
    previous_session = client.cookies["session_id"]
    now = application.state.store.now()
    application.state.store.clock = lambda: now + timedelta(days=1)
    assert client.get(f"/api/trip/{trip['id']}").status_code == 404
    assert client.cookies["session_id"] != previous_session
    with application.state.store.read() as connection:
        assert connection.execute("SELECT count(*) FROM trips").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM sessions WHERE id=?", (previous_session,)).fetchone()[0] == 0
    with TestClient(application, base_url="https://testserver") as secure:
        assert "Secure" in secure.get("/api/meta").headers["set-cookie"]


def test_static_spa_fallback_never_exposes_api_or_outside_files(api):
    application, client, directory = api
    dist = application.state.frontend_dist
    dist.mkdir()
    dist.joinpath("index.html").write_text("<html>Caspian test SPA</html>", encoding="utf-8")
    directory.joinpath("private.txt").write_text("not a public asset", encoding="utf-8")
    assert "Caspian test SPA" in client.get("/trip/example").text
    for path in ("/api/unknown", "/assets/missing.js", "/%2e%2e/private.txt", "/..%5cprivate.txt"):
        response = client.get(path)
        assert response.status_code == 404, path
        assert "Caspian test SPA" not in response.text
        assert "not a public asset" not in response.text


def test_internal_errors_do_not_expose_tracebacks(api, monkeypatch):
    application, client, _ = api

    def fail(*args, **kwargs):
        raise RuntimeError("Private internal implementation detail")

    monkeypatch.setattr(application.state.store, "save_trip", fail)
    response = client.post("/api/search", json=search_body())
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "Private internal" not in response.text and "Traceback" not in response.text
