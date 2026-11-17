/**
 * UXP-617-2 - the search and the chosen filters live in the /flows address:
 * every edit rewrites the current history entry in place (never a push), typing
 * is coalesced, a pending write is flushed before any push, and a shared
 * address opens the same results. (Ticket names test_uxp_617_2.py; vitest only
 * collects *.test.{ts,tsx}.)
 *
 * Planned design pinned here:
 *  - typing updates the results on every keystroke but writes the address once,
 *    about 250 ms after the last keystroke; ticking a facet writes at once;
 *  - opening a result (UXP-617-2-i) first flushes the pending write, then pushes.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { addressOf, redirectOf, runMiddleware } from "../helpers/flow-routes";
import {
  facetGroup,
  optionBox,
  pageElement,
  renderFinderPage,
  searchBox,
  statusText,
} from "../helpers/flow-finder-ui";
import { coreFn, dataset, run, stateOf, storeIndex } from "../helpers/flow-finder";

const hoisted = vi.hoisted(() => ({ routerPush: vi.fn(), routerReplace: vi.fn(), routerRefresh: vi.fn() }));

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({ headers: () => new Headers() }));
vi.mock("next/navigation", () => ({
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
  redirect: vi.fn(),
  useRouter: () => ({
    push: hoisted.routerPush,
    replace: hoisted.routerReplace,
    refresh: hoisted.routerRefresh,
  }),
  usePathname: () => "/flows",
  useSearchParams: () => new URLSearchParams(window.location.search),
}));

vi.setConfig({ testTimeout: 180000 });

beforeEach(() => {
  hoisted.routerPush.mockClear();
  hoisted.routerReplace.mockClear();
  hoisted.routerRefresh.mockClear();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const here = () => window.location.pathname + window.location.search;
const expectNoRouter = () => {
  expect(hoisted.routerPush).not.toHaveBeenCalled();
  expect(hoisted.routerReplace).not.toHaveBeenCalled();
  expect(hoisted.routerRefresh).not.toHaveBeenCalled();
};

describe("the address module", () => {
  it("build(parse(url)) equals the url for every FlowFinderQuery in atlas-flows.mock.json", async () => {
    // covers: UXP-617-2
    // angle: real_artifact
    const parse = await coreFn("parseFinderQuery");
    const build = await coreFn("buildFinderHref");
    const urls: string[] = dataset().entities.FlowFinderQuery.records.map((r: any) => r.url);
    expect(urls.length).toBeGreaterThanOrEqual(11);
    for (const url of urls) {
      expect(build(parse(new URL(url, "http://localhost").searchParams)), url).toBe(url);
    }
  });

  it("the address names stored values, never labels, and never carries a flow or step parameter", async () => {
    // covers: UXP-617-2
    // angle: discrimination
    const parse = await coreFn("parseFinderQuery");
    const build = await coreFn("buildFinderHref");
    // a hostile address that names a flow and a step: neither survives into the built address
    const state = parse(
      new URLSearchParams("flow=leafcutter/deliver-a-feature&step=plan&q=selected+option&actor=human"),
    );
    const url = build(state);
    expect(url).toBe("/flows?q=selected+option&actor=human");
    expect(url).not.toMatch(/[?&](flow|step)=/);
    // labels are not stored values: 'Person' is not an actor value
    expect(build(parse(new URLSearchParams("actor=Person")))).toBe("/flows");
    // facets in canonical order whatever the order they were chosen in
    const all = parse(new URLSearchParams("screen=checkout&io=gap&kind=user&product=leafcutter&actor=llm"));
    expect(build(all)).toBe("/flows?product=leafcutter&actor=llm&kind=user&io=gap&screen=checkout");
  });

  it("values of one facet are written in the facet's option order: Code, AI agent, Person, Jev", async () => {
    // covers: UXP-617-2
    // angle: discrimination
    const parse = await coreFn("parseFinderQuery");
    const build = await coreFn("buildFinderHref");
    const url = build(parse(new URLSearchParams("actor=jev&actor=human&actor=llm&actor=deterministic")));
    expect(url).toBe("/flows?actor=deterministic&actor=llm&actor=human&actor=jev");
  });
});

describe("editing the finder rewrites the entry in place", () => {
  it("typing 'selected option' then ticking Person rewrites the address twice with history.length unchanged", async () => {
    // covers: UXP-617-2
    // angle: criterion
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    await renderFinderPage({});
    const length = window.history.length;
    const replaceState = vi.spyOn(window.history, "replaceState");
    const pushState = vi.spyOn(window.history, "pushState");

    fireEvent.change(searchBox(), { target: { value: "selected option" } });
    await waitFor(() => expect(here()).toBe("/flows?q=selected+option"));

    fireEvent.click(optionBox(facetGroup("Actor"), "Person"));
    await waitFor(() => expect(here()).toBe("/flows?q=selected+option&actor=human"));

    const live = await run(await storeIndex(), stateOf("selected option", { actor: ["human"] }));
    expect(statusText()).toBe(live.status_text);
    expect(window.history.length).toBe(length);
    expect(pushState).not.toHaveBeenCalled();
    expect(replaceState.mock.calls.map((c) => addressOf(c[2]))).toEqual([
      "/flows?q=selected+option",
      "/flows?q=selected+option&actor=human",
    ]);
    expectNoRouter();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("typing is coalesced: the results follow every keystroke, the address is written once, shortly after the last", async () => {
    // covers: UXP-617-2
    // angle: boundary
    await renderFinderPage({});
    const replaceState = vi.spyOn(window.history, "replaceState");
    replaceState.mockClear();

    for (const text of ["s", "se", "sel", "selected", "selected o", "selected option"]) {
      fireEvent.change(searchBox(), { target: { value: text } });
    }
    // results already show the final text; the address has not been written yet
    const live = await run(await storeIndex(), stateOf("selected option"));
    expect(statusText()).toBe(live.status_text);
    expect(replaceState).not.toHaveBeenCalled();
    expect(here()).toBe("/flows");

    await waitFor(() => expect(here()).toBe("/flows?q=selected+option"));
    expect(replaceState).toHaveBeenCalledTimes(1);
  });

  it("clearing the search and unticking Person returns the address to exactly /flows", async () => {
    // covers: UXP-617-2
    // angle: boundary
    await renderFinderPage({ q: "selected option", actor: "human" });

    fireEvent.change(searchBox(), { target: { value: "" } });
    fireEvent.click(optionBox(facetGroup("Actor"), "Person"));

    await waitFor(() => expect(here()).toBe("/flows"));
    expect(window.location.href.endsWith("/flows")).toBe(true); // no trailing '?'
    expect(statusText()).toBe(`${(await storeIndex()).flows.length} flows`);
  });
});

describe("a shared finder address", () => {
  it("/flows?q=selected+option&actor=human renders the search, the Person chip and the runFinder summary", async () => {
    // covers: UXP-617-2
    // angle: reachability
    await renderFinderPage({ q: "selected option", actor: "human" });

    expect(searchBox().value).toBe("selected option");
    expect(screen.getByRole("button", { name: "Remove filter Actor: Person" })).toBeTruthy();
    const live = await run(await storeIndex(), stateOf("selected option", { actor: ["human"] }));
    expect(statusText()).toBe(live.status_text);
    expect(live.result_count.flows).toBeGreaterThan(0);
  });

  it("unknown parameters and unknown values are ignored: no chip, and the address is not rewritten on load", async () => {
    // covers: UXP-617-2
    // angle: failure
    window.history.replaceState({}, "", "/flows?bogus=1&q=selected+option&actor=human&kind=nonsense");
    const replaceState = vi.spyOn(window.history, "replaceState");
    const el = await pageElement({ bogus: "1", q: "selected option", actor: "human", kind: "nonsense" });
    replaceState.mockClear();
    render(el);
    await new Promise((r) => setTimeout(r, 300));

    expect(screen.getAllByRole("button", { name: /^Remove filter / })).toHaveLength(1);
    expect(replaceState).not.toHaveBeenCalled();
  });

  it.each([
    "http://localhost/flows?q=selected+option&actor=human",
    "http://localhost/flows?product=leafcutter&io=gap&screen=checkout",
  ])("middleware lets %s through with no 308 and no rewrite", async (url) => {
    // covers: UXP-617-2
    // angle: failure
    const res = await runMiddleware(url);
    expect(res.status).toBe(200);
    expect(res.headers.get("location")).toBeNull();
    expect(res.headers.get("x-middleware-rewrite")).toBeNull();
    // control: the legacy link still redirects
    const legacy = await redirectOf("http://localhost/flows?flow=leafcutter%2Fflow-render-pipeline");
    expect(legacy.res.status).toBe(308);
  });
});
