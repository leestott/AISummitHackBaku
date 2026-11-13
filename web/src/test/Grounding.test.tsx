import { render, screen } from "@testing-library/react";
import { api } from "../api";
import { AboutData } from "../components/AboutData";
import { Assistant } from "../components/Assistant";
import { copy } from "../i18n";
import { money, staleFact } from "../utils";
import { fact, meta } from "./fixtures";

it("marks facts older than 90 days without claiming a fresh verification", () => {
  const baseline = { ...fact, last_verified: "2026-01-01" };
  expect(staleFact(baseline, "2026-04-01")).toBe(false);
  expect(staleFact(baseline, "2026-04-02")).toBe(true);
  render(<AboutData facts={[baseline]} today="2026-04-02" loading={false} error={null} onRetry={vi.fn()} />);
  expect(screen.getByText(copy.common.stale)).toBeInTheDocument();
  expect(screen.getByText(copy.data.sourcesBody)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: copy.common.source })).toHaveAttribute("href", fact.source_url);
});

it("keeps native AZN when rates are unavailable rather than fabricating conversions", () => {
  expect(money(100, "GBP")).toContain("AZN");
  expect(money(100, "GBP")).not.toContain("£");
});

it("does not invent a hosted-agent answer when the service is unconfigured", () => {
  render(<Assistant meta={{ ...meta, hosted_agents: { configured: false, names: [] } }} facts={[fact]} today={meta.today} />);
  expect(screen.getByText(copy.assistant.offline)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: copy.assistant.ask })).toBeDisabled();
  expect(screen.queryByText(copy.assistant.by)).not.toBeInTheDocument();
});

it("surfaces structured API errors and includes the same-origin session cookie", async () => {
  const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({
    error: { code: "agent_unavailable", message: "Hosted service unavailable." },
  }), { status: 503, headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", fetchMock);
  await expect(api.assistant("How do I arrive?", "TRIP-TEST")).rejects.toThrow("Hosted service unavailable.");
  expect(fetchMock).toHaveBeenCalledWith("/api/assistant", expect.objectContaining({
    method: "POST", credentials: "same-origin", body: JSON.stringify({ message: "How do I arrive?", trip_id: "TRIP-TEST" }),
  }));
});
