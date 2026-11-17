/**
 * UXP-617-2-i - opening a result: a step row or a flow card pushes the flow's
 * address with the flow drawn client-side; Back returns the finder exactly as
 * it was left. (Ticket names test_uxp_617_2_i.py; vitest only collects
 * *.test.{ts,tsx}.)
 *
 * Planned design pinned here (IT-PO accepted default): finder and flow view are
 * one mounted client shell, so opening a result is a native pushState that draws
 * the flow in place, and a popstate onto /flows shows the finder. No router
 * navigation, no server request, no reload.
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { activeOf, addressOf } from "../helpers/flow-routes";
import {
  expectNoRouter,
  expectOnScreen,
  here,
  nameOf,
  openTab,
  storedView,
  traverse,
  watchNav,
  type NavState,
} from "../helpers/flow-history-nav";
import {
  facetGroup,
  optionBox,
  searchBox,
  statusText,
} from "../helpers/flow-finder-ui";
import { finderRecord, run, stateOf, storeIndex, dataset } from "../helpers/flow-finder";

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
beforeEach(() => {
  nav.headers = new Headers();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const RETR = "leafcutter/decision-retrieval";
const ROW = "Reuse it, or decide anew?";
const FINDER = "/flows?q=selected+option&actor=human";
const STEP_ADDRESS = `/flows/${RETR}?step=offer-reuse`;

const rowLink = () => screen.getByRole("link", { name: ROW });
const cardLink = () => screen.getByRole("link", { name: nameOf(RETR) });

/** The finder exactly as it was left: the search, the Person chip and the same summary. */
async function expectFinderRestored() {
  const live = await run(await storeIndex(), stateOf("selected option", { actor: ["human"] }));
  await waitFor(() => {
    expect(here()).toBe(FINDER);
    expect(searchBox().value).toBe("selected option");
    expect(screen.getByRole("button", { name: "Remove filter Actor: Person" })).toBeTruthy();
    expect(statusText()).toBe(live.status_text);
  });
  expect(document.querySelector(".react-flow")).toBeNull();
}

describe("opening a result pushes the flow's address", () => {
  it("clicking 'Reuse it, or decide anew?' adds /flows/leafcutter/decision-retrieval?step=offer-reuse with its drawer, Real, Data, All and a one-flow breadcrumb", async () => {
    // covers: UXP-617-2-i
    // angle: criterion
    await openTab(nav, FINDER);
    const before = window.history.length;
    const w = watchNav(nav);
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    const proceeded = fireEvent.click(rowLink());

    expect(proceeded, "a plain click is handled in-app").toBe(false);
    await expectOnScreen({ flow: RETR, crumbs: [RETR], drawer: "offer-reuse", address: STEP_ADDRESS });
    expect(w.push).toHaveBeenCalledTimes(1);
    expect(addressOf(w.push.mock.calls[0][2])).toBe(STEP_ADDRESS);
    expect(window.history.length).toBe(before + 1);
    // the finder entry was not rewritten into the flow's address
    for (const call of w.replace.mock.calls) expect(addressOf(call[2])).not.toContain(`/flows/${RETR}`);
    expect(activeOf("Source")).toBe("Real");
    expect(activeOf("Kind")).toBe("Data");
    expect(activeOf("Realization")).toBe("All");
    expect(storedView()).toEqual({
      crumbs: [RETR],
      filters: { source: "real", kind: "data", realization: "all" },
    });
    expectNoRouter(nav);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("clicking the Retrieving a decision as precedent flow card adds /flows/leafcutter/decision-retrieval with no drawer open", async () => {
    // covers: UXP-617-2-i
    // angle: boundary
    await openTab(nav, FINDER);
    const before = window.history.length;
    const w = watchNav(nav);

    expect(fireEvent.click(cardLink())).toBe(false);

    await expectOnScreen({ flow: RETR, crumbs: [RETR], drawer: null, address: `/flows/${RETR}` });
    expect(w.push).toHaveBeenCalledTimes(1);
    expect(addressOf(w.push.mock.calls[0][2])).toBe(`/flows/${RETR}`);
    expect(window.history.length).toBe(before + 1);
    expectNoRouter(nav);
  });

  it.each([
    ["Ctrl", { ctrlKey: true }],
    ["Meta", { metaKey: true }],
    ["Shift", { shiftKey: true }],
    ["middle button", { button: 1 }],
  ])("a %s-click on a result row is left to the browser: not intercepted, no push", async (_name, init) => {
    // covers: UXP-617-2-i
    // angle: failure
    await openTab(nav, FINDER);
    const w = watchNav(nav);

    const proceeded = fireEvent.click(rowLink(), init);

    expect(proceeded, "the default action (open in a new tab) is not prevented").toBe(true);
    expect(w.push).not.toHaveBeenCalled();
    expect(here()).toBe(FINDER);
    expect(searchBox().value).toBe("selected option");
  });
});

describe("Back and Forward between the finder and the flow", () => {
  it("Back returns the finder with the search, the Person chip and the same summary; Forward reopens the drawer", async () => {
    // covers: UXP-617-2-i
    // angle: seam
    await openTab(nav, FINDER);
    fireEvent.click(rowLink());
    await expectOnScreen({ flow: RETR, drawer: "offer-reuse", address: STEP_ADDRESS });
    const w = watchNav(nav);

    await traverse("back");
    await expectFinderRestored();
    await traverse("forward");
    await expectOnScreen({ flow: RETR, crumbs: [RETR], drawer: "offer-reuse", address: STEP_ADDRESS });
    expect(activeOf("Kind")).toBe("Data");

    // a pop writes no history
    expect(w.replace).not.toHaveBeenCalled();
    expect(w.push).not.toHaveBeenCalled();
    expectNoRouter(nav);
  });

  it("a search typed just before the click is flushed before the push, so Back shows the finder as it was left", async () => {
    // covers: UXP-617-2-i
    // angle: seam
    await openTab(nav, "/flows");
    const w = watchNav(nav);

    fireEvent.change(searchBox(), { target: { value: "selected option" } }); // coalesced write pending
    fireEvent.click(optionBox(facetGroup("Actor"), "Person"));
    fireEvent.click(rowLink()); // no pause: the write must not be left behind

    await expectOnScreen({ flow: RETR, drawer: "offer-reuse", address: STEP_ADDRESS });
    expect(w.push).toHaveBeenCalledTimes(1);
    // the finder address was written BEFORE the push, and nothing wrote it after
    const lastReplaceBeforePush = Math.max(
      ...w.replace.mock.invocationCallOrder.filter((n) => n < w.push.mock.invocationCallOrder[0]),
    );
    expect(addressOf(w.replace.mock.calls[w.replace.mock.invocationCallOrder.indexOf(lastReplaceBeforePush)][2])).toBe(
      FINDER,
    );
    await new Promise((r) => setTimeout(r, 500)); // a late coalesced write must not land on the flow entry
    expect(here()).toBe(STEP_ADDRESS);

    await traverse("back");
    await expectFinderRestored();
  });
});

describe("find-and-open-step session", () => {
  it("replays load, search, facet, open-result and back record by record", async () => {
    // covers: UXP-617-2-i
    // angle: real_artifact
    const rows = (dataset().entities.FlowNavigation.records as any[])
      .filter((r) => r.session === "find-and-open-step")
      .sort((a, b) => a.seq - b.seq);
    expect(rows).toHaveLength(5);

    await openTab(nav, rows[0].address_bar);
    const base = window.history.length;
    const checkFinder = async (rec: any) => {
      const fq = finderRecord(rec.finder_query);
      await waitFor(() => {
        expect(here(), `${rec.id} address`).toBe(rec.address_bar);
        expect(statusText(), `${rec.id} summary`).toBe(fq.status_text);
        expect(searchBox().value, `${rec.id} search`).toBe(fq.q ?? "");
      });
      expect(document.querySelector(".react-flow"), `${rec.id} shows the finder`).toBeNull();
      expect(window.history.length - base + 1, `${rec.id} stack`).toBe(rec.history_stack.length);
    };

    await checkFinder(rows[0]);
    fireEvent.change(searchBox(), { target: { value: "selected option" } }); // seq 2
    await checkFinder(rows[1]);
    fireEvent.click(optionBox(facetGroup("Actor"), "Person")); // seq 3
    await checkFinder(rows[2]);
    fireEvent.click(rowLink()); // seq 4
    await expectOnScreen({ flow: rows[3].rendered_flow, crumbs: rows[3].crumbs, drawer: rows[3].drawer, address: rows[3].address_bar });
    expect(window.history.length - base + 1).toBe(rows[3].history_stack.length);
    expect(activeOf("Source")).toBe("Real");
    expect(activeOf("Kind")).toBe("Data");
    await traverse("back"); // seq 5
    await checkFinder(rows[4]);
    expect(rows[4].history_index).toBe(0);
  });
});
