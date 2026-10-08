import { describe, expect, it, vi } from "vitest";
import fs from "node:fs";
import path from "node:path";

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

import { getFlows } from "../flows";

describe("canonical structured contracts reach Atlas", () => {
  it("retains definitions, steps, branches and compatibility text from the real flow file", () => {
    // covers: UXP-523-1
    // covers: UXP-523-2
    // angle: real_artifact
    const file = path.resolve(process.cwd(), "../docs/product-truth/flows/leafcutter/retrieval-needs-interpretation.flow.json");
    const raw = JSON.parse(fs.readFileSync(file, "utf8"));
    const flow = getFlows().find((item) => item.id === raw.id)!;
    expect(flow.contractDefinitions).toEqual(raw.contract_definitions);
    for (const [nodes, originals] of [[flow.steps, raw.steps], [flow.branches, raw.branches]] as const) {
      expect(originals.length).toBeGreaterThan(0);
      expect(nodes).toHaveLength(originals.length);
      for (const node of nodes) {
        const original = originals.find((item: { id: string }) => item.id === node.id);
        expect(node.ioContracts).toEqual(original.io_contracts);
        expect(node.human).toBe(original.human);
        expect(node.consumes).toEqual(original.consumes ?? []);
      }
    }
  });
});
