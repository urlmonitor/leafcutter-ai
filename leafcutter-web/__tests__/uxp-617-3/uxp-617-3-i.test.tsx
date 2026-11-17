/**
 * UXP-617-3-i - the keyboard opens and closes a step drawer exactly as a click
 * does: Enter on a focused card opens it, Enter on 'Close step details' closes
 * it, each with one in-place address rewrite and no new history entry. (Ticket
 * names test_uxp_617_3_i.py; vitest only collects *.test.{ts,tsx}.)
 *
 * jsdom does not turn Enter on a native <button> into a click the way a browser
 * does, so pressEnter() below performs that default action itself when the key
 * handler did not prevent it. A key handler that ALSO closes would therefore
 * write twice, as it would in a browser.
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, screen } from "@testing-library/react";
import { addressOf } from "../helpers/flow-routes";
import {
  drawerIds,
  expectNoRouter,
  expectOnScreen,
  here,
  openTab,
  watchNav,
  type NavState,
} from "../helpers/flow-history-nav";
import { cardByName, cardsOf } from "../helpers/flow-cards";
import { dataset } from "../helpers/flow-finder";

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

const PIPE = "leafcutter/flow-render-pipeline";
const RESOLVE_CARD = "Step 2 of 3: Resolve each step to its AC's live work_status (Code)";
const closeButton = () => screen.getByRole("button", { name: "Close step details" });

/** Focus the element, press Enter, and perform the browser's Enter-activates-a-button default. */
function pressEnter(el: HTMLElement) {
  el.focus();
  expect(document.activeElement, "the element can take focus").toBe(el);
  const proceeded = fireEvent.keyDown(el, { key: "Enter", code: "Enter" });
  if (proceeded && el.tagName === "BUTTON") fireEvent.click(el);
}

describe("Enter on a card and on the close button", () => {
  it("Enter on 'Step 2 of 3: Resolve each step … (Code)' opens the resolve drawer at ?step=resolve with history.length unchanged", async () => {
    // covers: UXP-617-3-i
    // angle: criterion
    await openTab(nav, `/flows/${PIPE}`);
    const length = window.history.length;
    const w = watchNav(nav);

    pressEnter(cardByName(RESOLVE_CARD));

    await expectOnScreen({ flow: PIPE, drawer: "resolve", address: `/flows/${PIPE}?step=resolve` });
    expect(w.replace).toHaveBeenCalledTimes(1); // exactly one write per open
    expect(addressOf(w.replace.mock.calls[0][2])).toBe(`/flows/${PIPE}?step=resolve`);
    expect(w.push).not.toHaveBeenCalled();
    expect(window.history.length).toBe(length);
    expectNoRouter(nav);
  });

  it("Enter on 'Close step details' closes the drawer and returns the address with no query, history unchanged", async () => {
    // covers: UXP-617-3-i
    // angle: criterion
    await openTab(nav, `/flows/${PIPE}?step=resolve`); // the drawer is open; only the close key is under test
    await expectOnScreen({ flow: PIPE, drawer: "resolve" });
    const length = window.history.length;
    const w = watchNav(nav);

    pressEnter(closeButton());

    await expectOnScreen({ flow: PIPE, drawer: null, address: `/flows/${PIPE}` });
    expect(w.replace).toHaveBeenCalledTimes(1);
    expect(addressOf(w.replace.mock.calls[0][2])).toBe(`/flows/${PIPE}`);
    expect(w.push).not.toHaveBeenCalled();
    expect(window.history.length).toBe(length);
    expect(here()).toBe(`/flows/${PIPE}`);
    expectNoRouter(nav);
  });

  it("every step and branch card is in the Tab order, and none is hidden from it", async () => {
    // covers: UXP-617-3-i
    // angle: boundary
    for (const flowId of [PIPE, "fern-and-fig/checkout-and-pay"]) {
      await openTab(nav, `/flows/${flowId}`);
      const cards = cardsOf(flowId);
      expect(cards.some((c) => c.kind === "step")).toBe(true);
      for (const c of cards) {
        const el = cardByName(c.name);
        expect(el.tabIndex, `${c.name} is reachable with Tab`).toBeGreaterThanOrEqual(0);
        expect(el.closest('[aria-hidden="true"]'), `${c.name} is not aria-hidden`).toBeNull();
      }
      cleanup();
    }
    expect(cardsOf("fern-and-fig/checkout-and-pay").some((c) => c.kind === "branch")).toBe(true);
  });
});

describe("keyboard-step-drawer session", () => {
  it("replays the dataset by keyboard and makes the same history writes a click session makes", async () => {
    // covers: UXP-617-3-i
    // angle: real_artifact
    const rows = (dataset().entities.FlowNavigation.records as any[])
      .filter((r) => r.session === "keyboard-step-drawer")
      .sort((a, b) => a.seq - b.seq);
    expect(rows).toHaveLength(3);
    const [load, open, close] = rows;

    const writes = (w: ReturnType<typeof watchNav>) => [
      ...w.replace.mock.calls.map((c) => ["replace", addressOf(c[2])] as const),
      ...w.push.mock.calls.map((c) => ["push", addressOf(c[2])] as const),
    ];

    // the click session first: the writes the keyboard session must equal
    await openTab(nav, load.address_bar);
    const wc = watchNav(nav);
    const node = cardsOf(PIPE).find((c) => c.nodeId === open.drawer)!;
    fireEvent.click(cardByName(node.name));
    await expectOnScreen({ drawer: open.drawer, address: open.address_bar });
    fireEvent.click(closeButton());
    await expectOnScreen({ drawer: null, address: close.address_bar });
    const clickWrites = writes(wc);
    cleanup();
    vi.restoreAllMocks();

    // now by keyboard
    await openTab(nav, load.address_bar);
    const base = window.history.length;
    const wk = watchNav(nav);
    pressEnter(cardByName(node.name));
    await expectOnScreen({ drawer: open.drawer, address: open.address_bar });
    expect(window.history.length - base + 1).toBe(open.history_stack.length);
    expect(open.history_op).toBe("replace");
    pressEnter(closeButton());
    await expectOnScreen({ drawer: null, address: close.address_bar });
    expect(window.history.length - base + 1).toBe(close.history_stack.length);
    expect(close.history_op).toBe("replace");

    expect(writes(wk)).toEqual(clickWrites);
    expect(writes(wk)).toEqual([
      ["replace", open.address_bar],
      ["replace", close.address_bar],
    ]);
    expect(drawerIds()).toEqual([]);
  });
});
