/**
 * UXP-591-1 - canonical flow address. Route + address-module tests.
 * (Ticket names test_uxp_591_1.py; vitest only collects *.test.{ts,tsx}, so the
 * files carry the vitest naming.)
 *
 * Must exist to go green: app/flows/[...id]/page.tsx (default async server
 * component taking { params: { id: string[] }, searchParams }) and
 * lib/flow-url.ts exporting flowHref(flowId, stepId?).
 */
import React from "react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";

vi.mock("server-only", () => ({}));
vi.mock("next/navigation", () => ({
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
  redirect: vi.fn(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/flows",
  useSearchParams: () => new URLSearchParams(),
}));

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
afterEach(cleanup);

function activeOf(label: string): string {
  const lab = screen.getByText(label, { selector: "span" });
  const group = lab.nextElementSibling as HTMLElement;
  const active = Array.from(group.querySelectorAll("button")).filter((b) =>
    b.className.includes("font-medium"),
  );
  expect(active).toHaveLength(1);
  return active[0].textContent!.trim();
}

describe("flowHref", () => {
  it("keeps the slash literal and never emits %2F or ?flow=", async () => {
    // covers: UXP-591-1
    // angle: criterion
    const { flowHref } = await import("@/lib/flow-url");
    expect(flowHref("leafcutter/flow-render-pipeline")).toBe(
      "/flows/leafcutter/flow-render-pipeline",
    );
    expect(flowHref("leafcutter/flow-render-pipeline")).not.toMatch(/%2F|\?flow=/i);
    expect(flowHref("leafcutter/flow-render-pipeline", "resolve")).toBe(
      "/flows/leafcutter/flow-render-pipeline?step=resolve",
    );
    // control: null / absent step adds no query
    expect(flowHref("fern-and-fig/customer-buys-a-plant", null)).toBe(
      "/flows/fern-and-fig/customer-buys-a-plant",
    );
  });
});

describe("catch-all flows route", () => {
  it("opens leafcutter/flow-render-pipeline selected, Real/Data/All, one-flow breadcrumb, no drawer", async () => {
    // covers: UXP-591-1
    // angle: reachability
    const { notFound } = await import("next/navigation");
    const mod = await import("@/app/flows/[...id]/page");
    const el = await mod.default({
      params: { id: ["leafcutter", "flow-render-pipeline"] },
      searchParams: {},
    });
    render(el);
    expect(notFound).not.toHaveBeenCalled();
    expect(
      screen.getByRole("heading", { level: 1, name: "How a flow renders in the Atlas" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Deliver a feature end-to-end")).toBeNull();
    expect(activeOf("Source")).toBe("Real");
    expect(activeOf("Kind")).toBe("Data");
    expect(activeOf("Flow")).toContain("How a flow renders in the Atlas");
    // one-flow breadcrumb: no parent trail, so no multi-crumb nav
    for (const n of screen.queryAllByRole("navigation")) {
      expect(within(n).queryAllByRole("button").length).toBeLessThanOrEqual(1);
    }
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("answers not-found for a path that is not exactly a known two-segment id", async () => {
    // covers: UXP-591-1
    // angle: failure
    const mod = await import("@/app/flows/[...id]/page");
    for (const id of [
      ["leafcutter", "flow-render-pipline"],
      ["leafcutter"],
      ["leafcutter", "flow-render-pipeline", "resolve"],
      ["..", "..", "etc"],
    ]) {
      await expect(
        (async () => render(await mod.default({ params: { id }, searchParams: {} })))(),
      ).rejects.toThrow("NEXT_NOT_FOUND");
    }
  });
});
