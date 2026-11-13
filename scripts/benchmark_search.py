"""Measure the structured-search acceptance target against a running demo."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import json
import math
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def run(base_url: str, concurrency: int, budget_ms: float) -> int:
    next_april = date.today().year + (date.today() >= date(date.today().year, 4, 10))
    payload = json.dumps(
        {
            "origin": "London",
            "arrival": f"{next_april}-04-10",
            "departure": f"{next_april}-04-14",
            "adults": 2,
            "children": 0,
            "budget": "mid-range",
            "interests": ["history", "food"],
            "regions": [],
            "pace": "balanced",
            "seed": 42,
        }
    ).encode()
    gate = threading.Barrier(concurrency)

    def search(_: int) -> tuple[float, str | None]:
        request = Request(
            f"{base_url.rstrip('/')}/api/search",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        gate.wait(timeout=30)
        started = time.perf_counter()
        try:
            with urlopen(request, timeout=30) as response:
                plan = json.load(response)
            if (
                plan.get("nights") != 4
                or len(plan.get("hotels", [])) < 5
                or len(plan.get("itinerary_days", [])) != 4
                or not any(
                    "H1" in f"{leg.get('operator', '')} {leg.get('schedule_note', '')}"
                    for leg in plan.get("transport_legs", [])
                )
            ):
                return (time.perf_counter() - started) * 1000, "invalid_trip_shape"
            return (time.perf_counter() - started) * 1000, None
        except HTTPError as exc:
            return (time.perf_counter() - started) * 1000, f"HTTP {exc.code}"
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            return (time.perf_counter() - started) * 1000, type(exc).__name__

    # Warm imports, database initialization, and the process before the timed burst.
    with urlopen(f"{base_url.rstrip('/')}/api/meta", timeout=10) as response:
        json.load(response)

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        results = list(executor.map(search, range(concurrency)))
    elapsed = time.perf_counter() - started
    latencies = sorted(latency for latency, _ in results)
    errors = [error for _, error in results if error is not None]
    p95 = latencies[math.ceil(len(latencies) * 0.95) - 1]
    meets_target = not errors and p95 < budget_ms
    print(
        json.dumps(
            {
                "scenario": "London, four April nights, history and food",
                "concurrent_requests": concurrency,
                "errors": errors,
                "elapsed_seconds": round(elapsed, 3),
                "p50_ms": round(latencies[math.ceil(len(latencies) * 0.5) - 1], 2),
                "p95_ms": round(p95, 2),
                "maximum_ms": round(latencies[-1], 2),
                "p95_budget_ms": budget_ms,
                "meets_target": meets_target,
                "scope": "One measured burst; not an availability or production SLA guarantee.",
            },
            indent=2,
        )
    )
    return 0 if meets_target else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--budget-ms", type=float, default=1500)
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 200:
        parser.error("--concurrency must be between 1 and 200")
    if args.budget_ms <= 0:
        parser.error("--budget-ms must be positive")
    raise SystemExit(run(args.base_url, args.concurrency, args.budget_ms))
