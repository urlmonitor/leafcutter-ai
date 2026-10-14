/**
 * UXP-591-1 - FlowsView honours its initial props (flowId, crumbs, filters,
 * step), replacing the hard-wired DEFAULT_ENTRY. Props are passed flat on
 * FlowsView per the ticket's Delivers-To contract.
 */
import React from "react";
import fs from "node:fs";
import path from "node:path";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";

vi.mock("server-only", () => ({}));
vi.mock("next/navigation", () => ({
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/flows",
  useSearchParams: () => new URLSearchParams(),
}));

import { getFlows, mockById, getScreenTitles } from "@/lib/data/flows";
import { FlowsView } from "../flows-view";
import type { MockData } from "@/lib/data/types";

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

function mount(flowId: string, filters: { source: string; kind: string; realization: string }) {
  const flows = getFlows();
  const mocks: Record<string, MockData | null> = {};
  for (const f of flows) mocks[f.id] = f.mockDataRef ? mockById(f.mockDataRef) ?? null : null;
  const View = FlowsView as unknown as React.ComponentType<Record<string, unknown>>;
  return render(
    <View
      flows={flows}
      mocks={mocks}
      screenTitles={getScreenTitles()}
      flowId={flowId}
      crumbs={[flowId]}
      filters={filters}
      step={null}
    />,
  );
}

const flowName = (id: string) => getFlows().find((f) => f.id === id)!.name;
const label = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

describe("FlowsView initial props", () => {
  it.each([
    ["fern-and-fig/customer-buys-a-plant", "Mock", "User"],
    ["leafcutter/product-truth-architecture", "Real", "Architecture"],
    ["leafcutter/flow-render-pipeline", "Real", "Data"],
  ])("%s opens at %s / %s / All with the linked flow listed", (id, source, kind) => {
    // covers: UXP-591-1
    // angle: boundary
    mount(id, { source: source.toLowerCase(), kind: kind.toLowerCase(), realization: "all" });
    expect(activeOf("Source")).toBe(source);
    expect(activeOf("Kind")).toBe(kind);
    expect(activeOf("Flow")).toContain(flowName(id));
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain(flowName(id));
  });
});

const mockFile = path.resolve(
  process.cwd(),
  "../docs/product-truth/mock-data/leafcutter/atlas-flows.mock.json",
);
const routes = (
  JSON.parse(fs.readFileSync(mockFile, "utf8")).entities.FlowRoute.records as any[]
).filter((r) => r.resolution === "selected" && r.requested_step === null);

describe("atlas-flows.mock.json FlowRoute replay", () => {
  it("has the four selected stepless routes", () => {
    // covers: UXP-591-1
    // angle: real_artifact
    expect(routes.length).toBe(4);
  });

  it.each(routes.map((r) => [r.id, r]))("%s opens with its rendered_flow and filters", (_id, r) => {
    // covers: UXP-591-1
    // angle: real_artifact
    mount(r.rendered_flow, r.filters);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain(
      flowName(r.rendered_flow),
    );
    expect(activeOf("Source")).toBe(label(r.filters.source));
    expect(activeOf("Kind")).toBe(label(r.filters.kind));
    expect(r.address_bar).toBe(r.requested_url);
    expect(r.crumbs).toEqual([r.rendered_flow]);
    expect(r.open_drawer).toBeNull();
  });
});
