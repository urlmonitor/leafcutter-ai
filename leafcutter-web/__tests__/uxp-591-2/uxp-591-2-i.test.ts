/**
 * UXP-591-2-i - a step address naming no step or branch opens the flow with a
 * 'Step not found' notice and no drawer. (Ticket names a Python test file;
 * vitest only collects *.test.{ts,tsx}.)
 */
import fs from "node:fs";
import path from "node:path";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import {
  activeOf,
  drawers,
  forwardedHeaders,
  load,
  paramsFor,
  runMiddleware,
  searchParamsOf,
  squash,
} from "../helpers/flow-routes";

const hoisted = vi.hoisted(() => ({ headers: new Headers() }));

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({ headers: () => hoisted.headers }));
vi.mock("next/navigation", () => ({
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
  redirect: vi.fn(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/flows",
  useSearchParams: () => new URLSearchParams(),
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
  hoisted.headers = new Headers();
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

async function openAddress(url: string) {
  const abs = `http://localhost${url}`;
  hoisted.headers = forwardedHeaders(await runMiddleware(abs));
  const mod = await load("@/app/flows/[...id]/page");
  const el = await mod.default({ params: paramsFor(abs), searchParams: searchParamsOf(abs) });
  return render(el);
}

const mockFile = path.resolve(
  process.cwd(),
  "../docs/product-truth/mock-data/leafcutter/atlas-flows.mock.json",
);
const stepNoticeRoutes = (
  JSON.parse(fs.readFileSync(mockFile, "utf8")).entities.FlowRoute.records as any[]
).filter((r) => r.step_notice !== null);

const LINT_DETAIL =
  "This flow has no step or branch with the id 'lint', so it opens without a step drawer.";

describe("unknown step on a known flow", () => {
  it("python-coder-internal?step=lint answers 200 with the flow, Real/Data/All, no drawer and the notice", async () => {
    // covers: UXP-591-2-i
    // angle: reachability
    const { notFound } = await import("next/navigation");
    await openAddress("/flows/leafcutter/python-coder-internal?step=lint");
    expect(notFound).not.toHaveBeenCalled();
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain(
      "Inside python-coder",
    );
    expect(activeOf("Source")).toBe("Real");
    expect(activeOf("Kind")).toBe("Data");
    expect(drawers()).toHaveLength(0);
    expect(squash(document.body.textContent)).toContain("Step not found");
    expect(squash(document.body.textContent)).toContain(LINT_DETAIL);
    expect(document.body.textContent).not.toContain("Flow not found");
    expect(screen.queryAllByRole("navigation")).toHaveLength(0);
  });

  it.each(stepNoticeRoutes.map((r) => [r.id, r]))(
    "%s renders the dataset's step_notice title and detail",
    async (_id, r) => {
      // covers: UXP-591-2-i
      // angle: real_artifact
      await openAddress(r.requested_url);
      const text = squash(document.body.textContent);
      expect(text).toContain(r.step_notice.title);
      expect(text).toContain(r.step_notice.detail);
      expect(drawers()).toHaveLength(0);
      expect(text).not.toContain("Flow not found");
    },
  );

  it("does not rewrite the address: ?step=lint stays, no replaceState on load", async () => {
    // covers: UXP-591-2-i
    // angle: failure
    window.history.pushState({}, "", "/flows/leafcutter/python-coder-internal?step=lint");
    const before = window.history.length;
    const replaceState = vi.spyOn(window.history, "replaceState");
    await openAddress("/flows/leafcutter/python-coder-internal?step=lint");
    await new Promise((r) => setTimeout(r, 0));
    expect(squash(document.body.textContent)).toContain("Step not found");
    expect(replaceState).not.toHaveBeenCalled();
    expect(window.location.search).toBe("?step=lint");
    expect(window.history.length).toBe(before);
  });

  it("the step id is matched exactly, not case-folded: ?step=RESOLVE on flow-render-pipeline is unknown", async () => {
    // covers: UXP-591-2-i
    // angle: boundary
    await openAddress("/flows/leafcutter/flow-render-pipeline?step=RESOLVE");
    expect(drawers()).toHaveLength(0);
    expect(squash(document.body.textContent)).toContain(
      "This flow has no step or branch with the id 'RESOLVE'",
    );
  });

  it("renders a hostile step value as text only", async () => {
    // covers: UXP-591-2-i
    // angle: failure
    await openAddress("/flows/leafcutter/python-coder-internal?step=%3Cimg%20src=x%20onerror=alert(1)%3E");
    expect(squash(document.body.textContent)).toContain("Step not found");
    expect(document.querySelector("img[src='x']")).toBeNull();
  });

  it("control: a known step on the same flow shows no notice and one drawer", async () => {
    // covers: UXP-591-2-i
    // angle: discrimination
    await openAddress("/flows/leafcutter/flow-render-pipeline?step=resolve");
    expect(document.body.textContent).not.toContain("Step not found");
    expect(drawers()).toHaveLength(1);
  });
});
