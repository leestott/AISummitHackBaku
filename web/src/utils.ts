import type { Booking, Currency, ExchangeRates, Fact, Hotel, SearchParams, TripPlan } from "../../contracts/api";

export const regionIds = ["sheki", "gabala", "guba", "shahdag", "ganja"] as const;
export const interestIds = ["history", "architecture", "food", "nature", "adventure", "wine", "family", "nightlife"] as const;
export const currencies: Currency[] = ["AZN", "GBP", "USD", "EUR"];

export function exampleSearch(today: string = new Date().toISOString().slice(0, 10)): SearchParams {
  const year = Number(today.slice(0, 4));
  const nextApril = today > `${year}-04-10` ? year + 1 : year;
  return {
    origin: "London", arrival: `${nextApril}-04-10`, departure: `${nextApril}-04-14`,
    adults: 2, children: 0, budget: "mid-range", interests: ["history", "food"],
    regions: [], pace: "balanced", seed: 42,
  };
}

export function formatDate(value: string, short = false): string {
  const date = new Date(value.length === 10 ? `${value}T12:00:00Z` : value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric", month: short ? "short" : "long", ...(short ? {} : { year: "numeric" }), timeZone: "UTC",
  }).format(date);
}

export function money(azn: number, currency: Currency, rates?: ExchangeRates): string {
  const usable = currency === "AZN" || (rates && Number.isFinite(rates.rates[currency]) && rates.rates[currency] > 0);
  const displayCurrency = usable ? currency : "AZN";
  const amount = displayCurrency === "AZN" ? azn : azn * (rates?.rates[displayCurrency] ?? 1);
  return new Intl.NumberFormat("en-GB", {
    style: "currency", currency: displayCurrency, maximumFractionDigits: 2, minimumFractionDigits: 0,
  }).format(amount);
}

export function gbp(value: number): string {
  return new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 }).format(value);
}

export function duration(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return hours ? `${hours}h${rest ? ` ${rest}m` : ""}` : `${rest} min`;
}

export function humanize(value: string): string {
  const text = value.replaceAll("_", " ").replaceAll("-", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function safeUrl(value: string): string | undefined {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) ? url.href : undefined;
  } catch {
    return undefined;
  }
}

export function staleFact(fact: Fact, today: string): boolean {
  const age = (Date.parse(today) - Date.parse(fact.last_verified)) / 86_400_000;
  return Number.isFinite(age) && age > 90;
}

export function suitableRoom(hotel: Hotel | undefined, guests: number): string {
  return hotel?.room_types.find(room => room.max_occupancy >= guests)?.id
    ?? hotel?.room_types.find(room => room.max_occupancy > 0)?.id
    ?? "";
}

export function itineraryIds(trip: TripPlan): string[] {
  return [...new Set(trip.itinerary_days.flatMap(day => day.items.map(item => item.activity_id)))];
}

export function activeHold(booking: Booking | null): boolean {
  return !!booking && ["draft", "held", "details_captured", "payment_simulated"].includes(booking.state);
}

export function remainingHold(booking: Booking, now: number): number {
  return Math.max(0, Math.floor((Date.parse(booking.expires_at) - now) / 1000));
}
