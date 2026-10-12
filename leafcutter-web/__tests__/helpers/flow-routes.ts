/**
 * Shared helpers for the UXP-591-1 sub-AC route tests (-i, -ii, -iii).
 * Not a test file (no .test suffix); vitest does not collect it.
 */
import { expect } from "vitest";
import { screen } from "@testing-library/react";
import { NextRequest } from "next/server";

/**
 * Request headers the real middleware forwards downstream, rebuilt from
 * Next.js's documented x-middleware-override-headers /
 * x-middleware-request-<name> mechanism. Piping these into a mocked
 * next/headers is the producer->consumer seam for the request-scoped
 * raw-id channel: the test never needs to know the header's name.
 */
export function forwardedHeaders(res: Response): Headers {
  const out = new Headers();
  const names = res.headers.get("x-middleware-override-headers");
  if (!names) return out;
  for (const n of names.split(",").map((s) => s.trim().toLowerCase())) {
    const v = res.headers.get(`x-middleware-request-${n}`);
    if (v !== null) out.set(n, v);
  }
  return out;
}

export async function runMiddleware(url: string): Promise<Response> {
  const { middleware } = await import("@/middleware");
  return middleware(new NextRequest(url));
}

/** The path after /flows/ exactly as requested: still percent-encoded, no query. */
export function rawIdOf(url: string): string {
  return new URL(url).pathname.slice("/flows/".length);
}

/** params.id as Next.js hands it to a [...id] page: non-empty segments, decoded. */
export function paramsFor(url: string): { id: string[] } {
  return {
    id: rawIdOf(url)
      .split("/")
      .filter((s) => s !== "")
      .map((s) => decodeURIComponent(s)),
  };
}

export function searchParamsOf(url: string): Record<string, string> {
  return Object.fromEntries(new URL(url).searchParams.entries());
}

export function groupButtons(label: string): HTMLElement[] {
  const labs = screen.queryAllByText(label, { selector: "span" });
  if (labs.length === 0) return [];
  const group = labs[0].nextElementSibling as HTMLElement;
  return Array.from(group.querySelectorAll("button"));
}

export function activeButtons(label: string): HTMLElement[] {
  return groupButtons(label).filter((b) => b.className.includes("font-medium"));
}

export function activeOf(label: string): string {
  const active = activeButtons(label);
  expect(active).toHaveLength(1);
  return active[0].textContent!.trim();
}

export const squash = (s: string | null | undefined) => (s ?? "").replace(/\s+/g, " ");

/**
 * Import a module that may not exist yet. A literal import() of an absent
 * module makes vite fail the WHOLE test file at transform time ("no tests");
 * import.meta.glob yields no entry for an absent file instead, so each test
 * reports its own red state (module absent) and goes green once the file exists.
 * Specifiers use the "@/" alias for the leafcutter-web root.
 */
const lazyModules = import.meta.glob([
  "../../app/flows/page.tsx",
  "../../app/flows/\[...id\]/page.tsx",
  "../../app/flows/\[...id\]/not-found.tsx",
  "../../lib/flow-url.ts",
]) as Record<string, () => Promise<unknown>>;

export async function load<T = any>(spec: string): Promise<T> {
  const rel = "../../" + spec.replace(/^@\//, "");
  const key = Object.keys(lazyModules).find(
    (k) => k.replace(/\.(tsx|ts)$/, "") === rel,
  );
  if (!key) throw new Error(`module absent: ${spec} does not exist yet`);
  return (await lazyModules[key]()) as T;
}

/** The open step/branch drawers: the FlowDrawer renders one <aside> per open drawer. */
export function drawers(): Array<{ id: string; label: string; text: string }> {
  return Array.from(document.querySelectorAll("aside")).map((a) => ({
    id: a.querySelector("span.font-mono")?.textContent?.trim() ?? "",
    label: a.querySelector("h3")?.textContent?.trim() ?? "",
    text: squash(a.textContent),
  }));
}

/** Run the middleware on a legacy URL and read the redirect it answers with. */
export async function redirectOf(url: string) {
  const res = await runMiddleware(url);
  const location = res.headers.get("location");
  const u = location ? new URL(location) : null;
  return {
    res,
    location,
    path: u?.pathname ?? null,
    search: u?.search ?? null,
    origin: u?.origin ?? null,
  };
}
