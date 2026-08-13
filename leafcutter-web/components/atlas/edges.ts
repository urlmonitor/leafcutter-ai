/**
 * Edge-kind visual vocabulary for the AC subgraph. One place that maps a
 * GraphEdgeKind to its stroke colour / dash / label so the canvas and the
 * legend never drift apart.
 */
import type { GraphEdgeKind } from "@/lib/data/types";

export interface EdgeStyleSpec {
  label: string;
  hsl: string;
  dashed: boolean;
}

export const EDGE_STYLES: Record<string, EdgeStyleSpec> = {
  depends_on: { label: "depends on", hsl: "150 64% 52%", dashed: false },
  delivers_to: { label: "delivers to", hsl: "168 60% 46%", dashed: true },
  expects_from: { label: "expects from", hsl: "200 78% 60%", dashed: true },
  covers: { label: "covers", hsl: "150 8% 52%", dashed: true },
  implements: { label: "implements", hsl: "265 60% 66%", dashed: true },
  member_of: { label: "member of", hsl: "150 8% 52%", dashed: true },
  flow: { label: "flow", hsl: "38 92% 58%", dashed: false },
};

export function edgeStyle(kind: GraphEdgeKind): EdgeStyleSpec {
  return EDGE_STYLES[kind] ?? EDGE_STYLES.depends_on;
}

/** Edge kinds that actually appear in the AC subgraph, for the legend. */
export const AC_EDGE_LEGEND: GraphEdgeKind[] = [
  "depends_on",
  "delivers_to",
  "expects_from",
  "covers",
];

/**
 * Trust rendering for the artifact knowledge-graph view.
 *
 * The authored JSON defines TWO orthogonal trust axes and an explicit rule:
 *   "A link is ingestable as-is only when it is enforced/derived-validated
 *    AND clean."
 * An earlier version keyed colour on `enforcement` alone, which drew the two
 * enforced-but-AMBIGUOUS edges (`depends_on`, `covered_by`-parent) as maximally
 * trustworthy — precisely the edges the reference doc calls traps. Colour now
 * encodes the RULE's verdict, so the strongest visual signal can never land on
 * an edge that needs partitioning first.
 *
 *   colour  = ingestability (the reader's actual ternary decision)
 *   dash    = derived (machine-generated), orthogonal to trust
 *   warnGlyph = the shape caveat that no line property can express
 *
 * Hues deliberately avoid the node-group palette (see ARTIFACT_GROUP_HSL in
 * flow-nodes.tsx): a hue must not mean both "ac-core" and "enforced".
 */
/**
 * Node-family palette for the artifact graph. Lives here (not in the node
 * component) so both the React renderer and the canvas PNG exporter read ONE
 * definition — they previously kept drifting copies.
 *
 * Deliberately DESATURATED: family is already encoded spatially and by the
 * group chip, so the vivid end of the spectrum is reserved for edge trust
 * below. No family hue may collide with a trust hue.
 */
export const ARTIFACT_GROUP_HSL: Record<string, string> = {
  "ac-core": "199 42% 62%",    // muted steel blue
  "prod-truth": "258 34% 68%", // muted violet
  meta: "322 28% 66%",         // muted rose
  delivery: "28 30% 62%",      // muted clay
};

export const ARTIFACT_GROUP_LABEL: Record<string, string> = {
  "ac-core": "AC Core",
  "prod-truth": "Prod Truth",
  meta: "Meta",
  delivery: "Delivery",
};

export type Ingestability = "ingestable" | "reconcile" | "untrusted";

export interface ArtifactEdgeSpec extends EdgeStyleSpec {
  ingestability: Ingestability;
  /** Marker for an ambiguous / freetext / often-empty value shape. */
  warnGlyph: string | null;
}

const INGESTABLE_HSL = "142 70% 55%"; // green  — ingest as-is
const RECONCILE_HSL = "34 95% 62%";   // amber  — needs preprocessing
const UNTRUSTED_HSL = "220 9% 62%";   // grey   — do not rely on

/** Enforcement values that guarantee the link at commit time. */
const STRONG_ENFORCEMENT = new Set(["enforced", "derived-validated"]);
/** Value shapes that require partitioning/resolution before ingestion. */
const CAVEAT_SHAPE: Record<string, string> = {
  ambiguous: "⚠",
  freetext: "~",
  "often-empty": "∅",
};

/**
 * Resolve an artifact edge's visual spec from BOTH trust axes.
 *
 * @param enforcement e.g. "enforced" | "warn" | "none" | "derived-validated"
 * @param shape       e.g. "clean" | "ambiguous" | "freetext" | "derived"
 */
export function artifactEdgeStyle(
  enforcement: string,
  shape: string = "clean",
): ArtifactEdgeSpec {
  const strong = STRONG_ENFORCEMENT.has(enforcement);
  const clean = shape === "clean" || shape === "derived";
  const warnGlyph = CAVEAT_SHAPE[shape] ?? null;
  const derived = enforcement === "derived-validated" || enforcement === "derived-raw";

  // The store's own ingestable_rule, applied verbatim.
  const ingestability: Ingestability = strong && clean
    ? "ingestable"
    : strong || enforcement === "warn"
      ? "reconcile"
      : "untrusted";

  const hsl =
    ingestability === "ingestable"
      ? INGESTABLE_HSL
      : ingestability === "reconcile"
        ? RECONCILE_HSL
        : UNTRUSTED_HSL;

  return {
    label: `${enforcement} · ${shape}`,
    hsl,
    dashed: derived || ingestability === "untrusted",
    ingestability,
    warnGlyph,
  };
}

/** Legend rows for the three-value ingestability scale. */
export const INGESTABILITY_LEGEND: {
  key: Ingestability;
  label: string;
  hsl: string;
  hint: string;
}[] = [
  { key: "ingestable", label: "Ingest as-is", hsl: INGESTABLE_HSL, hint: "enforced/derived-validated AND clean" },
  { key: "reconcile", label: "Reconcile first", hsl: RECONCILE_HSL, hint: "enforced but ambiguous, or warn-only" },
  { key: "untrusted", label: "Do not rely on", hsl: UNTRUSTED_HSL, hint: "no enforcement" },
];
