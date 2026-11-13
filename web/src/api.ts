import type {
  AssistantReply, Availability, Booking, ChecklistItem, Fact, Meta,
  ParsedSearch, SearchParams, TripPlan,
} from "../../contracts/api";
import { copy } from "./i18n";

export class ApiError extends Error {
  constructor(message: string, public readonly code: string, public readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : copy.common.unknownError;
}

export function isAborted(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  if (init.signal?.aborted) controller.abort();
  init.signal?.addEventListener("abort", abort, { once: true });
  let timedOut = false;
  const timer = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, 90_000);
  try {
    const response = await fetch(`/api${path}`, {
      ...init,
      credentials: "same-origin",
      headers: { Accept: "application/json", ...(init.body ? { "Content-Type": "application/json" } : {}), ...init.headers },
      signal: controller.signal,
    });
    if (!response.ok) {
      const body: unknown = await response.json().catch(() => null);
      const details = isRecord(body) && isRecord(body.error) ? body.error : null;
      const message = details && typeof details.message === "string"
        ? details.message
        : copy.common.httpError(response.status);
      const code = details && typeof details.code === "string" ? details.code : "http_error";
      throw new ApiError(message, code, response.status);
    }
    try {
      // The canonical server contract owns successful JSON shapes; errors are narrowed above.
      return await response.json() as T;
    } catch {
      throw new ApiError(copy.common.invalidResponse, "invalid_json", response.status);
    }
  } catch (error) {
    if (timedOut) throw new ApiError(copy.common.timeout, "timeout", 0);
    if (error instanceof ApiError || isAborted(error)) throw error;
    throw new ApiError(copy.common.networkError, "network_error", 0);
  } finally {
    window.clearTimeout(timer);
    init.signal?.removeEventListener("abort", abort);
  }
}

const json = (value: unknown) => JSON.stringify(value);
const segment = (value: string) => encodeURIComponent(value);

export interface TripPatch {
  hotel_id?: string;
  flight_id?: string;
  activity_ids?: string[];
  pace?: SearchParams["pace"];
}
export interface ItineraryPatch {
  days: { date: string; activity_ids: string[] }[];
}
export interface BookingRequest {
  trip_plan_id: string;
  hotel_id: string;
  room_type_id: string;
  activity_ids: string[];
  flight_id?: string;
}
export interface TravellerDetails {
  name: string;
  email: string;
  nationality: string;
  passport_expiry: string;
  evisa_expiry?: string;
}

export const api = {
  meta: (signal?: AbortSignal) => request<Meta>("/meta", { signal }),
  facts: (signal?: AbortSignal) => request<Fact[]>("/facts", { signal }),
  search: (params: SearchParams) => request<TripPlan>("/search", { method: "POST", body: json(params) }),
  parseSearch: (text: string) => request<ParsedSearch>("/search/parse", { method: "POST", body: json({ text }) }),
  trip: (id: string) => request<TripPlan>(`/trip/${segment(id)}`),
  updateTrip: (id: string, patch: TripPatch) =>
    request<TripPlan>(`/trip/${segment(id)}`, { method: "PATCH", body: json(patch) }),
  updateItinerary: (id: string, patch: ItineraryPatch) =>
    request<TripPlan>(`/trip/${segment(id)}/itinerary`, { method: "PATCH", body: json(patch) }),
  availability: (hotelId: string, checkin: string, checkout: string, guests: number, roomId: string, signal?: AbortSignal) => {
    const query = new URLSearchParams({ checkin, checkout, guests: String(guests), room_type_id: roomId });
    return request<Availability>(`/hotels/${segment(hotelId)}/availability?${query}`, { signal });
  },
  checklist: (tripId: string, nationality: string) =>
    request<ChecklistItem[]>(`/checklist?${new URLSearchParams({ trip_id: tripId, nationality })}`),
  assistant: (message: string, tripId?: string) =>
    request<AssistantReply>("/assistant", { method: "POST", body: json({ message, ...(tripId ? { trip_id: tripId } : {}) }) }),
  createBooking: (payload: BookingRequest) =>
    request<Booking>("/sim-bookings", { method: "POST", body: json(payload) }),
  booking: (reference: string) => request<Booking>(`/sim-bookings/${segment(reference)}`),
  details: (reference: string, payload: TravellerDetails) =>
    request<Booking>(`/sim-bookings/${segment(reference)}/details`, { method: "POST", body: json(payload) }),
  pay: (reference: string, card_number: string) =>
    request<Booking>(`/sim-bookings/${segment(reference)}/pay`, { method: "POST", body: json({ card_number }) }),
  cancel: (reference: string) =>
    request<Booking>(`/sim-bookings/${segment(reference)}/cancel`, { method: "POST" }),
  download: (reference: string, extension: "pdf" | "ics") =>
    `/api/sim-bookings/${segment(reference)}/itinerary.${extension}`,
};
