/**
 * UXP-617-2-i regression - after a result was opened in place, an App Router
 * navigation back to /flows (the sidebar link, any /flows?q=... link) delivers a
 * new page render with new initial props; the finder must show, not the stale flow.
 */
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { pageElement, searchBox } from "../helpers/flow-finder-ui";

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({ headers: () => new Headers() }));
vi.mock("next/navigation", () => ({
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
  redirect: vi.fn(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  usePathname: () => "/flows",
  useSearchParams: () => new URLSearchParams(window.location.search),
}));

vi.setConfig({ testTimeout: 180000 });

beforeAll(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
});
afterEach(() => cleanup());

describe("a router navigation to /flows after a result was opened", () => {
  it("shows the finder for the new address, not the opened flow", async () => {
    // covers: UXP-617-2-i
    // angle: failure
    const { rerender } = render(await pageElement({ q: "selected option", actor: "human" }));
    fireEvent.click(screen.getByRole("link", { name: "Reuse it, or decide anew?" }));
    await waitFor(() => expect(document.querySelector(".react-flow")).not.toBeNull());

    // the router moves to /flows?q=tracking: the page renders again with new props
    window.history.pushState({}, "", "/flows?q=tracking");
    rerender(await pageElement({ q: "tracking" }));

    await waitFor(() => expect(searchBox().value).toBe("tracking"));
    expect(document.querySelector(".react-flow")).toBeNull();
  });
});
