export type Budget = "economy" | "mid-range" | "premium";
export type Pace = "relaxed" | "balanced" | "packed";
export type Currency = "AZN" | "GBP" | "USD" | "EUR";

export interface SearchParams {
  origin: string;
  arrival: string;
  departure: string;
  adults: number;
  children: number;
  budget: Budget;
  interests: string[];
  regions: string[];
  pace: Pace;
  seed: number;
}

export interface ExchangeRates {
  base: "AZN";
  as_of: string;
  is_indicative: true;
  rates: Record<Currency, number>;
}

export interface Fact {
  id: string;
  topic: string;
  statement: string;
  value: number | string | null;
  unit: string | null;
  source_url: string;
  last_verified: string;
  confidence: string;
  reverify_required: boolean;
}

export interface RoomType {
  id: string;
  name: string;
  max_occupancy: number;
  rate_multiplier: number;
  inventory: number;
}

export interface Hotel {
  id: string;
  name: string;
  destination_id: string;
  district: string;
  lat: number;
  lon: number;
  stars: number;
  amenities: string[];
  base_rate_azn: number;
  price_per_night_azn: number;
  price_total_azn: number;
  nearest_metro: string | null;
  distance_to_metro_m: number | null;
  walking_min_to_old_city: number | null;
  airport_stop: string;
  family_friendly: boolean;
  guest_score: number;
  description: string;
  cancellation_policy: string;
  room_types: RoomType[];
  rooms_required?: number;
  available?: boolean;
  is_synthetic: true;
  grounding_refs: string[];
}

export interface Activity {
  id: string;
  name: string;
  destination_id: string;
  categories: string[];
  duration_min: number;
  season_months: number[];
  indoor: boolean;
  price_azn: number;
  opening_hours: { open: string; close: string };
  capacity_per_slot: number;
  lat: number;
  lon: number;
  description: string;
  how_to_get_there: string;
  is_synthetic: true;
  grounding_refs: string[];
  score: {
    season_fit: number;
    interest_match: number;
    budget_fit: number;
    travel_feasibility: number;
    diversity: number;
    total: number;
  };
}

export interface Flight {
  id: string;
  origin: string;
  destination: string;
  carrier: string;
  depart_local: string;
  arrive_local: string;
  arrival_day_offset: number;
  duration_min: number;
  stops: number;
  via: string | null;
  terminals: string;
  fare_min_gbp: number;
  fare_max_gbp: number;
  schedule_note: string;
  is_indicative: true;
  airline_url: string;
  early_checkin_note: string | null;
  departure_date?: string;
  arrival_date?: string;
  grounding_refs: string[];
}

export interface ItineraryItem {
  activity_id: string;
  title: string;
  start_time: string;
  end_time: string;
  travel_minutes: number;
  price_azn: number;
  transport_note: string;
}

export interface ItineraryDay {
  date: string;
  title: string;
  items: ItineraryItem[];
  total_azn: number;
}

export interface TransportLeg {
  id: string;
  from: string;
  to: string;
  mode: string;
  operator: string;
  duration_min: number;
  fare_azn: number;
  total_azn: number;
  schedule_note: string;
  booking_channel: string;
  last_verified: string;
  fact_refs: string[];
  alternative: string | null;
  approximate: boolean;
}

export interface ChecklistItem {
  id: string;
  title: string;
  description: string;
  severity: "info" | "warning";
  fact_refs: string[];
  source_url: string;
  last_verified: string;
}

export interface Totals {
  hotel_azn: number;
  activities_azn: number;
  transport_azn: number;
  total_azn: number;
  total_gbp: number;
}

export interface TripPlan {
  id: string;
  search_params: SearchParams;
  nights: number;
  hotels: Hotel[];
  flights: Flight[];
  activities: Activity[];
  itinerary_days: ItineraryDay[];
  transport_legs: TransportLeg[];
  checklist: ChecklistItem[];
  totals: Totals;
  selected_hotel_id: string;
  selected_flight_id: string | null;
  notices: string[];
  is_synthetic: true;
  exchange_rates: ExchangeRates;
  planning_mode: "deterministic";
  created_at: string;
}

export interface Availability {
  hotel_id: string;
  room_type_id: string;
  nights: { date: string; price_azn: number; unit_price_azn?: number; available: number; event: string | null }[];
  available: boolean;
  rooms_required?: number;
  total_azn: number;
  is_synthetic: true;
}

export type BookingState =
  | "draft"
  | "held"
  | "details_captured"
  | "payment_simulated"
  | "confirmed_simulated"
  | "expired"
  | "cancelled_simulated";

export interface BookingItem {
  id: string;
  kind: "hotel" | "activity";
  name: string;
  date: string;
  quantity: number;
  unit_price_azn: number;
  total_azn: number;
}

export interface Booking {
  reference: string;
  trip_plan_id: string;
  state: BookingState;
  items: BookingItem[];
  total_azn: number;
  total_gbp: number;
  created_at: string;
  expires_at: string;
  watermark: string;
  notices: string[];
  is_synthetic: true;
}

export interface Meta {
  seed: number;
  today: string;
  demo_mode: true;
  destinations: { id: string; name: string }[];
  interests: string[];
  exchange_rates: ExchangeRates;
  hosted_agents: { configured: boolean; names: string[] };
  test_cards: string[];
}

export interface ParsedSearch {
  search_params: SearchParams;
  needs_confirmation: true;
  explanation: string;
  source: "foundry";
}

export interface AssistantReply {
  message: string;
  source: "foundry";
  agents: string[];
  fact_refs: string[];
}

// All APIs are same-origin; session isolation uses an HttpOnly cookie.
// Errors use { error: { code: string, message: string, fields?: object } }.
//
// GET  /api/meta -> Meta
// POST /api/search (SearchParams) -> TripPlan
// POST /api/search/parse ({ text: string }) -> ParsedSearch
// GET  /api/trip/{id} -> TripPlan
// PATCH /api/trip/{id} ({ hotel_id?, flight_id?, activity_ids?, pace? }) -> TripPlan
// PATCH /api/trip/{id}/itinerary ({ days: { date, activity_ids: string[] }[] }) -> TripPlan
// GET  /api/hotels (spec filters) -> Hotel[]
// GET  /api/hotels/{id} -> Hotel
// GET  /api/hotels/{id}/availability (checkin, checkout, guests, room_type_id?) -> Availability
// GET  /api/activities/recommendations?trip_id= -> Activity[]
// GET  /api/flights?origin=&depart=&return= -> Flight[]
// GET  /api/transport/plan?trip_id= -> TransportLeg[]
// GET  /api/checklist?trip_id=&nationality= -> ChecklistItem[]
// GET  /api/facts -> Fact[]
// POST /api/sim-bookings ({ trip_plan_id, hotel_id, room_type_id, activity_ids, flight_id? }) -> Booking
// POST /api/sim-bookings/{ref}/details ({ name, email, nationality, passport_expiry, evisa_expiry? }) -> Booking
// POST /api/sim-bookings/{ref}/pay ({ card_number }) -> Booking
// POST /api/sim-bookings/{ref}/cancel -> Booking
// GET  /api/sim-bookings/{ref} -> Booking
// GET  /api/sim-bookings/{ref}/itinerary.pdf -> application/pdf
// GET  /api/sim-bookings/{ref}/itinerary.ics -> text/calendar
// POST /api/assistant ({ message, trip_id? }) -> AssistantReply
