/**
 * Pure, client-safe prompt assembly for the Pipeline prompt inspector.
 *
 * No filesystem / server imports — given a parsed AgentTemplate and a resolved
 * PromptExample, it produces (a) the list of resolved inputs for the Inputs view
 * and (b) the final assembled prompt string for the Assembled view. Kept pure so
 * the client can recompute instantly when the Mock/Real source is toggled.
 */
import type {
  AgentTemplate,
  PromptExample,
  PromptExampleAc,
  PromptExampleBundle,
  PromptExampleTicket,
  ResolvedInput,
} from "@/lib/data/types";

const UNRESOLVED = "(unresolved — not defined in this example)";

/** Merge the shared bundle with any per-agent override for `agentId`. */
export function effectiveBundle(
  example: PromptExample,
  agentId: string,
): PromptExampleBundle {
  const base = example.shared;
  const over = example.perAgent[agentId];
  if (!over) return base;
  return {
    label: over.label ?? base.label,
    ac: over.ac ?? base.ac,
    ticket: over.ticket ?? base.ticket,
    userRequest: over.userRequest ?? base.userRequest,
    config: { ...base.config, ...(over.config ?? {}) },
  };
}

/** True when a per-agent override exists for this agent in the example. */
export function hasPerAgentOverride(example: PromptExample, agentId: string): boolean {
  return Boolean(example.perAgent[agentId]);
}

/** Render an example AC as a compact, YAML-ish block. */
function renderAc(ac: PromptExampleAc): string {
  const lines = [
    `id: ${ac.id}`,
    `title: ${ac.title}`,
    `level: ${ac.level}`,
    `component: ${ac.component}`,
    `priority: ${ac.priority}`,
    `estimated_complexity: ${ac.complexity}`,
    `readiness: ${ac.readiness}`,
    `work_status: ${ac.workStatus}`,
  ];
  if (ac.assignedAgent) lines.push(`assigned_agent: ${ac.assignedAgent}`);
  if (ac.dependsOn.length) lines.push(`depends_on: [${ac.dependsOn.join(", ")}]`);
  if (ac.criteria) lines.push(`criteria: |\n${indent(ac.criteria, "  ")}`);
  if (ac.itRequirements) lines.push(`it_requirements: |\n${indent(ac.itRequirements, "  ")}`);
  return lines.join("\n");
}

/** Render an example ticket as a compact block. */
function renderTicket(t: PromptExampleTicket): string {
  const lines = [`path: ${t.path || "(unspecified)"}`, `title: ${t.title}`];
  if (t.epic) lines.push(`epic: ${t.epic}`);
  if (t.components.length) lines.push(`components: [${t.components.join(", ")}]`);
  if (t.filesTouched.length) {
    lines.push(`files_touched:\n${t.filesTouched.map((f) => `  - ${f}`).join("\n")}`);
  }
  if (t.testRequirements) {
    lines.push(`## Test Requirements\n${t.testRequirements}`);
  }
  return lines.join("\n");
}

function indent(text: string, pad: string): string {
  return text
    .split("\n")
    .map((l) => (l.length ? pad + l : l))
    .join("\n");
}

/** Resolve one declared input slot against the bundle. */
function resolveSlotValue(
  name: string,
  bundle: PromptExampleBundle,
): { value: string; resolved: boolean } {
  const key = name.toLowerCase();
  if (key === "user_request" || key === "request") {
    return bundle.userRequest
      ? { value: bundle.userRequest, resolved: true }
      : { value: UNRESOLVED, resolved: false };
  }
  if (key === "ticket_path") {
    return bundle.ticket?.path
      ? { value: bundle.ticket.path, resolved: true }
      : { value: UNRESOLVED, resolved: false };
  }
  if (key === "component") {
    return bundle.ac?.component
      ? { value: bundle.ac.component, resolved: true }
      : { value: UNRESOLVED, resolved: false };
  }
  if (key === "ac_id" || key === "ac" || key === "ac_path") {
    return bundle.ac
      ? { value: bundle.ac.id, resolved: true }
      : { value: UNRESOLVED, resolved: false };
  }
  // Fall back to a config value of the same name.
  if (bundle.config[name] != null) {
    return { value: bundle.config[name], resolved: true };
  }
  return { value: UNRESOLVED, resolved: false };
}

/** Resolve a pre-flight read source to what the agent would read. */
function resolvePreFlight(
  source: string,
  bundle: PromptExampleBundle,
): { value: string; resolved: boolean } {
  const s = source.toLowerCase();
  if (s.includes("acceptance-criteria")) {
    return bundle.ac
      ? { value: renderAc(bundle.ac), resolved: true }
      : { value: UNRESOLVED, resolved: false };
  }
  if (s === "ticket_path" || s.includes("tickets/")) {
    return bundle.ticket
      ? { value: renderTicket(bundle.ticket), resolved: true }
      : { value: UNRESOLVED, resolved: false };
  }
  // Any other declared file/dir: name the read target (contents not modelled).
  return { value: `reads ${source}`, resolved: true };
}

/**
 * Build the structured list of resolved inputs (inputs + pre-flight reads +
 * config keys) for the Inputs view.
 */
export function resolveInputs(
  template: AgentTemplate,
  bundle: PromptExampleBundle,
): ResolvedInput[] {
  const rows: ResolvedInput[] = [];

  for (const slot of template.inputs) {
    const { value, resolved } = resolveSlotValue(slot.name, bundle);
    rows.push({
      kind: "input",
      name: slot.name,
      detail: slot.type,
      required: slot.required,
      value,
      resolved,
    });
  }

  for (const pf of template.preFlightReads) {
    const { value, resolved } = resolvePreFlight(pf.source, bundle);
    rows.push({
      kind: "pre_flight",
      name: pf.source,
      detail: pf.condition ?? "pre-flight read",
      required: pf.required,
      value,
      resolved,
    });
  }

  for (const ck of template.configKeys) {
    const has = bundle.config[ck.key] != null;
    rows.push({
      kind: "config",
      name: ck.key,
      detail: "config key",
      required: ck.required,
      value: has ? bundle.config[ck.key] : UNRESOLVED,
      resolved: has,
    });
  }

  return rows;
}

/**
 * Compose the final prompt: the agent's system prompt followed by an injected
 * flight-time context section built from the resolved inputs.
 */
export function assemblePrompt(
  template: AgentTemplate,
  bundle: PromptExampleBundle,
): string {
  const rows = resolveInputs(template, bundle);
  const parts: string[] = [];

  parts.push("################ SYSTEM PROMPT ################");
  parts.push(template.systemPrompt);
  parts.push("");
  parts.push("############ INJECTED CONTEXT (flight-time) ############");
  parts.push(`# example: ${bundle.label}`);

  const inputs = rows.filter((r) => r.kind === "input");
  const reads = rows.filter((r) => r.kind === "pre_flight");
  const cfg = rows.filter((r) => r.kind === "config");

  if (inputs.length) {
    parts.push("");
    parts.push("## Inputs");
    for (const r of inputs) parts.push(renderRow(r));
  }
  if (reads.length) {
    parts.push("");
    parts.push("## Pre-flight reads");
    for (const r of reads) parts.push(renderRow(r));
  }
  if (cfg.length) {
    parts.push("");
    parts.push("## Config");
    for (const r of cfg) parts.push(renderRow(r));
  }

  return parts.join("\n");
}

/** Render one resolved row, block-quoting multi-line values. */
function renderRow(r: ResolvedInput): string {
  if (r.value.includes("\n")) {
    return `- ${r.name}:\n${indent(r.value, "    ")}`;
  }
  return `- ${r.name}: ${r.value}`;
}
