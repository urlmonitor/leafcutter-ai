/**
 * Shared harness for the UXP-591-5 history tests (select / drill / breadcrumb
 * pushes, Back / Forward restore, filter re-picks). Not a test file.
 *
 * Every test file must declare the same vi.mock calls for next/headers and
 * next/navigation as the UXP-591-4 files. jsdom's History is real: pushState,
 * replaceState, back() and forward() move a real entry list and back()/forward()
 * fire a real (asynchronous) popstate, so these tests drive the view the way a
 * browser would.
 */
import fs from "node:fs";
import path from "node:path";
import { expect, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { getFlows } from "@/lib/data/flows";
import { FLOW_VIEW_STATE_KEY } from "@/components/flows/flow-history";
import {
  activeOf,
  addressOf,
  clickNode,
  closeWithX,
  drawers,
  forwardedHeaders,
  groupButtons,
  load,
  runMiddleware,
  squash,
} from "./flow-routes";
import { openAt, placeTabAt, type NavState } from "./drawer-nav";

export type { NavState };

export const DEFAULT = "leafcutter/deliver-a-feature";

export const nameOf = (flowId: string) => getFlows().find((f) => f.id === flowId)!.name;
export const labelOf = (flowId: string, nodeId: string) => {
  const f = getFlows().find((x) => x.id === flowId)!;
  return [...f.steps, ...f.branches].find((x) => x.id === nodeId)!.label;
};

/** A fresh tab: a new tail entry (drops any Forward entries left by an earlier test). */
function freshEntry() {
  window.history.pushState({ __NA: true, __PRIVATE_NEXTJS_INTERNALS_TREE: ["", {}] }, "", "/");
}

export async function openTab(nav: NavState, url: string) {
  freshEntry();
  return openAt(nav, url);
}

/** The Flows view as the 'Flow not found' boundary renders it for `url`. */
export async function openNotFoundTab(nav: NavState, url: string) {
  freshEntry();
  placeTabAt(url);
  nav.headers = forwardedHeaders(await runMiddleware(`http://localhost${url}`));
  const mod = await load("@/app/flows/[...id]/not-found");
  return render(await mod.default());
}

export function watchNav(nav: NavState) {
  nav.routerPush.mockClear();
  nav.routerReplace.mockClear();
  return {
    length: window.history.length,
    replace: vi.spyOn(window.history, "replaceState"),
    push: vi.spyOn(window.history, "pushState"),
  };
}

export type NavWatch = ReturnType<typeof watchNav>;

export function expectNoRouter(nav: NavState) {
  expect(nav.routerPush).not.toHaveBeenCalled();
  expect(nav.routerReplace).not.toHaveBeenCalled();
}

export const here = () => window.location.pathname + window.location.search;

export const storedView = () =>
  (window.history.state ?? {})[FLOW_VIEW_STATE_KEY] as
    | { crumbs: string[]; filters: { source: string; kind: string; realization: string } }
    | undefined;

export const h1 = () => screen.queryAllByRole("heading", { level: 1 }).map((h) => h.textContent ?? "").join(" | ");
export const crumbNames = () =>
  Array.from(document.querySelectorAll("nav button")).map((b) => squash(b.textContent).trim());
export const drawerIds = () => drawers().map((d) => d.id);

export function selectFlow(name: string) {
  const b = groupButtons("Flow").find((x) => squash(x.textContent).includes(name));
  expect(b, `selector entry "${name}"`).toBeTruthy();
  fireEvent.click(b!);
}

export function clickCrumb(name: string) {
  const b = Array.from(document.querySelectorAll("nav button")).find((x) =>
    squash(x.textContent).includes(name),
  );
  expect(b, `breadcrumb "${name}"`).toBeTruthy();
  fireEvent.click(b!);
}

/** Click the drill affordance of a graph node (the node, not its body). */
export function drillNode(label: string) {
  const nodes = Array.from(document.querySelectorAll(".react-flow__node"));
  const node =
    nodes.find((n) => squash(n.textContent).trim().startsWith(label)) ??
    nodes.find((n) => squash(n.textContent).includes(label));
  expect(node, `graph node "${label}"`).toBeTruthy();
  const drill = (node as Element).querySelector("[data-flow-drill]");
  expect(drill, `drill affordance on "${label}"`).toBeTruthy();
  fireEvent.click(drill!);
}

/** 'Open sub-flow' inside the open drawer. */
export function openSubFlowInDrawer() {
  const aside = document.querySelector("aside");
  expect(aside, "an open drawer").toBeTruthy();
  const b = Array.from(aside!.querySelectorAll("button")).find((x) =>
    squash(x.textContent).includes("Open sub-flow"),
  );
  expect(b, "an 'Open sub-flow' button in the drawer").toBeTruthy();
  fireEvent.click(b!);
}

export function setFilter(group: "Source" | "Kind" | "Realization", option: string) {
  const b = groupButtons(group).find((x) => new RegExp(option, "i").test(squash(x.textContent)));
  expect(b, `${group} option "${option}"`).toBeTruthy();
  fireEvent.click(b!);
}

/** Back / Forward through the real jsdom history; resolves when popstate fired. */
export function traverse(dir: "back" | "forward") {
  return new Promise<void>((resolve) => {
    const done = () => {
      window.removeEventListener("popstate", done);
      resolve();
    };
    window.addEventListener("popstate", done);
    if (dir === "back") window.history.back();
    else window.history.forward();
    setTimeout(done, 3000);
  });
}

export async function expectOnScreen(opts: {
  flow?: string | null;
  crumbs?: string[];
  drawer?: string | null;
  address?: string;
}) {
  await waitFor(() => {
    if (opts.address !== undefined) expect(here()).toBe(opts.address);
    if (typeof opts.flow === "string") expect(h1()).toContain(nameOf(opts.flow));
    if (opts.crumbs) {
      const names = opts.crumbs.map(nameOf);
      // a one-flow trail renders no breadcrumb at all
      expect(crumbNames()).toEqual(names.length > 1 ? names : []);
    }
    if (opts.drawer !== undefined) expect(drawerIds()).toEqual(opts.drawer ? [opts.drawer] : []);
  });
}

// ---- FlowNavigation replay ----------------------------------------------

const mockFile = path.resolve(
  process.cwd(),
  "../docs/product-truth/mock-data/leafcutter/atlas-flows.mock.json",
);
const records = JSON.parse(fs.readFileSync(mockFile, "utf8")).entities.FlowNavigation
  .records as any[];

export function sessionRows(session: string, seqs: number[]) {
  return records
    .filter((r) => r.session === session && seqs.includes(r.seq))
    .sort((a, b) => a.seq - b.seq);
}

/** Perform one dataset action against the mounted view. */
async function perform(rec: any, prevFlow: string | null) {
  switch (rec.action) {
    case "drill":
      return drillNode(labelOf(prevFlow!, rec.via_step));
    case "select":
      return selectFlow(nameOf(rec.rendered_flow));
    case "crumb":
      return clickCrumb(nameOf(rec.rendered_flow));
    case "open-drawer":
      return clickNode(labelOf(rec.rendered_flow, rec.drawer));
    case "close-drawer":
      return closeWithX();
    case "back":
    case "forward":
      return traverse(rec.action);
    case "filter": {
      const m = /Sets the (\w+) filter to '(\w+)'/.exec(rec.trigger)!;
      return setFilter(m[1] as "Source" | "Kind" | "Realization", m[2]);
    }
    default:
      throw new Error(`unhandled action ${rec.action}`);
  }
}

/**
 * Replay the given rows of a session record by record: act, then assert the
 * address bar, the flow, the breadcrumb, the drawer, the filters and the size
 * of the history stack the record declares.
 */
export async function replayRows(nav: NavState, rows: any[]) {
  const [first, ...rest] = rows;
  expect(first.action).toBe("load");
  if (first.shows === "not-found") await openNotFoundTab(nav, first.address_bar);
  else await openTab(nav, first.address_bar);
  const base = window.history.length;
  let prevFlow: string | null = first.rendered_flow;
  for (const rec of rest) {
    await perform(rec, prevFlow);
    await waitFor(() => {
      expect(here(), `${rec.id} address`).toBe(rec.address_bar);
      expect(window.history.length - base + 1, `${rec.id} stack`).toBe(rec.history_stack.length);
      expect(drawerIds(), `${rec.id} drawer`).toEqual(rec.drawer ? [rec.drawer] : []);
      if (rec.rendered_flow) {
        expect(h1(), `${rec.id} flow`).toContain(nameOf(rec.rendered_flow));
        const names = rec.crumbs.map(nameOf);
        expect(crumbNames(), `${rec.id} crumbs`).toEqual(names.length > 1 ? names : []);
        expect(document.body.textContent).not.toContain("Flow not found");
      } else {
        expect(document.body.textContent, `${rec.id} notice`).toContain("Flow not found");
      }
    });
    if (rec.rendered_flow) {
      expect(activeOf("Source"), `${rec.id} source`).toBe(rec.filters.source === "mock" ? "Mock" : "Real");
      expect(activeOf("Kind"), `${rec.id} kind`).toBe(
        rec.filters.kind[0].toUpperCase() + rec.filters.kind.slice(1),
      );
    }
    prevFlow = rec.rendered_flow;
  }
}

export { addressOf };

export const groupButtonsText = (label: string) =>
  groupButtons(label).map((b) => squash(b.textContent));
