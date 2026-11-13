import { useRef, useState } from "react";
import type { SearchParams, TripPlan } from "../../contracts/api";
import { api, errorMessage, type ItineraryPatch, type TripPatch } from "./api";
import { copy } from "./i18n";

export function useTrip() {
  const [trip, setTrip] = useState<TripPlan | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const lock = useRef(false);

  async function apply(operation: () => Promise<TripPlan>, searching = false): Promise<boolean> {
    if (lock.current) return false;
    lock.current = true;
    setBusy(true);
    setError(null);
    setStatus("");
    try {
      const confirmed = await operation();
      setTrip(confirmed);
      setStatus(searching ? copy.search.success : copy.trip.changesSaved);
      return true;
    } catch (cause) {
      setError(`${errorMessage(cause)}${!searching ? ` ${copy.trip.changesFailed}` : ""}`);
      return false;
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  return {
    trip, busy, error, status,
    search: (params: SearchParams) => apply(() => api.search(params), true),
    update: (patch: TripPatch) => trip ? apply(() => api.updateTrip(trip.id, patch)) : Promise.resolve(false),
    editItinerary: (patch: ItineraryPatch) => trip ? apply(() => api.updateItinerary(trip.id, patch)) : Promise.resolve(false),
  };
}
