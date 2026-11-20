import { expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReviewWorkspace } from "@/components/review-workspace";
vi.mock("@/components/intelligence-graph", () => ({ IntelligenceGraph: () => <div>Graph</div> }));
vi.mock("@/lib/preferences", () => ({ usePreferences: () => [{ includeInfo: true }] }));
vi.mock("@/lib/api", () => ({ getReview: () => Promise.resolve({ id: "queued", status: "SCANNING", title: "Queued review", kind: "demo", report: null, sources_available: false, finding_states: {}, cancel_requested: false }), api: () => Promise.resolve([]) }));
it("renders a pending job before findings or sources exist", async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><ReviewWorkspace id="queued" /></QueryClientProvider>);
  expect(await screen.findByRole("heading", { name: "Queued review" })).toBeInTheDocument(); expect(screen.getByRole("button", { name: "Cancel review" })).toBeEnabled(); view.unmount(); client.clear();
});
