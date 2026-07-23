import * as React from "react";
import { Boxes, GitBranch, Route, ShieldCheck, Workflow } from "lucide-react";

type IconComponent = React.ComponentType<{ className?: string }>;

/* ── Flight levels ─────────────────────────────────────────────── */

export const FLIGHT_LEVELS = [
  { level: "L0", label: "Value proposition", desc: "Root customer goal. Authored by product-owner. Fulfilled when all children are done.", accent: "150 64% 56%" },
  { level: "L1", label: "Feature benefit", desc: "Concrete sub-goal. Also composite — fulfilled by L2/L3 children.", accent: "150 64% 56%" },
  { level: "L2", label: "Testable behaviour", desc: "Given/When/Then Gherkin rule. A leaf — the scanner turns it into a ticket.", accent: "168 60% 46%" },
  { level: "L3", label: "Edge-case spec", desc: "Failure mode or boundary condition. Also a leaf — becomes a ticket.", accent: "168 60% 46%" },
] as const;

/* ── Readiness lifecycle ──────────────────────────────────────── */

export const READINESS = [
  { state: "draft",    label: "Draft",    desc: "Authored by PO or BA. Scanner ignores it.", colorClass: "text-muted-foreground" },
  { state: "reviewed", label: "Reviewed", desc: "Enriched by it-po. Still ignored by scanner.", colorClass: "text-warning" },
  { state: "approved", label: "Approved", desc: "Set by you. The scanner picks this up — gates ticket generation.", colorClass: "text-success" },
] as const;

/* ── Ticket lifecycle folders ─────────────────────────────────── */

export const TICKET_FOLDERS = [
  { folder: "00_inbox/", label: "Inbox",    desc: "Proposed work awaiting a drive. Epics live in sub-folders." },
  { folder: "01_todo/",  label: "In-flight", desc: "Actively being driven — one git worktree per epic." },
  { folder: "99_done/",  label: "Archived", desc: "Completed epics and single tickets, fully signed off." },
  { folder: "99_rejected/", label: "Rejected", desc: "Decided-against work kept for context and history." },
] as const;

/* ── Gate catalog ─────────────────────────────────────────────── */

export const GATES = [
  { name: "Sign-off three-place parity",    desc: "An agent must atomically flip: frontmatter status, Sign-offs checkbox (em-dash + timestamp), and all its Implementation Tasks." },
  { name: "Test-first TDD",                 desc: "test-writer runs at priority 5, before any coder. It writes failing tests; coders make them green. check-contract-shrinking blocks weakening tests at commit time." },
  { name: "Commit Guardian hooks",          desc: "~20 pre-commit hooks: AC schema, governance write-locks, contract-shrinking, error handling (E722/BLE001/TRY), docs integrity, quality gates (cyclomatic ≤ 15), build-drift." },
  { name: "PR-only main + Ruff CI",         desc: "Direct push to main is rejected. Ruff (E722, BLE001, TRY + lint) is the required CI gate." },
  { name: "/finalize-feature HALT steps",   desc: "Merging origin/main halts on conflict. Post-merge test regression halts the finalize. PR merge is confirmation-gated." },
] as const;

/* ── Cross-links to live views ────────────────────────────────── */

export const CROSS_LINKS: { href: string; label: string; icon: IconComponent; desc: string }[] = [
  { href: "/pipeline",     label: "Pipeline",     icon: Workflow,    desc: "The four-stage flow, live agent roster, and real phase chains on completed tickets." },
  { href: "/flows",        label: "Flows",        icon: Route,       desc: "The product-truth layer: flows, mock data, and mockups — coloured by build status." },
  { href: "/coverage",     label: "Coverage",     icon: ShieldCheck, desc: "How many tests guard each acceptance criterion, live from the repo." },
  { href: "/architecture", label: "Architecture", icon: Boxes,       desc: "Every code component clustered by architectural role, cross-linked to the AC store." },
  { href: "/atlas",        label: "AC Atlas",     icon: GitBranch,   desc: "How acceptance criteria connect: the graph of depends_on and covered_by edges." },
];

/* ── Code specimens ───────────────────────────────────────────── */

export const AC_YAML = `id: ACD-1100b-3-i
components:
  - ac-driven-dev
readiness: approved    # draft | reviewed | approved — gates ticket generation
priority: high         # critical | high | medium | low
title: "Edge case: no agent carries any version suffix"
component: ac-driven-dev
level: L3              # L0/L1 = composite goals; L2/L3 = leaf (become tickets)
status: active
criteria: |            # Gherkin Given/When/Then — BA-owned, write-locked at commit
  Given the registry contains entries with no version suffix
  When the scanner processes the registry
  Then it returns an empty suffix list without error
depends_on:
  - ACD-1100b-3
assigned_agent: python-coder   # IT-PO enrichment
estimated_complexity: S        # S | M | L | XL
delivers_to: null
expects_from:
  ac_id: ACD-1100b-3
  contract: "parent AC provides the registry fixture"
origin_agent: BrainCandy
created: 2026-06-05
implemented_by: []             # written by /build-ac on ticket generation`;

export const TICKET_FRONTMATTER = `advances_current_outcome: true
agents:                 # phase-agent status map — supervisor drives on this
  commit: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  pull-request: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  test-writer: needed
components:
  - ac-driven-dev
created: '2026-06-10'
depends_on:
  - ACD-1100b-3        # sibling AC id — drives parallel-safety batching
files_touched:
  - docs/reference/agent-template-frontmatter.md
priority: high
requires_adr: false
requires_diagram: false
roadmap_phase: phase_1
source_ac: ACD-1100b-3-i   # back-link to the AC that generated this ticket
status: todo               # todo | in_progress | blocked | done | deferred
title: 'Edge case: no agent in registry carries any version suffix'`;
