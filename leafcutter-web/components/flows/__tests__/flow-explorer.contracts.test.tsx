/** Real repository JSON -> loader -> graph selection -> readable drawer seam. */
import React from "react";
import fs from "node:fs";
import path from "node:path";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";

vi.mock("server-only", () => ({}));
vi.mock("@/lib/data/ac-store", () => ({ acById: () => null }));
vi.mock("@/lib/data/repo", async () => {
  const fs = await import("node:fs");
  const path = await import("node:path");
  const root = path.resolve(process.cwd(), "..");
  const file = path.join(root, "docs/product-truth/flows/leafcutter/retrieval-needs-interpretation.flow.json");
  return { repoRoot: () => root, repoPath: (...parts: string[]) => path.join(root, ...parts),
    walk: () => [file], rel: (value: string) => path.relative(root, value).replaceAll("\\", "/"),
    readFileSafe: (value: string) => value === file ? fs.readFileSync(value, "utf8") : null };
});

import { getFlows } from "@/lib/data/flows";
import { FlowExplorer } from "../flow-explorer";

beforeAll(() => {
  // React Flow's browser measurement dependency, not an application seam.
  vi.stubGlobal("ResizeObserver", class {
    observe() {}
    unobserve() {}
    disconnect() {}
  });
});
afterEach(cleanup);

const file = path.resolve(process.cwd(), "../docs/product-truth/flows/leafcutter/retrieval-needs-interpretation.flow.json");
const raw = JSON.parse(fs.readFileSync(file, "utf8"));

describe("real contract flow selection", () => {
  it.each(["steps", "branches"] as const)("renders actual %s contracts after selecting a graph node", (kind) => {
    // covers: UXP-523-1
    // covers: UXP-523-2
    // covers: UXP-523-3
    // angle: seam
    const original = raw[kind].find((node: { io_contracts?: { examples?: unknown[] } }) => node.io_contracts?.examples?.length);
    expect(original).toBeDefined();
    const flow = getFlows().find((item) => item.id === raw.id)!;
    const { container } = render(<FlowExplorer flow={flow} mock={null} />);
    fireEvent.click(screen.getByText(original.label));
    const examples = screen.getByRole("region", { name: "JSON examples" });
    const rendered = Array.from(examples.querySelectorAll("pre"));
    expect(rendered.map((element) => JSON.parse(element.textContent!))).toEqual(
      original.io_contracts.examples.map((example: { value: unknown }) => example.value),
    );
    // No compatibility suffix or label copies survive the selection boundary.
    expect(container.textContent).not.toContain("Contract fields and examples (generated)");
    for (const label of [...original.consumes, ...original.produces]) {
      expect(container.textContent).not.toContain(label);
    }
    expect(screen.getByText(original.human.split("\n\nContract fields and examples (generated)\n")[0], { normalizer: (text) => text })).toBeInTheDocument();
    const bindings = [...original.io_contracts.consumes, ...original.io_contracts.produces];
    expect(screen.getAllByRole("table")).toHaveLength(bindings.length);
    for (const table of screen.getAllByRole("table")) {
      expect(within(table).getByRole("columnheader", { name: "Field" })).toBeInTheDocument();
    }
  });
});
