/**
 * Canonical data types for the Leafcutter Atlas.
 * These mirror the on-disk artifacts in the leafcutter-ai repo:
 *   - AC store:     docs/acceptance-criteria/<component>/**.yaml
 *   - tickets:      tickets/**.md  (YAML frontmatter + markdown body)
 *   - components:   docs/components.json
 *   - roadmap:      docs/roadmap.json
 *   - agents:       config/agent_registry.json
 *
 * All view components consume THESE types via the loaders in lib/data/*.
 * Loaders are defensive: unknown/missing fields degrade to sensible defaults,
 * never throw on a single malformed file.
 */

export type AcLevel = "L0" | "L1" | "L2" | "L3";
export type WorkStatus =
  | "done"
  | "in_progress"
  | "todo"
  | "blocked"
  | "not_started"
  | "unknown";
export type Readiness = "draft" | "reviewed" | "approved" | "unknown";
export type Priority = "critical" | "high" | "medium" | "low" | "unknown";
export type Complexity = "S" | "M" | "L" | "XL" | "unknown";

/** One acceptance criterion, normalized from a single YAML file. */
export interface AC {
  id: string;
  title: string;
  component: string;          // AC-store namespace id (kebab), e.g. "build_pipeline"
  level: AcLevel;
  status: string;             // active | deprecated | ...
  reqStatus: string;          // req_status
  workStatus: WorkStatus;     // normalized work_status
  workStatusRaw: string;      // original string for display
  readiness: Readiness;
  priority: Priority;
  complexity: Complexity;
  criteria: string;           // Gherkin text
  dependsOn: string[];        // AC ids this depends on
  deliversTo: string | null;  // downstream AC id (contract)
  expectsFrom: { id: string; reason: string }[]; // upstream contracts
  docLinks: string[];
  assignedAgent: string | null;
  itRequirements: string;
  originAgent: string | null;
  created: string | null;
  createdByTicket: string | null;
  amendedBy: string[];
  supersededBy: string | null;
  coveredBy: string[];        // child AC ids
  implementedBy: string[];    // ticket paths / commits
  changeTarget: string | null;
  riskSurface: string | null;
  implementsPattern: string | null;
  filePath: string;           // repo-relative path to the source YAML

  // ---- Enriched by getAtlas() (undefined if an AC is used raw from loadAcs) ----
  isLeaf?: boolean;           // false = composite parent (completion derived from children)
  testCount?: number;         // # tests DIRECTLY guarding this AC (id named in a test file, etc.)
  testRefs?: string[];        // the guarding test files/nodes
  testRolledUpCount?: number; // tests on this AC + all descendant ACs (for composites)
  bucket?: BacklogBucket;     // honest backlog classification
  blockedBy?: string[];       // unfinished dependency AC ids (when bucket === "blocked")
  derivedDone?: boolean;      // composites only: all in-store children are done
}

/**
 * Honest backlog classification for a not-done AC. Mutually exclusive.
 * Explains WHY the raw "todo" count is not the buildable backlog.
 */
export type BacklogBucket =
  | "done"            // work_status done
  | "superseded"      // status != active or superseded_by set — dead
  | "composite"       // parent roll-up; completion derived from children, not built directly
  | "built_unflipped" // leaf; implemented_by resolves to real source or a done ticket — stale status
  | "draft"           // leaf; readiness draft — not real backlog yet
  | "untriaged"       // leaf; readiness missing — needs triage
  | "blocked"         // leaf; triaged but has unfinished dependencies
  | "ready";          // leaf; triaged, unblocked, todo — genuinely buildable now

/** One AC-store component namespace, from index.yaml. */
export interface AcComponent {
  id: string;
  prefix: string;
  description: string;
  owner: string | null;
  directoryPatterns: string[];
}

/** A ticket parsed from tickets/**.md. */
export interface Ticket {
  slug: string;               // filename without extension
  title: string;
  status: string;             // done | in_progress | ... (frontmatter authoritative)
  lifecycle: "inbox" | "done" | "epic" | "other";
  epic: string | null;        // EPIC-Name if under an epic folder
  components: string[];
  created: string | null;
  dependsOn: string[];
  priority: Priority;
  roadmapPhase: string | null;
  advancesOutcome: boolean;
  requiresDiagram: boolean;
  requiresAdr: boolean;
  filesTouched: string[];
  agents: { name: string; status: string }[];
  acTraceability: { l0: string[]; l1: string[]; l2: string[]; l3: string[]; acPath: string | null } | null;
  filePath: string;           // repo-relative path
}

/** A code/architecture component from components.json. */
export interface Component {
  id: string;
  name: string;
  type: string;               // orchestration | infrastructure | coding | analysis | ...
  description: string;
  detailRef: string | null;   // arch-doc path
  status: string;
  primaryCode: string[];
}

export interface RoadmapPhase {
  id: string;
  title: string;
  status: string;             // active | planned | done
  description: string;
  exitCriteria: string[];
  ticketsAdvancingOutcome: string[];
}

export interface Roadmap {
  currentPhase: string;
  currentOutcome: string;
  phases: RoadmapPhase[];
}

/** A phase/supervisor agent from the registry, normalized for display. */
export interface AgentDef {
  id: string;
  name: string;
  category: string | null;    // implementation | planning | testing | research | supervisor | ...
  tier: string | null;        // phase | supervisor | utility
  role: string | null;        // orchestration | coding | review | ...
  description: string;
  isTicketPhase: boolean;
  model: string | null;
  produces: string | null;
  spawnAllowlist: string[];   // agent ids this one may spawn (topology edges)
  spawnedBy: string[];        // who dispatches this one
  skillsUsed: string[];
  deprecated: boolean;
}

/* ---------- Graph model (shared by AC Atlas & Architecture views) ---------- */

export type GraphNodeKind = "ac" | "component" | "ticket" | "phase" | "agent";
export type GraphEdgeKind =
  | "depends_on"      // AC -> AC (or ticket -> ticket)
  | "delivers_to"     // AC -> AC contract
  | "expects_from"    // AC -> AC contract
  | "covers"          // parent AC -> child AC (covered_by)
  | "implements"      // ticket -> AC
  | "member_of"       // AC/ticket -> component
  | "flow";           // pipeline sequence

export interface GraphNode {
  id: string;
  kind: GraphNodeKind;
  label: string;
  group: string;              // component id / phase group — for clustering & color
  status?: WorkStatus;
  level?: AcLevel;
  priority?: Priority;
  meta?: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  kind: GraphEdgeKind;
  weight?: number;            // used by rollup graphs (cross-component dep count)
}

export interface Graph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

/* ---------- Product-truth flows ---------- */

/** One field of a mock-data entity (name + its human/type spec string). */
export interface MockField {
  name: string;
  spec: string;               // e.g. "number — in euros"
}

/** One entity from a *.mock.json file: its field specs and concrete records. */
export interface MockEntity {
  name: string;               // "Plant" | "Customer" | "Order" | ...
  fields: MockField[];
  records: Record<string, unknown>[];
}

/** A parsed mock-data artifact (docs/product-truth/mock-data/**.mock.json). */
export interface MockData {
  id: string;                 // e.g. "fern-and-fig/catalog"
  component: string;
  entities: MockEntity[];
  filePath: string;           // repo-relative path
}

/** A resolved reference from a flow step to one of its acceptance criteria. */
export interface AcRef {
  id: string;
  title: string;
  level: AcLevel;
  workStatus: WorkStatus;     // LIVE status pulled from the AC store
  resolved: boolean;          // false = the AC id did not resolve in the store
}

/** Rolled-up implementation counts for a flow (derived from live AC status). */
export interface FlowImplSummary {
  done: number;
  in_progress: number;
  not_started: number;
  total: number;
  asof: string | null;
}

/** One acceptance scenario attached to a flow step (Gherkin-ish). */
export interface FlowScenario {
  for: string;                // step / branch id this scenario covers
  given: string;
  when: string;
  then: string;
}

/** One step in a product-truth flow. */
export interface FlowStep {
  id: string;
  label: string;
  human: string;              // plain-language description
  order: number;
  screen: string | null;
  reads: string[];            // entity names read
  writes: string[];           // entity names written
  implements: string[];       // AC ids
  implStatus: WorkStatus;     // DERIVED from the live AC status (done|in_progress|not_started)
  fallbackStatus: WorkStatus; // the flow's own impl_status (used when an AC id doesn't resolve)
  acs: AcRef[];               // resolved AC references (id + live status)
}

/** A conditional branch off a flow step (e.g. out-of-stock path). */
export interface FlowBranch {
  id: string;
  from: string;               // step id this branches from
  condition: string;
  label: string;
  human: string;
  screen: string | null;
  reads: string[];
  writes: string[];
  implements: string[];
  implStatus: WorkStatus;
  fallbackStatus: WorkStatus;
  acs: AcRef[];
}

/** The nature of a flow: an end-user journey, a data pipeline, or architecture. */
export type FlowKind = "user" | "data" | "architecture";
/** Whether a flow is backed by mock data or a real (process/architecture) surface. */
export type FlowSource = "mock" | "real";

/** A product-truth flow (docs/product-truth/flows/**.flow.json). */
export interface Flow {
  id: string;
  component: string;
  product: string | null;
  name: string;
  summary: string;
  kind: FlowKind;
  source: FlowSource;
  status: string;
  readiness: string;
  entities: string[];
  mockDataRef: string | null;
  steps: FlowStep[];
  branches: FlowBranch[];
  scenarios: FlowScenario[];
  implSummary: FlowImplSummary; // derived from live AC status
  filePath: string;
}

/** One place an AC appears in a flow — for the reverse "Appears in flows" index. */
export interface FlowAppearance {
  flowId: string;
  flowName: string;
  stepId: string;
  stepLabel: string;
}

/* ---------- Agent prompt inspector (Pipeline view) ---------- */

/** One declared input slot from an agent template's `inputs:` frontmatter. */
export interface PromptSlot {
  name: string;
  type: string;
  required: boolean;
  description: string;
}

/** One `pre_flight_reads:` entry — a file/dir the agent reads at flight time. */
export interface PromptPreFlightRead {
  source: string;
  required: boolean;
  condition: string | null;
}

/** One `config_keys:` entry — a skills_config.json value the agent consumes. */
export interface PromptConfigKey {
  key: string;
  required: boolean;
  description: string;
}

/** One `skills_used:` entry — a skill the agent is allowed to load, + rationale. */
export interface PromptSkill {
  name: string;
  note: string;                 // inline rationale comment from the template, if any
}

/**
 * A parsed agent template (templates/agents/<id>.md): its frontmatter contract
 * plus the markdown body, which IS the agent's system prompt.
 */
export interface AgentTemplate {
  id: string;
  name: string;
  model: string | null;
  produces: string | null;
  signoff: boolean;
  tools: string[];
  description: string;
  systemPrompt: string;         // the markdown body verbatim
  inputs: PromptSlot[];
  preFlightReads: PromptPreFlightRead[];
  configKeys: PromptConfigKey[];
  skills: PromptSkill[];
}

/** A trimmed AC used as an example when rendering a prompt. */
export interface PromptExampleAc {
  id: string;
  title: string;
  level: string;
  component: string;
  criteria: string;
  priority: string;
  complexity: string;
  itRequirements: string;
  assignedAgent: string | null;
  dependsOn: string[];
  readiness: string;
  workStatus: string;
}

/** A trimmed ticket used as an example when rendering a prompt. */
export interface PromptExampleTicket {
  slug: string;
  path: string;                 // repo-relative ticket path (fills ticket_path slots)
  title: string;
  epic: string | null;
  components: string[];
  filesTouched: string[];
  testRequirements: string;
}

/** The concrete values a single example provides to fill prompt slots. */
export interface PromptExampleBundle {
  label: string;
  ac: PromptExampleAc | null;
  ticket: PromptExampleTicket | null;
  userRequest: string;
  config: Record<string, string>;
}

/**
 * A named example (mock or real). `shared` fills every agent's prompt; `perAgent`
 * holds optional overrides — the target is one authored bundle per agent.
 */
export interface PromptExample {
  id: string;
  label: string;
  source: FlowSource;           // "mock" | "real"
  shared: PromptExampleBundle;
  perAgent: Record<string, Partial<PromptExampleBundle>>;
}

/** One resolved input row for the Inputs view. */
export interface ResolvedInput {
  kind: "input" | "pre_flight" | "config";
  name: string;
  detail: string;               // slot type / condition / "config key"
  required: boolean;
  value: string;                // resolved display value, or an "(unresolved)" marker
  resolved: boolean;
}

/* ---------- Aggregate snapshot ---------- */

export interface Counts {
  total: number;
  byStatus: Record<string, number>;
  byLevel: Record<string, number>;
  byPriority: Record<string, number>;
  byReadiness: Record<string, number>;
  byComponent: Record<string, number>;
}

/** Test-coverage rollup across the whole store. */
export interface CoverageStats {
  totalAcs: number;
  guarded: number;              // ACs with >=1 direct guarding test
  guardedPct: number;
  rolledUpGuarded: number;      // ACs guarded directly OR via a descendant
  histogram: { bucket: string; count: number }[]; // "0","1","2","3+"
  byLevel: { level: AcLevel; total: number; guarded: number }[];
  byComponent: { component: string; total: number; guarded: number }[];
  totalTestFiles: number;
}

/** Bidirectional AC⇄test⇄code traceability health. */
export interface TraceabilityHealth {
  // Guard coverage over the LOGICAL denominator (shipped work), not all ACs.
  doneGuard: {
    total: number; guarded: number; unguarded: number; pct: number;
    leafTotal: number; leafGuarded: number; leafUnguarded: number; leafPct: number;
  };
  // Tests that reference no acceptance criterion (untraceable to a requirement).
  orphanTests: {
    files: number; linkedFiles: number; orphanFiles: number; orphanFilePct: number;
    orphanFileSamples: string[];
    fns: number; linkedFns: number; orphanFns: number; orphanFnPct: number;
  };
  // Source functions/classes in files no AC links to. Two scopes ("the code" is ambiguous).
  untracedCode: {
    scopes: {
      key: string; label: string;
      files: number; linkedFiles: number; untracedFiles: number; untracedFilePct: number;
      symbols: number; symbolsInUntraced: number; symbolsUntracedPct: number;
      topUntraced: { path: string; symbols: number }[];
    }[];
  };
  ticketsWithTraceability: number;   // tickets carrying ac_traceability
  ticketsTotal: number;
}

/** One row of the honest backlog waterfall (raw todo -> genuinely ready). */
export interface BacklogWaterfall {
  bucket: BacklogBucket | "not_done";
  label: string;
  count: number;
  description: string;
}

/** A ticket actively in flight, with its phase-agent chain. */
export interface ActivityItem {
  ticket: Ticket;
  activePhases: string[];       // agents still `needed`
  failedPhases: string[];       // agents `failed`
  donePhases: string[];         // agents `signed_off`
  sourceAcs: string[];          // ACs this ticket traces to
}

export interface AtlasSnapshot {
  generatedAt: string;
  acs: AC[];                    // enriched (isLeaf, testCount, bucket, …)
  acComponents: AcComponent[];
  tickets: Ticket[];
  components: Component[];
  roadmap: Roadmap;
  agents: AgentDef[];
  acCounts: Counts;
  ticketCounts: {
    total: number;
    byStatus: Record<string, number>;
    byLifecycle: Record<string, number>;
  };
  // ---- Phase-2 intelligence ----
  backlog: {
    byBucket: Record<BacklogBucket, number>;
    waterfall: BacklogWaterfall[];
    buildableLeaves: number;    // ready + blocked (real leaf backlog, triaged)
  };
  nextUp: AC[];                 // the TRUE /build-ac queue: eligible + ranked
  builtUnflipped: AC[];         // built (real source / done ticket) but still not "done"
  coverage: CoverageStats;
  traceability: TraceabilityHealth;
  activity: {
    inProgress: ActivityItem[];     // in-progress LEAF tickets with a live phase chain
    inFlightEpics: Ticket[];        // in-progress epic Master_Plan markers (may be stale)
    telemetryAvailable: boolean;    // is there an agent_telemetry.jsonl with data?
  };
}
