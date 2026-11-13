import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { api, ApiError } from "../api";
import { BookingFlow } from "../components/BookingFlow";
import { copy } from "../i18n";
import { availability, booking, fact, rates, trip } from "./fixtures";

const props = {
  trip, onBooking: vi.fn(), onClose: vi.fn(), initialRoomId: "double",
  currency: "AZN" as const, rates, facts: [fact], today: "2026-11-13",
};

describe("simulated booking boundaries", () => {
  it("creates a hold using IDs only and never submits a client-computed price", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "availability").mockResolvedValue(availability);
    const create = vi.spyOn(api, "createBooking").mockResolvedValue(booking());
    render(<BookingFlow {...props} booking={null} />);
    const continueButton = screen.getByRole("button", { name: copy.booking.continue });
    await waitFor(() => expect(continueButton).toBeEnabled());
    await user.click(continueButton);
    expect(create).toHaveBeenCalledWith({
      trip_plan_id: trip.id, hotel_id: trip.selected_hotel_id, room_type_id: "double", activity_ids: ["ACT-001", "ACT-002"],
    });
    expect(Object.keys(create.mock.calls[0][0])).not.toEqual(expect.arrayContaining(["price", "total_azn"]));
  });

  it("allows a multi-room party and displays aggregate availability prices without multiplying again", async () => {
    const party = { ...trip, search_params: { ...trip.search_params, adults: 6 } };
    vi.spyOn(api, "availability").mockResolvedValue({
      ...availability, rooms_required: 3, total_azn: 2640,
      nights: availability.nights.map(night => ({ ...night, price_azn: 660, unit_price_azn: 220 })),
    });
    render(<BookingFlow {...props} trip={party} booking={null} />);
    expect(await screen.findByText(copy.hotels.roomCount(3) + ".")).toBeInTheDocument();
    expect(screen.getByText(/2,640/)).toBeInTheDocument();
    expect(screen.queryByText(/7,920/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: copy.booking.continue })).toBeEnabled();
    expect(api.availability).toHaveBeenCalledWith(trip.selected_hotel_id, "2027-04-10", "2027-04-14", 6, "double", expect.any(AbortSignal));
  });

  it("submits actual e-visa expiry separately from passport expiry and never uses the trip departure as a visa expiry", async () => {
    const user = userEvent.setup();
    const details = vi.spyOn(api, "details").mockResolvedValue(booking("details_captured"));
    render(<BookingFlow {...props} booking={booking()} />);
    await user.type(screen.getByLabelText(copy.booking.name), "Demo Traveller");
    await user.type(screen.getByLabelText(copy.booking.email), "demo@example.test");
    await user.type(screen.getByLabelText(copy.booking.passportExpiry), "2028-01-01");
    await user.type(screen.getByLabelText(copy.booking.visaExpiry), "2027-06-01");
    await user.click(screen.getByRole("button", { name: copy.booking.detailsContinue }));
    expect(details).toHaveBeenCalledWith("SIM-BAK-ABC123", {
      name: "Demo Traveller", email: "demo@example.test", nationality: "GB",
      passport_expiry: "2028-01-01", evisa_expiry: "2027-06-01",
    });
    await screen.findByRole("heading", { name: copy.booking.review });
    expect(screen.queryByLabelText(copy.booking.passportExpiry)).not.toBeInTheDocument();
  });

  it("does not submit traveller details without the sample passport date required by the API", async () => {
    const user = userEvent.setup();
    const details = vi.spyOn(api, "details").mockResolvedValue(booking("details_captured"));
    render(<BookingFlow {...props} booking={booking()} />);
    await user.type(screen.getByLabelText(copy.booking.name), "Demo Traveller");
    await user.type(screen.getByLabelText(copy.booking.email), "demo@example.test");

    await user.click(screen.getByRole("button", { name: copy.booking.detailsContinue }));

    expect(details).not.toHaveBeenCalled();
    expect(screen.getByRole("heading", { name: copy.booking.traveller })).toBeVisible();
  });

  it("shows the server's real-card rejection without pretending payment succeeded", async () => {
    const user = userEvent.setup();
    const pay = vi.spyOn(api, "pay").mockRejectedValue(new ApiError(copy.booking.cardRejected, "real_card_rejected", 422));
    render(<BookingFlow {...props} booking={booking("details_captured")} />);
    await user.click(screen.getByRole("button", { name: copy.booking.paymentContinue }));
    const card = screen.getByLabelText(copy.booking.card);
    await user.clear(card);
    await user.type(card, "4111111111111111");
    await user.click(screen.getByRole("checkbox", { name: copy.booking.agreement }));
    await user.click(screen.getByRole("button", { name: copy.booking.pay }));
    expect(await screen.findByRole("alert")).toHaveTextContent(copy.booking.cardRejected);
    expect(pay).toHaveBeenCalledWith("SIM-BAK-ABC123", "4111111111111111");
    expect(screen.queryByRole("heading", { name: copy.booking.confirmation })).not.toBeInTheDocument();
    expect(card).toHaveValue("4242424242424242");
  });

  it("blocks elapsed holds and refreshes the authoritative booking state", async () => {
    const elapsed = { ...booking(), expires_at: new Date(Date.now() - 2000).toISOString() };
    const refresh = vi.spyOn(api, "booking").mockResolvedValue({ ...elapsed, state: "expired" });
    render(<BookingFlow {...props} booking={elapsed} />);
    expect(screen.getByRole("alert")).toHaveTextContent(copy.booking.expired);
    expect(screen.queryByRole("button", { name: copy.booking.detailsContinue })).not.toBeInTheDocument();
    await waitFor(() => expect(refresh).toHaveBeenCalledOnce());
  });

  it("uses real server download endpoints and requires confirmation before cancellation", async () => {
    const user = userEvent.setup();
    const cancel = vi.spyOn(api, "cancel").mockResolvedValue(booking("cancelled_simulated"));
    render(<BookingFlow {...props} booking={booking("confirmed_simulated")} />);
    expect(screen.getByText(copy.booking.watermark)).toBeVisible();
    expect(screen.getByRole("link", { name: copy.booking.pdf })).toHaveAttribute("href", "/api/sim-bookings/SIM-BAK-ABC123/itinerary.pdf");
    expect(screen.getByRole("link", { name: copy.booking.calendar })).toHaveAttribute("href", "/api/sim-bookings/SIM-BAK-ABC123/itinerary.ics");
    await user.click(screen.getByRole("button", { name: copy.booking.cancel }));
    expect(cancel).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: copy.booking.cancelConfirm }));
    expect(cancel).toHaveBeenCalledWith("SIM-BAK-ABC123");
  });
});
