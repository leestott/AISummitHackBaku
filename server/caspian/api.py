"""Same-origin REST API: run ``uvicorn caspian.api:app`` from the server folder."""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
import threading
import time
import uuid
from collections import OrderedDict, deque
from concurrent.futures import Future
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import (
    AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, ValidationError,
    model_validator,
)
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException

from . import catalog, planning
from .booking import BookingService, TEST_CARDS
from .exports import render_ics, render_pdf
from .storage import ServiceError, Store, encode

LOGGER = logging.getLogger("caspian.api")
if not LOGGER.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    LOGGER.addHandler(handler)
LOGGER.setLevel(logging.INFO)
MAX_REQUEST_BYTES = 64 * 1024
MAX_AI_SECONDS = 120
NOT_FOUND = {"error": {"code": "not_found", "message": "Resource not found."}}


def _iso_date(value: str) -> str:
    date.fromisoformat(value)
    return value


Identifier = Annotated[str, StringConstraints(
    min_length=1, max_length=96, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$"
)]
DateText = Annotated[str, StringConstraints(pattern=r"^\d{4}-\d{2}-\d{2}$"), AfterValidator(_iso_date)]
ShortText = Annotated[str, StringConstraints(min_length=1, max_length=80, pattern=r"^[^\x00-\x1f\x7f]+$")]
Nationality = Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}$")]
Pace = Literal["relaxed", "balanced", "packed"]


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)


class SearchRequest(StrictRequest):
    origin: ShortText
    arrival: DateText
    departure: DateText
    adults: int = Field(default=2, ge=1, le=12)
    children: int = Field(default=0, ge=0, le=11)
    budget: Literal["economy", "mid-range", "premium"] = "mid-range"
    interests: list[ShortText] = Field(default_factory=list, max_length=8)
    regions: list[ShortText] = Field(default_factory=list, max_length=6)
    pace: Pace = "balanced"
    seed: int = Field(default=42, ge=0, le=2_147_483_647)

    @model_validator(mode="after")
    def bounded_search(self) -> SearchRequest:
        stay = (date.fromisoformat(self.departure) - date.fromisoformat(self.arrival)).days
        if not 1 <= stay <= 60:
            raise ValueError("A trip must contain between one and sixty nights.")
        if self.adults + self.children > 12:
            raise ValueError("A demo party must contain at most twelve travellers.")
        if len(set(self.interests)) != len(self.interests) or len(set(self.regions)) != len(self.regions):
            raise ValueError("Interests and regions must not be duplicated.")
        return self


class TripChanges(StrictRequest):
    hotel_id: Identifier | None = None
    flight_id: Identifier | None = None
    activity_ids: list[Identifier] | None = Field(default=None, max_length=15)
    pace: Pace | None = None

    @model_validator(mode="after")
    def nonempty_change(self) -> TripChanges:
        if not self.model_fields_set or any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Supply at least one non-null trip change.")
        if self.activity_ids is not None and len(set(self.activity_ids)) != len(self.activity_ids):
            raise ValueError("Activities must not be duplicated.")
        return self


class ItineraryDayRequest(StrictRequest):
    date: DateText
    activity_ids: list[Identifier] = Field(max_length=15)


class ItineraryChanges(StrictRequest):
    days: list[ItineraryDayRequest] = Field(min_length=1, max_length=60)

    @model_validator(mode="after")
    def unique_dates(self) -> ItineraryChanges:
        dates = [day.date for day in self.days]
        identifiers = [identifier for day in self.days for identifier in day.activity_ids]
        if len(set(dates)) != len(dates) or len(set(identifiers)) != len(identifiers):
            raise ValueError("Dates and activities must not be duplicated.")
        return self


class BookingRequest(StrictRequest):
    trip_plan_id: Identifier
    hotel_id: Identifier
    room_type_id: Identifier
    activity_ids: list[Identifier] = Field(default_factory=list, max_length=15)
    flight_id: Identifier | None = None


class TravellerDetails(StrictRequest):
    name: Annotated[str, StringConstraints(
        min_length=2, max_length=100, pattern=r"^[^\x00-\x1f\x7f]+$"
    )] = Field(repr=False)
    email: Annotated[str, StringConstraints(
        min_length=3, max_length=254, pattern=r"^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$"
    )] = Field(repr=False)
    nationality: Nationality
    passport_expiry: DateText = Field(repr=False)
    evisa_expiry: DateText | None = Field(default=None, repr=False)


class PaymentRequest(StrictRequest):
    card_number: str = Field(min_length=1, max_length=32, repr=False)


class ParseRequest(StrictRequest):
    text: str = Field(min_length=3, max_length=2000)


class AssistantRequest(StrictRequest):
    message: str = Field(min_length=1, max_length=4000)
    trip_id: Identifier | None = None


class AssistantResponse(StrictRequest):
    message: str = Field(min_length=1, max_length=16000)
    source: Literal["foundry"]
    agents: list[ShortText] = Field(max_length=16)
    fact_refs: list[Identifier] = Field(max_length=100)


class ParsedSearchResponse(StrictRequest):
    search_params: SearchRequest
    needs_confirmation: Literal[True]
    explanation: str = Field(min_length=1, max_length=4000)
    source: Literal["foundry"]


class HotelFilters(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    destination: ShortText | None = None
    district: ShortText | None = None
    stars: int | None = Field(default=None, ge=1, le=5)
    price_min: float | None = Field(default=None, ge=0, le=100000, allow_inf_nan=False)
    price_max: float | None = Field(default=None, ge=0, le=100000, allow_inf_nan=False)
    currency: Literal["AZN", "GBP", "USD", "EUR"] = "AZN"
    guest_score: float | None = Field(default=None, ge=0, le=10, allow_inf_nan=False)
    amenities: list[ShortText] = Field(default_factory=list, max_length=20)
    distance_to_metro_m: int | None = Field(default=None, ge=0, le=50000)
    family_friendly: bool | None = None
    checkin: DateText | None = None
    checkout: DateText | None = None
    guests: int = Field(default=2, ge=1, le=12)
    seed: int = Field(default=42, ge=0, le=2_147_483_647)

    @model_validator(mode="after")
    def valid_ranges(self) -> HotelFilters:
        if bool(self.checkin) != bool(self.checkout):
            raise ValueError("Check-in and check-out are required together.")
        if self.checkin and self.checkout:
            if not 1 <= (date.fromisoformat(self.checkout) - date.fromisoformat(self.checkin)).days <= 60:
                raise ValueError("Choose between one and sixty nights.")
        if self.price_min is not None and self.price_max is not None and self.price_min > self.price_max:
            raise ValueError("The price range is reversed.")
        return self


class SearchPlanCache:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.plans: OrderedDict[str, str] = OrderedDict()
        self.pending: dict[str, Future[str]] = {}
        self.day: str | None = None

    def clear(self) -> None:
        with self.lock:
            self.plans.clear()

    def get(self, params: dict, today: str) -> dict:
        key = today + ":" + encode(params)
        with self.lock:
            if self.day != today:
                self.plans.clear()
                self.day = today
            cached = self.plans.get(key)
            if cached is not None:
                self.plans.move_to_end(key)
                return json.loads(cached)
            future = self.pending.get(key)
            owner = future is None
            if owner:
                future = Future()
                self.pending[key] = future
        if owner:
            try:
                result = encode(_domain(planning.build_trip, params))
                with self.lock:
                    self.plans[key] = result
                    while len(self.plans) > 64:
                        self.plans.popitem(last=False)
                future.set_result(result)
            except BaseException as error:
                future.set_exception(error)
                raise
            finally:
                with self.lock:
                    self.pending.pop(key, None)
        # Cached JSON is immutable; IDs, selections and session state are never shared.
        return json.loads(future.result())


class RateLimiter:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.buckets: OrderedDict[tuple[str, str], deque[float]] = OrderedDict()
        self.limits = {
            "ip": {"general": 1200, "search": 240, "ai": 60},
            "session": {"general": 300, "search": 30, "ai": 10},
        }

    def require(self, kind: str, identity: str, category: str) -> None:
        now = time.monotonic()
        categories = ("general",) if category == "general" else ("general", category)
        with self.lock:
            for group in categories:
                key = (f"{kind}:{identity}", group)
                bucket = self.buckets.setdefault(key, deque())
                while bucket and bucket[0] <= now - 60:
                    bucket.popleft()
                self.buckets.move_to_end(key)
                if len(bucket) >= self.limits[kind][group]:
                    raise ServiceError(429, "rate_limited", "Too many requests. Try again in a minute.")
                bucket.append(now)
            while len(self.buckets) > 8192:
                self.buckets.popitem(last=False)


class RequestSafetyMiddleware:
    def __init__(self, app, store: Store, limiter: RateLimiter) -> None:
        self.app, self.store, self.limiter = app, store, limiter

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        request_id = uuid.uuid4().hex
        status = 500
        sent_headers = False
        session_cookie: str | None = None
        path = scope.get("path", "")
        is_api = path == "/api" or path.startswith("/api/")
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        scope.setdefault("state", {})["request_id"] = request_id

        async def safe_send(message) -> None:
            nonlocal status, sent_headers
            if message["type"] == "http.response.start":
                sent_headers = True
                status = message["status"]
                output = list(message.get("headers", []))
                output.extend([
                    (b"x-request-id", request_id.encode("ascii")),
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"content-security-policy", b"frame-ancestors 'none'; base-uri 'self'; object-src 'none'"),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                ])
                if is_api:
                    output = [(key, value) for key, value in output if key.lower() != b"cache-control"]
                    output.append((b"cache-control", b"no-store"))
                if session_cookie:
                    output.append((b"set-cookie", session_cookie.encode("ascii")))
                message = {**message, "headers": output}
            await send(message)

        try:
            cached_receive = receive
            if is_api:
                category = "ai" if path in ("/api/search/parse", "/api/assistant") else (
                    "search" if path == "/api/search" else "general"
                )
                client = scope.get("client")
                self.limiter.require("ip", client[0] if client else "unknown", category)
                if len(scope.get("query_string", b"")) > 4096:
                    raise ServiceError(414, "request_too_large", "The query string is too long.")
                if len(path) > 1024:
                    raise ServiceError(414, "request_too_large", "The request path is too long.")
                if scope["method"] not in ("GET", "HEAD", "OPTIONS"):
                    origin = headers.get(b"origin")
                    if origin:
                        try:
                            parsed = urlsplit(origin.decode("latin-1"))
                        except ValueError:
                            raise ServiceError(403, "origin_rejected", "Cross-origin requests are not accepted.") from None
                        host = headers.get(b"host", b"").decode("latin-1").lower()
                        if parsed.scheme != scope["scheme"] or parsed.netloc.lower() != host:
                            raise ServiceError(403, "origin_rejected", "Cross-origin requests are not accepted.")
                declared = headers.get(b"content-length")
                if declared:
                    try:
                        size = int(declared)
                    except ValueError:
                        raise ServiceError(400, "invalid_request", "Invalid Content-Length.") from None
                    if size < 0:
                        raise ServiceError(400, "invalid_request", "Invalid Content-Length.")
                    if size > MAX_REQUEST_BYTES:
                        raise ServiceError(413, "request_too_large", "The request body is too large.")
                chunks = []
                size = 0
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    size += len(chunk)
                    if size > MAX_REQUEST_BYTES:
                        raise ServiceError(413, "request_too_large", "The request body is too large.")
                    chunks.append(chunk)
                    if not message.get("more_body", False):
                        break
                body = b"".join(chunks)
                content_type = headers.get(b"content-type", b"").split(b";", 1)[0].strip().lower()
                if body and content_type != b"application/json":
                    raise ServiceError(415, "unsupported_media_type", "Use application/json for API requests.")
                consumed = False

                async def cached_receive():
                    nonlocal consumed
                    if not consumed:
                        consumed = True
                        return {"type": "http.request", "body": body, "more_body": False}
                    return await receive()

                cookies = SimpleCookie()
                try:
                    cookies.load(headers.get(b"cookie", b"").decode("latin-1"))
                except CookieError:
                    cookies = SimpleCookie()
                candidate = cookies.get("session_id")
                session_id, new_session, max_age = await run_in_threadpool(
                    self.store.session, candidate.value if candidate else None
                )
                scope["state"]["session_id"] = session_id
                self.limiter.require("session", session_id, category)
                if new_session or scope["scheme"] == "https":
                    cookie = SimpleCookie()
                    cookie["session_id"] = session_id
                    cookie["session_id"]["httponly"] = True
                    cookie["session_id"]["samesite"] = "Strict"
                    cookie["session_id"]["path"] = "/"
                    cookie["session_id"]["max-age"] = max_age
                    if scope["scheme"] == "https":
                        cookie["session_id"]["secure"] = True
                    session_cookie = cookie.output(header="").strip()
            await self.app(scope, cached_receive, safe_send)
        except ServiceError as error:
            if not sent_headers:
                response_headers = {"Retry-After": "60"} if error.status_code == 429 else None
                await JSONResponse(error.payload(), error.status_code, headers=response_headers)(scope, receive, safe_send)
        except Exception as error:
            # The boundary deliberately logs neither exception text nor request contents.
            LOGGER.error(json.dumps({
                "event": "request_error", "request_id": request_id, "error_type": type(error).__name__,
            }))
            if not sent_headers:
                await JSONResponse(
                    {"error": {"code": "internal_error", "message": "The request could not be completed."}},
                    500,
                )(scope, receive, safe_send)
        finally:
            route = scope.get("route")
            LOGGER.info(json.dumps({
                "event": "request", "request_id": request_id,
                "method": scope.get("method", "UNKNOWN"),
                "route": getattr(route, "path", "[unmatched]"),
                "status": status, "duration_ms": round((time.perf_counter() - started) * 1000, 2),
            }))


def _domain(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except ValueError as error:
        raise ServiceError(422, "invalid_selection", str(error)) from error


def _foundry_module():
    try:
        return importlib.import_module("caspian.foundry")
    except ModuleNotFoundError as error:
        if error.name == "caspian.foundry":
            return None
        raise ServiceError(
            503, "ai_dependencies_missing", "The optional hosted-agent dependencies are not installed."
        ) from None


def _agent_status() -> dict:
    try:
        module = _foundry_module()
    except ServiceError as error:
        if error.code != "ai_dependencies_missing":
            raise
        return {"configured": False, "names": []}
    return module.get_agent_status() if module else {"configured": False, "names": []}


class _AbsentFoundryError(Exception):
    pass


async def _ask_foundry(operation: str, *args) -> dict:
    module = _foundry_module()
    if module is None or not module.get_agent_status()["configured"]:
        raise ServiceError(503, "ai_not_configured", "Foundry hosted agents are not configured.")
    try:
        return await asyncio.wait_for(getattr(module, operation)(*args), timeout=MAX_AI_SECONDS)
    except getattr(module, "FoundryNotConfiguredError", _AbsentFoundryError):
        raise ServiceError(503, "ai_not_configured", "Foundry hosted agents are not configured.") from None
    except getattr(module, "FoundryUnavailableError", _AbsentFoundryError):
        raise ServiceError(503, "ai_unavailable", "The Foundry hosted agent is currently unavailable.") from None
    except getattr(module, "FoundryResponseError", _AbsentFoundryError):
        raise ServiceError(502, "ai_invalid_response", "The hosted agent returned an invalid response.") from None
    except TimeoutError:
        raise ServiceError(504, "ai_timeout", "The hosted agent timed out. Please try again.") from None


def create_app(database_path: str | None = None) -> FastAPI:
    store = Store(database_path or os.environ.get("CASPIAN_DATABASE_PATH") or str(
        Path(__file__).resolve().parents[1].joinpath(".data", "caspian.sqlite3")
    ))
    bookings = BookingService(store)
    limiter = RateLimiter()
    plans = SearchPlanCache()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        async def purge_at_midnight():
            while True:
                now = store.now()
                midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), timezone.utc)
                await asyncio.sleep(max(0.05, (midnight - now).total_seconds()))
                await run_in_threadpool(store.purge)
                plans.clear()

        purge_task = asyncio.create_task(purge_at_midnight())
        try:
            yield
        finally:
            purge_task.cancel()
            await asyncio.gather(purge_task, return_exceptions=True)
            store.close()

    application = FastAPI(title="Caspian Compass demo API", debug=False, lifespan=lifespan)
    application.state.store = store
    application.state.bookings = bookings
    application.state.rate_limiter = limiter
    application.state.frontend_dist = Path(__file__).resolve().parents[2].joinpath("web", "dist")
    application.add_middleware(RequestSafetyMiddleware, store=store, limiter=limiter)
    # Uvicorn's default access line contains raw URLs; our structured log excludes queries and identities.
    logging.getLogger("uvicorn.access").disabled = True

    @application.exception_handler(ServiceError)
    async def service_error(request: Request, error: ServiceError):
        return JSONResponse(error.payload(), error.status_code)

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        if error.status_code == 404:
            return JSONResponse(NOT_FOUND, 404)
        return JSONResponse(
            {"error": {"code": "http_error", "message": "The requested operation is not available."}},
            error.status_code,
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        issues = error.errors()
        if request.url.path.endswith("/pay") and any("card_number" in issue["loc"] for issue in issues):
            return JSONResponse(
                {"error": {"code": "test_card_required", "message": "Real cards are not accepted in this demo"}},
                422,
            )
        # Pydantic's default errors echo inputs, including rejected card/document fields.
        fields = {
            ".".join(str(part) for part in issue["loc"]): "Invalid or missing value."
            for issue in issues[:20]
        }
        return JSONResponse(
            {"error": {"code": "validation_error", "message": "Check the request fields.", "fields": fields}},
            422,
        )

    @application.get("/api/meta")
    def meta():
        return {
            "seed": 42, "today": store.now().date().isoformat(), "demo_mode": True,
            "destinations": [
                {"id": destination["id"], "name": destination["name"]}
                for destination in catalog.get_destinations()
            ],
            "interests": list(catalog.INTERESTS), "exchange_rates": catalog.EXCHANGE_RATES,
            "hosted_agents": _agent_status(), "test_cards": list(TEST_CARDS),
        }

    @application.post("/api/search")
    def search(body: SearchRequest, request: Request):
        params = _domain(planning.normalize_search, body.model_dump())
        plan = plans.get(params, store.now().date().isoformat())
        plan["id"] = f"TRIP-{uuid.uuid4().hex.upper()}"
        return JSONResponse(store.save_trip(request.state.session_id, plan))

    @application.post("/api/search/parse")
    async def parse_search(body: ParseRequest):
        result = await _ask_foundry("parse_search", body.text)
        try:
            parsed = ParsedSearchResponse.model_validate(result).model_dump()
            parsed["search_params"] = planning.normalize_search(parsed["search_params"])
            return parsed
        except (ValidationError, ValueError):
            raise ServiceError(502, "ai_invalid_response", "The hosted agent returned invalid search fields.") from None

    @application.get("/api/trip/{trip_id}")
    def get_trip(trip_id: Identifier, request: Request):
        return store.get_trip(request.state.session_id, trip_id)

    @application.patch("/api/trip/{trip_id}")
    def patch_trip(trip_id: Identifier, body: TripChanges, request: Request):
        def update(trip: dict) -> dict:
            params = dict(trip["search_params"])
            if body.pace is not None:
                params["pace"] = body.pace
            selected_activities = body.activity_ids if body.activity_ids is not None else [
                item["activity_id"] for day in trip["itinerary_days"] for item in day["items"]
            ]
            return _domain(
                planning.build_trip, params, trip_id=trip_id,
                selected_hotel_id=body.hotel_id or trip["selected_hotel_id"],
                selected_flight_id=body.flight_id or trip["selected_flight_id"],
                selected_activity_ids=selected_activities,
            )
        return store.update_trip(request.state.session_id, trip_id, update)

    @application.patch("/api/trip/{trip_id}/itinerary")
    def patch_itinerary(trip_id: Identifier, body: ItineraryChanges, request: Request):
        def update(trip: dict) -> dict:
            return _domain(
                planning.build_trip, trip["search_params"], trip_id=trip_id,
                selected_hotel_id=trip["selected_hotel_id"], selected_flight_id=trip["selected_flight_id"],
                selected_activity_ids=[identifier for day in body.days for identifier in day.activity_ids],
                itinerary_override=[day.model_dump() for day in body.days],
            )
        return store.update_trip(request.state.session_id, trip_id, update)

    @application.get("/api/hotels")
    def hotels(filters: Annotated[HotelFilters, Query()]):
        params = filters.model_dump(exclude_none=True)
        params.pop("price_min", None)
        params.pop("price_max", None)
        values = _domain(catalog.get_hotels, params)
        rate = catalog.EXCHANGE_RATES["rates"][filters.currency]
        return [
            hotel for hotel in values
            if (filters.price_min is None or hotel["price_per_night_azn"] * rate >= filters.price_min)
            and (filters.price_max is None or hotel["price_per_night_azn"] * rate <= filters.price_max)
            and (filters.guest_score is None or hotel["guest_score"] >= filters.guest_score)
            and (filters.family_friendly is None or hotel["family_friendly"] == filters.family_friendly)
            and (filters.distance_to_metro_m is None or (
                hotel["distance_to_metro_m"] is not None and hotel["distance_to_metro_m"] <= filters.distance_to_metro_m
            ))
            and set(filters.amenities).issubset(hotel["amenities"])
        ]

    @application.get("/api/hotels/{hotel_id}")
    def hotel(hotel_id: Identifier):
        result = next((hotel for hotel in catalog.get_hotels() if hotel["id"] == hotel_id), None)
        if result is None:
            raise ServiceError(404, "not_found", "Hotel not found.")
        return result

    @application.get("/api/hotels/{hotel_id}/availability")
    def availability(
        hotel_id: Identifier, request: Request, checkin: DateText, checkout: DateText,
        guests: Annotated[int, Query(ge=1, le=12)] = 2,
        room_type_id: Identifier | None = None,
        seed: Annotated[int, Query(ge=0, le=2_147_483_647)] = 42,
    ):
        if not any(hotel["id"] == hotel_id for hotel in catalog.get_hotels()):
            raise ServiceError(404, "not_found", "Hotel not found.")
        return bookings.availability(
            request.state.session_id, hotel_id, checkin, checkout, guests, room_type_id, seed
        )

    @application.get("/api/activities/recommendations")
    def recommendations(trip_id: Identifier, request: Request):
        trip = store.get_trip(request.state.session_id, trip_id)
        hotel = next(hotel for hotel in trip["hotels"] if hotel["id"] == trip["selected_hotel_id"])
        return _domain(planning.recommend_activities, trip["search_params"], hotel)

    @application.get("/api/flights")
    def flights(
        origin: ShortText, depart: DateText,
        return_date: Annotated[DateText, Query(alias="return")],
        seed: Annotated[int, Query(ge=0, le=2_147_483_647)] = 42,
    ):
        return _domain(planning.get_flights, origin, depart, return_date, seed)

    @application.get("/api/transport/plan")
    def transport(trip_id: Identifier, request: Request):
        trip = store.get_trip(request.state.session_id, trip_id)
        return trip["transport_legs"]

    @application.get("/api/checklist")
    def checklist(trip_id: Identifier, request: Request, nationality: Nationality = "GB"):
        trip = store.get_trip(request.state.session_id, trip_id)
        return _domain(planning.build_checklist, trip["search_params"], nationality, store.now().date())

    @application.get("/api/facts")
    def facts():
        return catalog.get_facts(store.now().date())

    @application.post("/api/sim-bookings")
    def create_booking(body: BookingRequest, request: Request):
        return bookings.create(request.state.session_id, body.model_dump())

    @application.get("/api/sim-bookings/{reference}")
    def get_booking(reference: Identifier, request: Request):
        return bookings.get(request.state.session_id, reference)

    @application.post("/api/sim-bookings/{reference}/details")
    def booking_details(reference: Identifier, body: TravellerDetails, request: Request):
        return bookings.details(request.state.session_id, reference, body.model_dump())

    @application.post("/api/sim-bookings/{reference}/pay")
    def pay(reference: Identifier, body: PaymentRequest, request: Request):
        return bookings.pay(request.state.session_id, reference, body.card_number)

    @application.post("/api/sim-bookings/{reference}/cancel")
    def cancel(reference: Identifier, request: Request):
        return bookings.cancel(request.state.session_id, reference)

    @application.get("/api/sim-bookings/{reference}/itinerary.pdf")
    def pdf(reference: Identifier, request: Request):
        booking, trip = bookings.export(request.state.session_id, reference)
        return Response(
            render_pdf(booking, trip, catalog.get_facts(store.now().date())),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{booking["reference"]}-itinerary.pdf"'},
        )

    @application.get("/api/sim-bookings/{reference}/itinerary.ics")
    def calendar_download(reference: Identifier, request: Request):
        booking, trip = bookings.export(request.state.session_id, reference)
        return Response(
            render_ics(booking, trip, catalog.get_facts(store.now().date())),
            media_type="text/calendar; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{booking["reference"]}-itinerary.ics"'},
        )

    @application.post("/api/assistant")
    async def assistant(body: AssistantRequest, request: Request):
        trip = await run_in_threadpool(
            store.get_trip, request.state.session_id, body.trip_id
        ) if body.trip_id else None
        result = await _ask_foundry("ask_assistant", body.message, trip)
        try:
            return AssistantResponse.model_validate(result).model_dump()
        except ValidationError:
            raise ServiceError(502, "ai_invalid_response", "The hosted agent returned an invalid response.") from None

    @application.api_route("/api", methods=["GET", "HEAD", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"])
    @application.api_route("/api/{unknown:path}", methods=["GET", "HEAD", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"])
    def unknown_api(unknown: str = ""):
        return JSONResponse(NOT_FOUND, 404)

    @application.api_route("/{path:path}", methods=["GET", "HEAD"])
    def frontend(path: str):
        dist = application.state.frontend_dist.resolve()
        if "\\" in path or "\x00" in path or any(part.startswith(".") for part in path.split("/") if part):
            return JSONResponse(NOT_FOUND, 404)
        candidate = dist.joinpath(path).resolve()
        if not candidate.is_relative_to(dist):
            return JSONResponse(NOT_FOUND, 404)
        if candidate.is_file():
            return FileResponse(candidate)
        if not Path(path).suffix and dist.joinpath("index.html").is_file():
            return FileResponse(dist.joinpath("index.html"), headers={"Cache-Control": "no-store"})
        return JSONResponse(NOT_FOUND, 404)

    return application


app = create_app()
