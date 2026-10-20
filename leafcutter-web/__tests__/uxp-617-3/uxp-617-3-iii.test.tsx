/**
 * UXP-617-3-iii - the criterion chips in a step drawer link /atlas?ac=<id>, and
 * the Atlas opens with that criterion selected and its detail open. (Ticket
 * names test_uxp_617_3_iii.py; vitest only collects *.test.{ts,tsx}.)
 *
 * The chip half already exists (the drawer links /atlas?ac=<id>); the Atlas page
 * ignoring ?ac= is what these tests pin red. The detail drawer is recognised by
 * its heading (the criterion's title) and its id label.
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { drawerIds, openTab, type NavState } from "../helpers/flow-history-nav";

const nav = vi.hoisted(() => ({
  headers: new Headers(),
  routerPush: vi.fn(),
  routerReplace: vi.fn(),
})) as NavState;

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({ headers: () => nav.headers }));
vi.mock("next/navigation", () => ({
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
  redirect: vi.fn(),
  useRouter: () => ({ push: nav.routerPush, replace: nav.routerReplace, refresh: vi.fn() }),
  usePathname: () => "/atlas",
  useSearchParams: () => new URLSearchParams(window.location.search),
}));

import { acById } from "@/lib/data/ac-store";

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
beforeEach(() => {
  nav.headers = new Headers();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const PIPE = "leafcutter/flow-render-pipeline";

async function atlasPage(searchParams: Record<string, string>) {
  window.history.replaceState({}, "", "/atlas?" + new URLSearchParams(searchParams).toString());
  const mod = await import("@/app/atlas/page");
  return (mod.default as unknown as (p: unknown) => Promise<React.ReactElement> | React.ReactElement)({
    searchParams,
  });
}

/** The Atlas detail drawer for an AC: its title heading and its id label. */
function expectDetailOpen(id: string) {
  const title = acById(id)!.title;
  expect(title).toBeTruthy();
  const heading = screen.getByRole("heading", { level: 3, name: title });
  const drawer = heading.closest("aside") as HTMLElement;
  expect(drawer, "the detail drawer").toBeTruthy();
  expect(within(drawer).getByText(id, { selector: "span" })).toBeTruthy();
}

describe("criterion chips in the step drawer", () => {
  it("the resolve drawer shows UXP-411 then UXP-411a, each with its title and an /atlas?ac= link", async () => {
    // covers: UXP-617-3-iii
    // angle: criterion
    await openTab(nav, `/flows/${PIPE}?step=resolve`);
    await waitFor(() => expect(drawerIds()).toEqual(["resolve"]));

    const drawer = document.querySelector("aside") as HTMLElement;
    const chips = Array.from(drawer.querySelectorAll('a[href^="/atlas?ac="]')) as HTMLAnchorElement[];
    expect(chips.map((a) => a.getAttribute("href"))).toEqual(["/atlas?ac=UXP-411", "/atlas?ac=UXP-411a"]);
    expect(chips[0].textContent).toContain(acById("UXP-411")!.title);
    expect(chips[1].textContent).toContain(acById("UXP-411a")!.title);
  });
});

describe("the Atlas opens on a linked criterion", () => {
  it("/atlas?ac=UXP-411 renders UXP-411 selected with its detail open, not the component overview", async () => {
    // covers: UXP-617-3-iii
    // angle: reachability
    render(await atlasPage({ ac: "UXP-411" }));

    expectDetailOpen("UXP-411");
  });

  it("/atlas?ac=UXP-411a opened directly selects UXP-411a with its detail open", async () => {
    // covers: UXP-617-3-iii
    // angle: criterion
    render(await atlasPage({ ac: "UXP-411a" }));

    expectDetailOpen("UXP-411a");
    expect(screen.queryByRole("heading", { level: 3, name: acById("UXP-411")!.title })).toBeNull();
  });

  it("an unknown ?ac= id renders the Atlas overview without throwing and without a detail drawer", async () => {
    // covers: UXP-617-3-iii
    // angle: failure
    const errors = vi.spyOn(console, "error").mockImplementation(() => {});
    render(await atlasPage({ ac: "UXP-0000" }));

    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain("AC Atlas");
    expect(document.querySelector("aside")).toBeNull();
    expect(window.location.search).toBe("?ac=UXP-0000"); // the address is kept
    expect(errors.mock.calls.filter((c) => /error/i.test(String(c[0]?.message ?? c[0])))).toEqual([]);
  });
});
