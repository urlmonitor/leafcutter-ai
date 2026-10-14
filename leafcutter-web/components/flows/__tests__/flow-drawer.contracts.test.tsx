import React from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { FlowDrawer, type StepView } from "../flow-drawer";

afterEach(cleanup);

const definition = { model: "retrieval_needs_output" };
const base: StepView = {
  id: "interpret", label: "Interpret the question", description: "Keep the original question.",
  screen: null, variant: "step", status: "not_started", reads: [], writes: [],
  acs: [], scenarios: [],
};
const fields = [
  { path: "/original_question", types: ["string"], required: true },
  { path: "/enabled", types: ["boolean"], required: false, default: false },
  { path: "/limit", types: ["integer"], required: false, default: 0 },
  { path: "/model_id", types: ["string", "null"], required: false, default: null },
  { path: "/selections/*", types: ["array"], required: true },
];

function show(extra: Record<string, unknown>) {
  return render(<FlowDrawer step={{ ...base, ...extra } as StepView} mock={null} onClose={() => {}} />);
}

describe("structured flow contracts", () => {
  it("shows one contract heading, readable field table, and each raw example once", () => {
    // covers: UXP-523-1
    // covers: UXP-523-3
    // angle: criterion
    const value = { original_question: "Which tests cover this AC?" };
    const { container } = show({
      consumes: ["retrieval_needs_output/original_question: string (required)"],
      contractDefinitions: { retrieval_needs_output: definition },
      ioContracts: { consumes: [{ contract: "retrieval_needs_output", fields }], produces: [], examples: [
        { contract: "retrieval_needs_output", mode: "projection", origin: "illustrative", label: "Question only", value },
      ] },
    });
    expect(screen.getAllByRole("heading", { name: "Retrieval needs output" })).toHaveLength(1);
    const table = screen.getByRole("table");
    expect(within(table).getByRole("columnheader", { name: "Field" })).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "Required" })).toBeInTheDocument();
    const row = within(table).getByText("original_question").closest("tr")!;
    expect(within(row).getByText("Text")).toBeInTheDocument();
    expect(within(row).getByText("Yes")).toBeInTheDocument();
    for (const value of ["false", "0", "null"]) expect(within(table).getByText(value)).toBeInTheDocument();
    expect(within(table).getByText("Each present item/value")).toBeInTheDocument();
    expect(screen.getByText(/Projection.*not a complete payload/i)).toBeInTheDocument();
    expect(screen.getByText("Illustrative")).toBeInTheDocument();
    expect(container.querySelectorAll("pre")).toHaveLength(1);
    expect(container.querySelector("pre")?.textContent).toBe(JSON.stringify(value, null, 2));
    expect(screen.queryByText(/Contract fields and examples/)).not.toBeInTheDocument();
    expect(screen.queryByText(/retrieval_needs_output\/original_question/)).not.toBeInTheDocument();
    expect(screen.getAllByText(base.description)).toHaveLength(1);
  });

  it("preserves root arrays, escaped field keys, authority and observed provenance", () => {
    // covers: UXP-523-1
    // covers: UXP-523-2
    // angle: boundary
    const value = ["<img src=x onerror=alert(1)>"];
    const { container } = show({
      contractDefinitions: { terms: { schema: "docs/product-truth/schemas/terms.json", authority: "illustrative_design", note: "Proposed; no runtime operation is registered." } },
      ioContracts: { consumes: [], produces: [{ contract: "terms", fields: [
        { path: "", types: ["array"], required: true },
        { path: "/a~1b/c~0d", types: ["string"], required: false },
      ] }], examples: [{ contract: "terms", mode: "full", origin: "observed", label: "Stored array", source: { path: "reports/terms.json", pointer: "/result" }, value }] },
    });
    expect(screen.getByText("Whole value")).toBeInTheDocument();
    expect(screen.getByTitle("JSON pointer: /a~1b/c~0d")).toHaveTextContent("a/b › c~d");
    expect(screen.queryByText("/a~1b/c~0d")).not.toBeInTheDocument();
    expect(screen.getByText("Proposed design")).toBeInTheDocument();
    expect(screen.getByText("Proposed; no runtime operation is registered.")).toBeInTheDocument();
    expect(screen.getByText(/reports\/terms.json/)).toBeInTheDocument();
    expect(screen.getByText("Observed")).toBeInTheDocument();
    expect(container.querySelector("pre")?.textContent).toBe(JSON.stringify(value, null, 2));
    expect(container.querySelector("img")).toBeNull();
  });

  it("shows missing bindings and true non-JSON reasons without generated duplicates", () => {
    // covers: UXP-523-2
    // covers: UXP-523-3
    // angle: criterion
    const { unmount } = show({ description: "Plan the route.", ioContracts: { missing_bindings: [
      { name: "Method plan", direction: "produces", reason: "No scoped multi-method record exists.", source: "docs/product-truth/flows/leafcutter/retrieve-project-knowledge.flow.json" },
    ] } });
    expect(screen.getByText("Method plan")).toBeInTheDocument();
    expect(screen.getByText(/Proposed.*missing JSON binding/i)).toBeInTheDocument();
    expect(screen.getAllByText("Plan the route.")).toHaveLength(1);
    unmount();
    show({ description: "A person approves.", ioContracts: { not_applicable: "This step records a conversation, not a JSON payload." } });
    expect(screen.getByText("This step records a conversation, not a JSON payload.")).toBeInTheDocument();
    expect(screen.getAllByText("A person approves.")).toHaveLength(1);
  });

  it("labels reconstructed projections with the remaining contract obligations", () => {
    // covers: UXP-523-2
    // angle: criterion
    show({ contractDefinitions: { output: { model: "output", authority: "source_reviewed", note: "Reviewed against the producer; no automatic runtime parity." } },
      ioContracts: { consumes: [], produces: [{ contract: "output", fields }], examples: [
        { contract: "output", mode: "projection", origin: "reconstructed", label: "Selected result", value: { original_question: "Which tests?" } },
      ] } });
    expect(screen.getByText("Reconstructed")).toBeInTheDocument();
    expect(screen.getByText("Source reviewed")).toBeInTheDocument();
    expect(screen.getByText("Reviewed against the producer; no automatic runtime parity.")).toBeInTheDocument();
    expect(screen.getByText(/omitted required and defaulted fields remain in the linked contract/i)).toBeInTheDocument();
  });

  it.each([
    { consumes: [], produces: [], examples: [] },
    { consumes: [{ contract: "output", fields: [] }], produces: [], examples: [] },
    { consumes: [{ contract: "output", fields }], produces: [], examples: [
      { contract: "output", mode: "full", origin: "observed", label: "Receipt", value: {} },
    ] },
    { consumes: [{ contract: "output", fields: [{ path: "/question", types: ["wrong"], required: true }] }], produces: [], examples: [
      { contract: "output", mode: "full", origin: "illustrative", label: "Value", value: {} },
    ] },
    { not_applicable: "   " },
    { missing_bindings: [{ name: "Result", direction: "produces", reason: "   ", source: "docs/product-truth/design.md" }] },
  ])("rejects incomplete contract shapes without hiding legacy details", (ioContracts) => {
    // covers: UXP-523-4
    // angle: boundary
    show({ description: "Narrative of what happens.", consumes: ["Legacy input"], produces: ["Legacy output"],
      contractDefinitions: { output: definition }, ioContracts });
    expect(screen.getByText("Narrative of what happens.")).toBeInTheDocument();
    expect(screen.getByText("Legacy input")).toBeInTheDocument();
    expect(screen.getByText("Legacy output")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "JSON examples" })).not.toBeInTheDocument();
  });

  it.each([undefined, { consumes: "invalid" }, { consumes: [{ contract: "unknown", fields }], produces: [], examples: [] }])(
    "keeps the legacy readable fallback when structured metadata is absent or unusable", (ioContracts) => {
      // covers: UXP-523-4
      // angle: failure
      show({ description: "Narrative of what happens.", consumes: ["Legacy input"], ioContracts, contractDefinitions: {} });
      expect(screen.getByText("Narrative of what happens.")).toBeInTheDocument();
      expect(screen.getByText("Legacy input")).toBeInTheDocument();
      expect(screen.queryByRole("table")).not.toBeInTheDocument();
    },
  );

  it.each(["mode", "origin", "authority", "direction"])("rejects coerced %s values and preserves the legacy fallback", (key) => {
    // covers: UXP-523-4
    // angle: discrimination
    const example = { contract: "output", mode: "full", origin: "illustrative", label: "Output", value: {} };
    const contract = { model: "output", authority: "source_reviewed", note: "Reviewed source." };
    const gap = { name: "Pending", direction: "produces", reason: "No binding.", source: "docs/product-truth/flow.json" };
    if (key === "authority") Object.assign(contract, { authority: ["source_reviewed"] });
    else if (key === "direction") Object.assign(gap, { direction: ["produces"] });
    else Object.assign(example, { [key]: [example[key as "mode" | "origin"]] });
    show({ description: "Narrative of what happens.", consumes: ["Legacy input"],
      contractDefinitions: { output: contract }, ioContracts: {
        consumes: [{ contract: "output", fields }], produces: [], examples: [example], missing_bindings: [gap],
      } });
    expect(screen.getByText("Narrative of what happens.")).toBeInTheDocument();
    expect(screen.getByText("Legacy input")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});

describe("who runs the step", () => {
  it("shows the actor kind as a plain badge beside the named agent", () => {
    // covers: UXP-523-3
    // angle: criterion
    const { container } = show({ agent: "pr-reviewer", actorKind: "llm" });
    expect(screen.getByText("Runs")).toBeInTheDocument();
    expect(screen.getByText("pr-reviewer")).toBeInTheDocument();
    const badge = container.querySelector('[data-actor-kind="llm"]');
    expect(badge?.textContent).toBe("AI agent");
  });

  it.each([
    ["deterministic", "Code"], ["jev", "Jev"], ["human", "Person"],
  ])("labels %s in plain words even without an agent", (kind, label) => {
    // covers: UXP-523-3
    // angle: boundary
    const { container } = show({ agent: null, actorKind: kind });
    expect(container.querySelector(`[data-actor-kind="${kind}"]`)?.textContent).toBe(label);
  });

  it("shows no runner section when neither the agent nor the kind is known", () => {
    // covers: UXP-523-3
    // angle: failure
    const { container } = show({ agent: null, actorKind: null });
    expect(screen.queryByText("Runs")).not.toBeInTheDocument();
    expect(container.querySelector("[data-actor-kind]")).toBeNull();
  });
});
