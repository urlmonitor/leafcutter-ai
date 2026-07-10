import "server-only";
import matter from "gray-matter";
import { repoPath, readFileSafe } from "./repo";
import { loadAcs, acById } from "./ac-store";
import { loadTickets } from "./tickets";
import { computeNextUp } from "./backlog";
import type {
  AC,
  AgentTemplate,
  PromptConfigKey,
  PromptExample,
  PromptExampleAc,
  PromptExampleBundle,
  PromptExampleTicket,
  PromptPreFlightRead,
  PromptSkill,
  PromptSlot,
  Ticket,
} from "./types";

const AGENTS_DIR = "templates/agents";
/** Where the hand-authored mock example artifact lives (Flows mock-data family). */
const MOCK_EXAMPLE = "docs/product-truth/mock-data/pipeline-prompts/report-export.prompt.json";

function asArray(v: unknown): string[] {
  if (Array.isArray(v)) return v.map((x) => String(x)).filter(Boolean);
  if (v == null || v === "") return [];
  return [String(v)];
}

/** Parse a comma-or-list `tools:` value into a clean string array. */
function parseTools(v: unknown): string[] {
  if (Array.isArray(v)) return v.map((x) => String(x).trim()).filter(Boolean);
  if (typeof v === "string") {
    // Strip any trailing inline comment (e.g. "Read, Write  # scoped to …").
    return v
      .split("#")[0]
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }
  return [];
}

function parseSlots(v: unknown): PromptSlot[] {
  if (!Array.isArray(v)) return [];
  return v
    .map((s) => {
      const o = (s ?? {}) as Record<string, unknown>;
      return {
        name: String(o.name ?? ""),
        type: String(o.type ?? "string"),
        required: Boolean(o.required),
        description: String(o.description ?? ""),
      };
    })
    .filter((s) => s.name);
}

function parsePreFlight(v: unknown): PromptPreFlightRead[] {
  if (!Array.isArray(v)) return [];
  return v
    .map((s) => {
      const o = (s ?? {}) as Record<string, unknown>;
      return {
        source: String(o.source ?? ""),
        required: Boolean(o.required),
        condition: o.condition ? String(o.condition) : null,
      };
    })
    .filter((s) => s.source);
}

/**
 * Parse the `skills_used:` list. Names come from the parsed YAML (authoritative);
 * the inline `# rationale` comment after each block-style list item is recovered
 * by scanning the raw frontmatter, since the YAML parser discards comments.
 */
function parseSkills(raw: string, fm: Record<string, unknown>): PromptSkill[] {
  const names = asArray(fm.skills_used);
  if (names.length === 0) return [];
  const notes: Record<string, string> = {};
  const fmMatch = raw.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (fmMatch) {
    let inSkills = false;
    for (const line of fmMatch[1].split("\n")) {
      if (/^skills_used\s*:/.test(line)) {
        inSkills = true;
        continue;
      }
      if (inSkills) {
        // A new top-level key (unindented, not a list item) ends the block.
        if (/^\S/.test(line) && !/^\s*-/.test(line)) break;
        const m = line.match(/^\s*-\s*([^\s#]+)\s*(?:#\s*(.*))?$/);
        if (m) notes[m[1]] = (m[2] ?? "").trim();
      }
    }
  }
  return names.map((name) => ({ name, note: notes[name] ?? "" }));
}

function parseConfigKeys(v: unknown): PromptConfigKey[] {
  if (!v || typeof v !== "object" || Array.isArray(v)) return [];
  return Object.entries(v as Record<string, unknown>).map(([key, body]) => {
    const o = (body ?? {}) as Record<string, unknown>;
    return {
      key,
      required: Boolean(o.required),
      description: String(o.description ?? ""),
    };
  });
}

const _templateCache = new Map<string, AgentTemplate | null>();

/**
 * Load a single agent template (templates/agents/<id>.md), parsing its
 * frontmatter contract + markdown body (the system prompt). Returns null when
 * the file is absent (e.g. worktree-agent has no template) — never throws.
 */
export function loadAgentTemplate(id: string): AgentTemplate | null {
  if (_templateCache.has(id)) return _templateCache.get(id) ?? null;
  const raw = readFileSafe(repoPath(AGENTS_DIR, `${id}.md`));
  if (!raw) {
    _templateCache.set(id, null);
    return null;
  }
  let parsed: matter.GrayMatterFile<string>;
  try {
    parsed = matter(raw);
  } catch {
    _templateCache.set(id, null);
    return null;
  }
  const fm = parsed.data as Record<string, unknown>;
  const tpl: AgentTemplate = {
    id,
    name: String(fm.name ?? id),
    model: fm.model ? String(fm.model) : null,
    produces: fm.produces ? String(fm.produces) : null,
    signoff: Boolean(fm.signoff),
    tools: parseTools(fm.tools),
    description: String(fm.description ?? "").trim(),
    systemPrompt: parsed.content.trim(),
    inputs: parseSlots(fm.inputs),
    preFlightReads: parsePreFlight(fm.pre_flight_reads),
    configKeys: parseConfigKeys(fm.config_keys),
    skills: parseSkills(raw, fm),
  };
  _templateCache.set(id, tpl);
  return tpl;
}

/** Load templates for a set of agent ids as an id→template|null map. */
export function loadAgentTemplates(ids: string[]): Record<string, AgentTemplate | null> {
  const out: Record<string, AgentTemplate | null> = {};
  for (const id of ids) out[id] = loadAgentTemplate(id);
  return out;
}

/* ---------- Example bundles ---------- */

function acToExample(ac: AC): PromptExampleAc {
  return {
    id: ac.id,
    title: ac.title,
    level: ac.level,
    component: ac.component,
    criteria: ac.criteria,
    priority: ac.priority,
    complexity: ac.complexity,
    itRequirements: ac.itRequirements,
    assignedAgent: ac.assignedAgent,
    dependsOn: ac.dependsOn,
    readiness: ac.readiness,
    workStatus: ac.workStatus,
  };
}

function ticketToExample(t: Ticket): PromptExampleTicket {
  return {
    slug: t.slug,
    path: t.filePath,
    title: t.title,
    epic: t.epic,
    components: t.components,
    filesTouched: t.filesTouched,
    testRequirements: "",
  };
}

function parseExampleAc(v: unknown): PromptExampleAc | null {
  if (!v || typeof v !== "object") return null;
  const o = v as Record<string, unknown>;
  if (!o.id) return null;
  return {
    id: String(o.id),
    title: String(o.title ?? o.id),
    level: String(o.level ?? "L2"),
    component: String(o.component ?? ""),
    criteria: String(o.criteria ?? "").trim(),
    priority: String(o.priority ?? "medium"),
    complexity: String(o.complexity ?? "M"),
    itRequirements: String(o.it_requirements ?? "").trim(),
    assignedAgent: o.assigned_agent ? String(o.assigned_agent) : null,
    dependsOn: asArray(o.depends_on),
    readiness: String(o.readiness ?? "approved"),
    workStatus: String(o.work_status ?? "todo"),
  };
}

function parseExampleTicket(v: unknown): PromptExampleTicket | null {
  if (!v || typeof v !== "object") return null;
  const o = v as Record<string, unknown>;
  return {
    slug: String(o.slug ?? ""),
    path: String(o.path ?? ""),
    title: String(o.title ?? ""),
    epic: o.epic ? String(o.epic) : null,
    components: asArray(o.components),
    filesTouched: asArray(o.files_touched),
    testRequirements: String(o.test_requirements ?? "").trim(),
  };
}

function parseBundle(v: unknown, fallbackLabel: string): PromptExampleBundle {
  const o = (v ?? {}) as Record<string, unknown>;
  const cfg: Record<string, string> = {};
  if (o.config && typeof o.config === "object") {
    for (const [k, val] of Object.entries(o.config as Record<string, unknown>)) {
      cfg[k] = String(val ?? "");
    }
  }
  return {
    label: String(o.label ?? fallbackLabel),
    ac: parseExampleAc(o.ac),
    ticket: parseExampleTicket(o.ticket),
    userRequest: String(o.user_request ?? o.userRequest ?? "").trim(),
    config: cfg,
  };
}

let _mockCache: PromptExample | null = null;

/**
 * The hand-authored mock example. Editing the .prompt.json artifact retunes how
 * every agent's Mock prompt renders. Degrades to an empty example if absent.
 */
export function getPromptExample(): PromptExample {
  if (_mockCache) return _mockCache;
  const raw = readFileSafe(repoPath(MOCK_EXAMPLE));
  let doc: Record<string, unknown> = {};
  if (raw) {
    try {
      doc = JSON.parse(raw) as Record<string, unknown>;
    } catch {
      doc = {};
    }
  }
  const perAgent: Record<string, Partial<PromptExampleBundle>> = {};
  if (doc.perAgent && typeof doc.perAgent === "object") {
    for (const [id, body] of Object.entries(doc.perAgent as Record<string, unknown>)) {
      perAgent[id] = parseBundle(body, id);
    }
  }
  const example: PromptExample = {
    id: String(doc.id ?? "pipeline/prompt-example"),
    label: String(doc.label ?? "Mock example"),
    source: "mock",
    shared: parseBundle(doc.shared, "Mock example"),
    perAgent,
  };
  _mockCache = example;
  return example;
}

let _realCache: PromptExample | null = null;

/**
 * A representative REAL example, assembled live from the store: a genuinely
 * buildable AC (first of the /build-ac next-up queue, else first approved leaf),
 * a ticket that implements it (else the most recent ticket), and config values
 * from skills_config.json if present. Never throws.
 */
export function buildRealExample(): PromptExample {
  if (_realCache) return _realCache;
  const acs = loadAcs();
  const tickets = loadTickets();

  const nextUp = computeNextUp(acs, 5);
  const ac =
    nextUp[0] ??
    acs.find((a) => a.readiness === "approved" && a.workStatus !== "done") ??
    acs.find((a) => a.level === "L2") ??
    acs[0] ??
    null;

  // Prefer a ticket that references this AC; else the most recent ticket.
  let ticket: Ticket | null = null;
  if (ac) {
    ticket =
      tickets.find((t) => {
        const tr = t.acTraceability;
        if (!tr) return false;
        return [...tr.l0, ...tr.l1, ...tr.l2, ...tr.l3].includes(ac.id);
      }) ?? null;
  }
  if (!ticket) ticket = tickets[0] ?? null;

  const config = readSkillsConfig();

  const shared: PromptExampleBundle = {
    label: ac ? `Live AC ${ac.id}` : "Live store",
    ac: ac ? acToExample(ac) : null,
    ticket: ticket ? ticketToExample(ticket) : null,
    userRequest: ac ? ac.title : "",
    config,
  };

  const example: PromptExample = {
    id: "pipeline/real-example",
    label: shared.label,
    source: "real",
    shared,
    perAgent: {},
  };
  _realCache = example;
  return example;
}

/** Flatten a shallow skills_config.json into string-valued keys (best-effort). */
function readSkillsConfig(): Record<string, string> {
  const raw =
    readFileSafe(repoPath("skills_config.json")) ??
    readFileSafe(repoPath(".leafcutter", "skills_config.json"));
  if (!raw) return {};
  let doc: Record<string, unknown>;
  try {
    doc = JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return {};
  }
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(doc)) {
    if (v == null) continue;
    if (typeof v === "object") {
      for (const [k2, v2] of Object.entries(v as Record<string, unknown>)) {
        if (v2 != null && typeof v2 !== "object") out[`${k}.${k2}`] = String(v2);
      }
    } else {
      out[k] = String(v);
    }
  }
  return out;
}
