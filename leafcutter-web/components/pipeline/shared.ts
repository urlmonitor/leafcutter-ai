/**
 * Pipeline view — shared client-safe constants & helpers.
 * No server-only imports; safe to pull into any "use client" component here.
 *
 * The Pipeline view teaches how Leafcutter builds software. Everything in this
 * module is grounded in the real registry (config/agent_registry.json) and the
 * two arch docs (agent_delivery_workflows.md, ADR-006-flatten-supervisor-chain).
 */
import type { AgentDef } from "@/lib/data/types";

/* ---------- Agent-category vocabulary (color + label) ---------- */

export interface CatTone {
  label: string;
  hsl: string; // channels, wrap with hsl()
}

export const CATEGORY_TONE: Record<string, CatTone> = {
  planning: { label: "Planning", hsl: "265 60% 66%" }, // orchid
  supervisor: { label: "Supervisor", hsl: "38 92% 58%" }, // amber
  implementation: { label: "Implementation", hsl: "150 64% 52%" }, // leaf
  testing: { label: "Testing", hsl: "168 60% 46%" }, // teal
  research: { label: "Research", hsl: "200 78% 60%" }, // sky
  other: { label: "Utility", hsl: "150 8% 55%" }, // slate
};

export function catKey(a: Pick<AgentDef, "category" | "tier">): string {
  const c = a.category ?? a.tier ?? "other";
  return c in CATEGORY_TONE ? c : "other";
}

export function catTone(a: Pick<AgentDef, "category" | "tier">): CatTone {
  return CATEGORY_TONE[catKey(a)];
}

/** Deterministic left-to-right column order for the constellation. */
export const CATEGORY_ORDER = [
  "planning",
  "supervisor",
  "implementation",
  "testing",
  "research",
  "other",
] as const;

/* ---------- Ticket phase-chain status vocabulary ---------- */
/**
 * The per-ticket `agents` map uses a different enum than work_status:
 *   signed_off | needed | not_needed | failed | skip
 * (see the signoff skill's canonical status enum).
 */
export interface PhaseTone {
  label: string;
  hsl: string;
  /** solid tailwind dot class for legends */
  dot: string;
  text: string;
}

export const PHASE_STATUS_TONE: Record<string, PhaseTone> = {
  signed_off: { label: "Signed off", hsl: "150 60% 48%", dot: "bg-success", text: "text-success" },
  needed: { label: "Needed", hsl: "38 92% 58%", dot: "bg-warning", text: "text-warning" },
  failed: { label: "Failed", hsl: "356 72% 56%", dot: "bg-destructive", text: "text-destructive" },
  skip: { label: "Skipped", hsl: "205 78% 60%", dot: "bg-info", text: "text-info" },
  not_needed: { label: "Not needed", hsl: "150 8% 45%", dot: "bg-muted-foreground/60", text: "text-muted-foreground" },
};

export function phaseTone(status: string): PhaseTone {
  return PHASE_STATUS_TONE[status] ?? PHASE_STATUS_TONE.not_needed;
}

/**
 * Canonical ordering of ticket phase agents (natural dispatch order used by
 * ticket-supervisor). Ticket frontmatter key order is not guaranteed, so the
 * phase-chain visualizer sorts by this rank to render the true sequence.
 */
export const PHASE_ORDER: string[] = [
  "architect-review",
  "adr-author",
  "architecture-diagram-author",
  "documentation-expert",
  "how-to-author",
  "reference-author",
  "explanation-author",
  "llm-expert",
  "test-writer",
  "test-runner",
  "python-coder",
  "sql-coder",
  "sql-query",
  "frontend-coder",
  "change-scope-reviewer",
  "pr-reviewer",
  "user-surface-smoker",
  "ac-validator",
  "ac-fulfillment-gate",
  "status-checker",
  "commit",
  "pull-request",
];

export function phaseRank(name: string): number {
  const i = PHASE_ORDER.indexOf(name);
  return i === -1 ? PHASE_ORDER.length + 1 : i;
}

/** A phase agent counts as "active" in a chain when it was actually engaged. */
export function isActivePhase(status: string): boolean {
  return status !== "not_needed";
}

/* ---------- Four-stage flow (the headline explainer) ---------- */

export interface StageAgent {
  id: string; // registry id (used to cross-check existence)
  note?: string;
}

export interface Stage {
  key: string;
  index: number;
  command: string;
  title: string;
  tagline: string;
  purpose: string;
  output: string;
  /** botanical accent (channels) */
  hsl: string;
  agents: StageAgent[];
}

export const STAGES: Stage[] = [
  {
    key: "plan",
    index: 1,
    command: "/plan-feature",
    title: "Plan",
    tagline: "From intent to acceptance criteria",
    purpose:
      "A triage agent classifies the request, then the authoring chain writes acceptance criteria top-down: customer value (L0) → feature benefit (L1) → testable Gherkin (L2) → edge cases (L3), enriched with technical contracts.",
    output: "Approved ACs land in the AC store — no ticket files yet.",
    hsl: "265 60% 66%",
    agents: [
      { id: "ac-triage", note: "classify request" },
      { id: "product-owner", note: "L0 / L1 value" },
      { id: "business-analyst", note: "L2 / L3 behavior" },
      { id: "it-po", note: "technical enrichment" },
    ],
  },
  {
    key: "select",
    index: 2,
    command: "/build-ac",
    title: "Select",
    tagline: "Rank the backlog, cut a ticket",
    purpose:
      "The coordinator ranks approved-but-unbuilt ACs by priority then complexity, picks the top one, and generates a fully-wired ticket from it — writing the implemented_by back-reference into the AC.",
    output: "One ready ticket, traceable to its AC. Hands off to the user to build.",
    hsl: "200 78% 60%",
    agents: [
      { id: "build-ac", note: "rank + generate ticket" },
      { id: "ac-triage", note: "store scan" },
    ],
  },
  {
    key: "build",
    index: 3,
    command: "/build-feature",
    title: "Build",
    tagline: "Drive one ticket through its phase chain",
    purpose:
      "ticket-supervisor runs at depth 0 and dispatches each phase agent at depth 1 (ADR-006): architect-review → test-writer (TDD red) → coders → pr-reviewer → ac-validator → commit → pull-request. Failures climb an adjudication ladder — retry → cross-agent → brainstorm-lead → halt.",
    output: "Green tests, a reviewed diff, a committed change on a feature branch.",
    hsl: "150 64% 52%",
    agents: [
      { id: "ticket-supervisor", note: "depth-0 orchestrator" },
      { id: "architect-review", note: "blast radius" },
      { id: "test-writer", note: "red baseline" },
      { id: "python-coder", note: "make it green" },
      { id: "pr-reviewer", note: "self-review" },
      { id: "ac-validator", note: "coverage gate" },
      { id: "commit", note: "gated commit" },
      { id: "pull-request", note: "open PR" },
    ],
  },
  {
    key: "finalize",
    index: 4,
    command: "/finalize-feature",
    title: "Finalize",
    tagline: "Merge, verify, close, learn",
    purpose:
      "A depth-0 workflow captures a pre-merge test baseline, merges origin/main, re-runs the suite (triaging regressions), merges the PR only when green, then closes tickets, archives the epic, and writes a retrospective + changelog.",
    output: "Merged to main, tickets closed, epic archived, learnings captured.",
    hsl: "38 92% 58%",
    agents: [
      { id: "status-checker", note: "state check" },
      { id: "test-runner", note: "post-merge suite" },
      { id: "test-failure-triage", note: "regression triage" },
      { id: "worktree-agent", note: "cleanup" },
      { id: "retrospective-agent", note: "learnings" },
      { id: "changelog-agent", note: "release notes" },
    ],
  },
];

/** Human label for a registry agent id (fallback to humanized id). */
export function agentLabel(agents: AgentDef[], id: string): string {
  const a = agents.find((x) => x.id === id);
  if (a) return a.name;
  return id.replace(/[-_]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
