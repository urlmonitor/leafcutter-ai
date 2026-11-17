/**
 * Shared helpers for the UXP-617-1 finder screen tests (UI side). Not a test
 * file (no .test suffix); vitest does not collect it.
 *
 * Every screen test enters through the real route: the default export of
 * app/flows/page.tsx, awaited with Next's searchParams object, then rendered.
 * The DOM contract pinned here follows the reviewed mockup
 * (atlas-flows-finder.html) and the AC wording:
 *  - one search box labelled "Search flows";
 *  - one role=status polite live region holding the result summary;
 *  - the facet panel is labelled "Filters"; Product, Actor, Kind, Realization,
 *    Level and "I/O not yet defined" are groups (fieldset + legend) of
 *    checkboxes whose row ends in the option's flow count;
 *  - applied chips sit in a "Remove filter <Facet>: <Option>" button each, plus
 *    a "Clear all" link;
 *  - results are cards (article) with the flow name as a link to
 *    /flows/<id>, and step rows (list items) linking to /flows/<id>?step=<node>.
 */
import type React from "react";
import { vi } from "vitest";
import { render, screen, within } from "@testing-library/react";

export const squash = (s: string | null | undefined) => (s ?? "").replace(/\s+/g, " ").trim();

export const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** Point jsdom's address at the finder URL before the page mounts (no spy involved). */
export function setAddress(searchParams: Record<string, string | string[] | undefined>) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(searchParams)) {
    if (v === undefined) continue;
    for (const one of Array.isArray(v) ? v : [v]) qs.append(k, one);
  }
  const s = qs.toString();
  window.history.replaceState({}, "", "/flows" + (s ? "?" + s : ""));
}

export function stubBrowserGlobals() {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
}

/** The page's React element for these searchParams, exactly as Next awaits it. */
export async function pageElement(
  searchParams: Record<string, string | string[] | undefined> = {},
): Promise<React.ReactElement> {
  setAddress(searchParams);
  const mod = await import("@/app/flows/page");
  return (await (mod.default as unknown as (p: unknown) => Promise<React.ReactElement> | React.ReactElement)({
    searchParams,
  })) as React.ReactElement;
}

export async function renderFinderPage(searchParams: Record<string, string | string[] | undefined> = {}) {
  stubBrowserGlobals();
  const el = await pageElement(searchParams);
  return render(el);
}

// ---------------------------------------------------------------- queries

export function statusRegion(): HTMLElement {
  const regions = screen.queryAllByRole("status");
  if (regions.length !== 1) {
    throw new Error(`expected exactly one role=status live region, found ${regions.length}`);
  }
  return regions[0];
}

export const statusText = () => squash(statusRegion().textContent);

export function searchBox(): HTMLInputElement {
  return screen.getByLabelText("Search flows") as HTMLInputElement;
}

export function facetPanel(): HTMLElement {
  return screen.getByLabelText("Filters");
}

export function facetGroup(label: string): HTMLElement {
  return within(facetPanel()).getByRole("group", { name: label });
}

export function optionBox(group: HTMLElement, label: string): HTMLInputElement {
  return within(group).getByRole("checkbox", {
    name: new RegExp("^" + escapeRe(label) + "(\\s*\\d+)?$"),
  }) as HTMLInputElement;
}

/** The count shown beside a facet option: the number its row ends in. */
export function optionCount(box: HTMLElement): number {
  let el: HTMLElement | null = box.parentElement;
  while (el) {
    const m = squash(el.textContent).match(/(\d+)$/);
    if (m && el.querySelectorAll('input[type="checkbox"],[role="checkbox"]').length === 1) {
      return Number(m[1]);
    }
    el = el.parentElement;
  }
  throw new Error("no count found beside the facet option");
}

export const isDisabled = (el: HTMLElement) =>
  (el as HTMLInputElement).disabled === true || el.getAttribute("aria-disabled") === "true";

/** Flow cards in document order: one per link to a bare /flows/<product>/<flow>. */
export function flowLinks(): HTMLAnchorElement[] {
  const seen = new Set<string>();
  const out: HTMLAnchorElement[] = [];
  for (const a of Array.from(document.querySelectorAll("a[href]")) as HTMLAnchorElement[]) {
    const href = a.getAttribute("href")!;
    if (/^\/flows\/[a-z0-9-]+\/[a-z0-9-]+$/.test(href) && !seen.has(href)) {
      seen.add(href);
      out.push(a);
    }
  }
  return out;
}

export function cardOf(flowId: string): HTMLElement {
  const link = flowLinks().find((a) => a.getAttribute("href") === `/flows/${flowId}`);
  if (!link) throw new Error(`no result card for ${flowId}`);
  const card = link.closest("article, li");
  if (!card) throw new Error(`result card for ${flowId} is not an article or list item`);
  return card as HTMLElement;
}

/** The step rows of a card: its list items, each with the step link inside. */
export function rowsInCard(card: HTMLElement) {
  return within(card)
    .queryAllByRole("listitem")
    .map((li) => {
      const a = li.querySelector('a[href*="?step="]') as HTMLAnchorElement | null;
      return { li, link: a, text: squash(li.textContent) };
    })
    .filter((r) => r.link !== null);
}

export function chipsAbove(): string[] {
  return screen
    .queryAllByRole("button", { name: /^Remove filter / })
    .map((b) => b.getAttribute("aria-label") ?? squash(b.textContent));
}
