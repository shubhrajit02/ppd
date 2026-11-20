import { afterEach, expect, it, vi } from "vitest";
import { api } from "@/lib/api";
afterEach(() => vi.unstubAllGlobals());
it("sends the local client header and preserves API error messages", async () => {
  const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ code: "bad_input", detail: "Invalid source" }), { status: 422 })); vi.stubGlobal("fetch", fetch);
  await expect(api("/reviews", { method: "POST", body: "{}" })).rejects.toThrow("Invalid source");
  expect(fetch.mock.calls[0][1].headers["X-AICR-Client"]).toBe("web");
});
it("explains disconnected backend", async () => { vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network"))); await expect(api("/health")).rejects.toThrow(/API|engine|backend/i); });
