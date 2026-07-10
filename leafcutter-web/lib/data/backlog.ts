/**
 * Honest backlog classification + the TRUE "/build-ac" next-up queue.
 *
 * Why this exists: the raw "1687 todo" figure is not the buildable backlog.
 * Most of it is composite parent roll-ups (completion derived from children),
 * plus superseded/draft/untriaged records and a handful that were built but
 * never had their status flipped. This module reproduces the real pipeline's
 * eligibility + ranking so the site tells the truth.
 *
 * Pure (no fs / server-only): operates on already-loaded ACs + tickets.
 */
import type { AC, BacklogBucket, BacklogWaterfall, Ticket } from "./types";

const PRIORITY_ORDER: Record<string, number> = {
  critical: 0, high: 1, medium: 2, low: 3, unknown: 4,
};
// /build-ac derives priority purely from complexity, then sorts by file path.
const COMPLEXITY_TO_PRIORITY: Record<string, string> = {
  S: "high", M: "medium", L: "low", XL: "low", unknown: "low",
};

/** A covered_by entry that is a child AC id (not a test/file path). */
function isChildRef(entry: string): boolean {
  return /^[A-Z]{2,4}-\d/.test(entry) && !entry.includes("/") && !entry.endsWith(".py");
}

/** Leaf = no covered_by entry points at another AC. */
export function isLeafAc(ac: AC): boolean {
  return !ac.coveredBy.some(isChildRef);
}

/** An implemented_by ref that indicates REAL delivery (source file or a done ticket). */
function isBuiltRef(ref: string, doneTicketSlugs: Set<string>): boolean {
  const r = ref.trim();
  // A real source file under a code dir (not a generated ticket stub).
  if (/^(scripts|templates|leafcutter|config)\//.test(r) && /\.(py|js|ts|tsx|sql)$/.test(r)) {
    return true;
  }
  // A ticket reference whose ticket is actually done.
  if (/tickets\//.test(r) && r.endsWith(".md")) {
    const slug = r.split("/").pop()!.replace(/\.md$/, "");
    return doneTicketSlugs.has(slug);
  }
  return false;
}

export interface BacklogContext {
  doneAcIds: Set<string>;
  doneTicketSlugs: Set<string>;
}

export function buildContext(acs: AC[], tickets: Ticket[]): BacklogContext {
  return {
    doneAcIds: new Set(acs.filter((a) => a.workStatus === "done").map((a) => a.id)),
    doneTicketSlugs: new Set(
      tickets.filter((t) => t.status === "done" || t.lifecycle === "done").map((t) => t.slug),
    ),
  };
}

/** Direct dependencies that are not satisfied (not a known done AC). */
export function unfinishedDeps(ac: AC, ctx: BacklogContext): string[] {
  return ac.dependsOn.filter((d) => !ctx.doneAcIds.has(d));
}

/** Classify one AC into its honest backlog bucket. */
export function classify(ac: AC, ctx: BacklogContext): BacklogBucket {
  if (ac.workStatus === "done") return "done";
  if (ac.status !== "active" || ac.supersededBy) return "superseded";
  if (!isLeafAc(ac)) return "composite";
  // leaf, active, not done:
  if (ac.implementedBy.some((r) => isBuiltRef(r, ctx.doneTicketSlugs))) return "built_unflipped";
  if (ac.readiness === "draft") return "draft";
  if (ac.readiness === "unknown") return "untriaged";
  // triaged (reviewed | approved):
  if (unfinishedDeps(ac, ctx).length > 0) return "blocked";
  return "ready";
}

/**
 * The TRUE /build-ac queue: eligible leaves (active, todo, approved, unblocked),
 * ranked by complexity-derived priority then file path — exactly as the real
 * scanner + ac_prioritizer pick. Depends only on ACs (eligibility never consults
 * tickets), so it is safe to call standalone.
 */
export function computeNextUp(acs: AC[], limit?: number): AC[] {
  const doneAcIds = new Set(acs.filter((a) => a.workStatus === "done").map((a) => a.id));
  const eligible = acs.filter(
    (a) =>
      isLeafAc(a) &&
      a.status === "active" &&
      !a.supersededBy &&
      a.workStatus === "todo" &&
      a.readiness === "approved" &&
      a.dependsOn.every((d) => doneAcIds.has(d)),
  );
  eligible.sort((a, b) => {
    const pa = PRIORITY_ORDER[COMPLEXITY_TO_PRIORITY[a.complexity] ?? "low"];
    const pb = PRIORITY_ORDER[COMPLEXITY_TO_PRIORITY[b.complexity] ?? "low"];
    if (pa !== pb) return pa - pb;
    return a.filePath.localeCompare(b.filePath);
  });
  return typeof limit === "number" ? eligible.slice(0, limit) : eligible;
}

/**
 * Enrich ACs in place with isLeaf / bucket / blockedBy / derivedDone, and return
 * the aggregate backlog view + the true next-up queue + built-but-unflipped list.
 */
export function enrichBacklog(acs: AC[], tickets: Ticket[]) {
  const ctx = buildContext(acs, tickets);
  const byBucket: Record<BacklogBucket, number> = {
    done: 0, superseded: 0, composite: 0, built_unflipped: 0,
    draft: 0, untriaged: 0, blocked: 0, ready: 0,
  };

  for (const ac of acs) {
    ac.isLeaf = isLeafAc(ac);
    const bucket = classify(ac, ctx);
    ac.bucket = bucket;
    byBucket[bucket]++;
    if (bucket === "blocked") ac.blockedBy = unfinishedDeps(ac, ctx);
    if (!ac.isLeaf) {
      const kids = ac.coveredBy.filter(isChildRef);
      ac.derivedDone = kids.length > 0 && kids.every((k) => ctx.doneAcIds.has(k));
    }
  }

  // TRUE /build-ac queue: eligible leaves, ranked by complexity-derived priority then path.
  const nextUp = computeNextUp(acs);

  const builtUnflipped = acs
    .filter((a) => a.bucket === "built_unflipped")
    .sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true }));

  const notDone = acs.length - byBucket.done;
  const waterfall: BacklogWaterfall[] = [
    { bucket: "not_done", label: "Not marked done", count: notDone,
      description: "Every AC whose work_status is not 'done'." },
    { bucket: "composite", label: "− Composite parents", count: byBucket.composite,
      description: "Roll-up ACs; completion is derived from their children, not built directly." },
    { bucket: "superseded", label: "− Superseded", count: byBucket.superseded,
      description: "Replaced or inactive — dead, never to build." },
    { bucket: "built_unflipped", label: "− Built, not flipped", count: byBucket.built_unflipped,
      description: "Delivered (real source or a done ticket) but work_status never updated." },
    { bucket: "draft", label: "− Draft", count: byBucket.draft,
      description: "readiness: draft — not real backlog yet." },
    { bucket: "untriaged", label: "− Untriaged", count: byBucket.untriaged,
      description: "No readiness set — needs triage before it can be scheduled." },
    { bucket: "blocked", label: "− Blocked by dependencies", count: byBucket.blocked,
      description: "Triaged leaves waiting on unfinished prerequisite ACs." },
    { bucket: "ready", label: "= Genuinely ready to build", count: byBucket.ready,
      description: "Triaged, unblocked leaf ACs — the real buildable-now backlog." },
  ];

  return {
    byBucket,
    waterfall,
    buildableLeaves: byBucket.ready + byBucket.blocked,
    nextUp,
    builtUnflipped,
  };
}
