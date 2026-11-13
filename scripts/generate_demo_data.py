"""Write a reproducible, grounded snapshot without calling any supplier."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from caspian.catalog import EXCHANGE_RATES, get_activities, get_destinations, get_facts, get_hotels
from caspian.planning import get_flights, normalize_search


def generate(seed: int, arrival: str, departure: str) -> dict:
    params = normalize_search(
        {
            "origin": "London",
            "arrival": arrival,
            "departure": departure,
            "regions": [destination["id"] for destination in get_destinations()],
            "seed": seed,
        }
    )
    facts = get_facts()
    hotels = get_hotels(params)
    activities = get_activities()
    flights = get_flights("London", arrival, departure, seed)
    fact_ids = {fact["id"] for fact in facts}
    for record in [*hotels, *activities, *flights]:
        references = record.get("grounding_refs", [])
        if record.get("is_synthetic") is not True or not references or not set(references) <= fact_ids:
            raise ValueError(f"Synthetic record has missing or invalid grounding: {record['id']}")
    return {
        "seed": seed,
        "search_params": params,
        "is_synthetic": True,
        "notice": "Fictional inventory and illustrative prices. Not a booking feed.",
        "exchange_rates": EXCHANGE_RATES,
        "facts": facts,
        "destinations": get_destinations(),
        "hotels": hotels,
        "activities": activities,
        "flights": flights,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--arrival", default="2027-04-10")
    parser.add_argument("--departure", default="2027-04-14")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(generate(args.seed, args.arrival, args.departure), indent=2, ensure_ascii=True)
    if args.output is None:
        print(result)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as output:
            output.write(result + "\n")
        print(f"Wrote the synthetic snapshot to {args.output}.")
