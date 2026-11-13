import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { api, ApiError } from "../api";
import { SearchForm } from "../components/SearchForm";
import { copy } from "../i18n";
import { meta, trip } from "./fixtures";

describe("SearchForm", () => {
  it("shows parsed fields and waits for explicit confirmation before a real search", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "parseSearch").mockResolvedValue({
      search_params: trip.search_params, explanation: "Four April nights from London.",
      needs_confirmation: true, source: "foundry",
    });
    const onSearch = vi.fn().mockResolvedValue(true);
    render(<SearchForm meta={meta} busy={false} error={null} locked={false} onSearch={onSearch} />);
    await user.click(screen.getByText(copy.search.natural));
    await user.click(screen.getByLabelText(copy.search.naturalLabel));
    await user.paste("Four nights in Baku from London in April");
    await user.click(screen.getByRole("button", { name: copy.search.parse }));
    expect(await screen.findByRole("heading", { name: copy.search.parsed })).toBeInTheDocument();
    expect(screen.getByLabelText(copy.search.arrival)).toHaveValue("2027-04-10");
    expect(screen.getByLabelText(copy.search.departure)).toHaveValue("2027-04-14");
    expect(onSearch).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: copy.search.confirm }));
    expect(onSearch).toHaveBeenCalledOnce();
    expect(onSearch).toHaveBeenCalledWith(trip.search_params);
  });

  it("keeps structured search usable when hosted parsing fails without inventing a result", async () => {
    const user = userEvent.setup();
    vi.spyOn(api, "parseSearch").mockRejectedValue(new ApiError("Hosted agent unavailable.", "agent_unavailable", 503));
    const onSearch = vi.fn().mockResolvedValue(true);
    render(<SearchForm meta={meta} busy={false} error={null} locked={false} onSearch={onSearch} />);
    await user.click(screen.getByText(copy.search.natural));
    await user.type(screen.getByLabelText(copy.search.naturalLabel), "Please plan my visit");
    await user.click(screen.getByRole("button", { name: copy.search.parse }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Hosted agent unavailable.");
    expect(screen.queryByRole("heading", { name: copy.search.parsed })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: copy.search.submit }));
    await waitFor(() => expect(onSearch).toHaveBeenCalledOnce());
  });

  it("rejects departure before arrival without sending a search", async () => {
    const user = userEvent.setup();
    const onSearch = vi.fn();
    render(<SearchForm meta={meta} initial={{ ...trip.search_params, departure: "2027-04-09" }} busy={false} error={null} locked={false} onSearch={onSearch} />);
    await user.click(screen.getByRole("button", { name: copy.search.submit }));
    expect(screen.getByRole("alert")).toHaveTextContent(copy.search.dateError);
    expect(onSearch).not.toHaveBeenCalled();
  });
});
