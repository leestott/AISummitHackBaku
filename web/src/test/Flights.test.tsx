import { render, screen } from "@testing-library/react";
import type { Flight } from "../../../contracts/api";
import { Flights } from "../components/Flights";
import { fact, rates, trip } from "./fixtures";

it("uses outbound flight dates rather than labelling an overnight departure with the Azerbaijan arrival date", () => {
  const flight: Flight = {
    id: "LHR-GYD", origin: "London Heathrow", destination: "Baku GYD", carrier: "AZAL",
    depart_local: "22:05", arrive_local: "07:35", arrival_day_offset: 1, duration_min: 330,
    stops: 0, via: null, terminals: "Heathrow T4 → GYD T1", fare_min_gbp: 250, fare_max_gbp: 400,
    schedule_note: "Illustrative pattern only.", is_indicative: true, airline_url: "https://www.azal.az",
    early_checkin_note: "Arrange early check-in directly.", departure_date: "2027-04-09", arrival_date: "2027-04-10",
    grounding_refs: [fact.id],
  };
  render(<Flights trip={{ ...trip, flights: [flight] }} facts={[fact]} today="2026-11-13" busy={false}
    onSelect={vi.fn()} currency="AZN" rates={rates} />);
  expect(screen.getByText("9 Apr")).toHaveAttribute("datetime", "2027-04-09");
  expect(screen.getByText("10 Apr")).toHaveAttribute("datetime", "2027-04-10");
  expect(screen.getByText("Arrange early check-in directly.")).toBeInTheDocument();
});
