import type { Activity, Availability, Booking, Fact, Hotel, Meta, TripPlan } from "../../../contracts/api";
import { exampleSearch } from "../utils";

export const rates = {
  base: "AZN", as_of: "2026-11-13", is_indicative: true,
  rates: { AZN: 1, GBP: 0.46, USD: 0.59, EUR: 0.54 },
} satisfies Meta["exchange_rates"];

export const meta: Meta = {
  seed: 42, today: "2026-11-13", demo_mode: true, destinations: [{ id: "baku", name: "Baku" }],
  interests: ["history", "food"], exchange_rates: rates, hosted_agents: { configured: true, names: ["Trip guide"] },
  test_cards: ["4242424242424242"],
};

export const fact: Fact = {
  id: "FACT-H1", topic: "Airport bus", statement: "A dated baseline airport connection.",
  value: 1.3, unit: "AZN", source_url: "https://www.bakubus.az/quality", last_verified: "2026-11-13",
  confidence: "baseline", reverify_required: false,
};

export const hotel: Hotel = {
  id: "HTL-BAK-001", name: "Test Courtyard House", destination_id: "baku", district: "Icherisheher",
  lat: 40.365, lon: 49.833, stars: 4, amenities: ["wifi", "breakfast"],
  base_rate_azn: 200, price_per_night_azn: 220, price_total_azn: 880, nearest_metro: "Icheri Sheher",
  distance_to_metro_m: 250, walking_min_to_old_city: 4, airport_stop: "28 May",
  family_friendly: true, guest_score: 8.7, description: "Fictional test accommodation.",
  cancellation_policy: "Free simulated cancellation.", room_types: [
    { id: "double", name: "Double room", max_occupancy: 2, rate_multiplier: 1, inventory: 5 },
    { id: "family", name: "Family room", max_occupancy: 4, rate_multiplier: 1.4, inventory: 3 },
  ],
  is_synthetic: true, grounding_refs: [fact.id],
};

export const activity: Activity = {
  id: "ACT-001", name: "Old City walk", destination_id: "baku", categories: ["history"],
  duration_min: 120, season_months: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
  indoor: false, price_azn: 35, opening_hours: { open: "09:00", close: "18:00" }, capacity_per_slot: 12,
  lat: 40.366, lon: 49.833, description: "A fictional slot at a real landmark.",
  how_to_get_there: "Walk from the metro.", is_synthetic: true, grounding_refs: [fact.id],
  score: { season_fit: 1, interest_match: 1, budget_fit: 0.9, travel_feasibility: 1, diversity: 0.6, total: 0.92 },
};
export const foodActivity: Activity = { ...activity, id: "ACT-002", name: "Food walk", categories: ["food"], price_azn: 50 };

export const trip: TripPlan = {
  id: "TRIP-TEST", search_params: exampleSearch("2026-11-13"), nights: 4,
  hotels: [hotel], flights: [], activities: [activity, foodActivity],
  itinerary_days: [{
    date: "2027-04-10", title: "First impressions", total_azn: 170,
    items: [
      { activity_id: activity.id, title: activity.name, start_time: "10:00", end_time: "12:00", travel_minutes: 10, price_azn: 70, transport_note: "Walk" },
      { activity_id: foodActivity.id, title: foodActivity.name, start_time: "13:00", end_time: "15:00", travel_minutes: 15, price_azn: 100, transport_note: "Walk" },
    ],
  }],
  transport_legs: [], checklist: [{
    id: "visa", title: "E-visa stay limit", description: "Confirm the 30-day stay limit before travel.",
    severity: "info", fact_refs: [fact.id], source_url: "https://evisa.gov.az/en/information", last_verified: "2026-11-13",
  }],
  totals: { hotel_azn: 880, activities_azn: 170, transport_azn: 20, total_azn: 1070, total_gbp: 492.2 },
  selected_hotel_id: hotel.id, selected_flight_id: null, notices: [], is_synthetic: true,
  exchange_rates: rates, planning_mode: "deterministic", created_at: "2026-11-13T12:00:00Z",
};

export const availability: Availability = {
  hotel_id: hotel.id, room_type_id: "double", available: true, total_azn: 880, is_synthetic: true,
  nights: [10, 11, 12, 13].map(day => ({ date: `2027-04-${day}`, price_azn: 220, available: 3, event: null })),
};

export function booking(state: Booking["state"] = "held"): Booking {
  return {
    reference: "SIM-BAK-ABC123", trip_plan_id: trip.id, state,
    items: [{ id: "item-1", kind: "hotel", name: hotel.name, date: "2027-04-10", quantity: 4, unit_price_azn: 220, total_azn: 880 }],
    total_azn: 880, total_gbp: 404.8, created_at: new Date().toISOString(), expires_at: new Date(Date.now() + 900_000).toISOString(),
    watermark: "SIMULATED – NOT A RESERVATION", notices: [], is_synthetic: true,
  };
}
