import { act, render, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { TripPlan } from "../../../contracts/api";
import { api, ApiError } from "../api";
import { Activities } from "../components/Activities";
import { defaultHotelFilters, filterHotels } from "../components/Hotels";
import { copy } from "../i18n";
import { useTrip } from "../useTrip";
import { fact, hotel, rates, trip } from "./fixtures";

describe("confirmed trip editing", () => {
  it("retains the last saved plan and prices when a patch fails", async () => {
    vi.spyOn(api, "search").mockResolvedValue(trip);
    vi.spyOn(api, "updateTrip").mockRejectedValue(new ApiError("Room unavailable.", "unavailable", 409));
    const { result } = renderHook(() => useTrip());
    await act(async () => { await result.current.search(trip.search_params); });
    await act(async () => { expect(await result.current.update({ hotel_id: "another-hotel" })).toBe(false); });
    expect(result.current.trip).toBe(trip);
    expect(result.current.error).toContain(copy.trip.changesFailed);
    expect(result.current.trip?.totals.total_azn).toBe(1070);
  });

  it("serializes updates so rapid clicks cannot overwrite a newer plan", async () => {
    vi.spyOn(api, "search").mockResolvedValue(trip);
    let resolveUpdate!: (value: TripPlan) => void;
    const patch = vi.spyOn(api, "updateTrip").mockReturnValue(new Promise(resolve => { resolveUpdate = resolve; }));
    const { result } = renderHook(() => useTrip());
    await act(async () => { await result.current.search(trip.search_params); });
    let pending: Promise<boolean>;
    await act(async () => {
      pending = result.current.update({ pace: "relaxed" });
      expect(await result.current.update({ pace: "packed" })).toBe(false);
    });
    expect(patch).toHaveBeenCalledOnce();
    expect(result.current.trip).toBe(trip);
    const revised = { ...trip, search_params: { ...trip.search_params, pace: "relaxed" as const } };
    await act(async () => { resolveUpdate(revised); await pending; });
    expect(result.current.trip).toBe(revised);
  });

  it("provides keyboard reorder controls and does not display an unconfirmed order", async () => {
    const user = userEvent.setup();
    const onEdit = vi.fn().mockResolvedValue(false);
    render(<Activities trip={trip} busy={false} onEdit={onEdit} onUpdate={vi.fn()} currency="AZN" rates={rates} facts={[fact]} today="2026-11-13" />);
    await user.click(screen.getByRole("button", { name: copy.activities.moveUp("Food walk") }));
    expect(onEdit).toHaveBeenCalledWith({ days: [{ date: "2027-04-10", activity_ids: ["ACT-002", "ACT-001"] }] });
    const timelineTitles = screen.getAllByRole("heading", { level: 5 }).map(heading => heading.textContent);
    expect(timelineTitles).toEqual(["Old City walk", "Food walk"]);
  });
});

it("combines hotel filters and excludes a property without a metro distance", () => {
  const far = { ...hotel, id: "far", distance_to_metro_m: null };
  const expensive = { ...hotel, id: "expensive", price_per_night_azn: 900 };
  const noBreakfast = { ...hotel, id: "no-breakfast", amenities: ["wifi"] };
  const visible = filterHotels([hotel, far, expensive, noBreakfast], {
    ...defaultHotelFilters, stars: 4, metro: 500, maxPrice: "300", score: 8, family: true, amenities: ["breakfast"],
  });
  expect(visible.map(item => item.id)).toEqual([hotel.id]);
});
