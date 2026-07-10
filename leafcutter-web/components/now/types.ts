/**
 * Lean, serializable view-models for the /now ("Now & Next") view.
 * The server page (app/now/page.tsx) maps the rich AtlasSnapshot slices down to
 * these shapes so the client components receive only what they render — no giant
 * Gherkin `criteria` strings or full Ticket objects cross the server→client wire.
 */

/** One phase agent in a ticket's live chain, collapsed to a display status. */
export type PhaseLiteStatus = "signed_off" | "needed" | "failed";

export interface PhaseLite {
  name: string;
  status: PhaseLiteStatus;
}

/** A leaf ticket that is mid-build right now. */
export interface FlightItem {
  slug: string;
  title: string;
  epic: string | null;
  phases: PhaseLite[];
  filesTouched: number;
  sourceAcs: string[];
}

/** An epic-level in-progress marker (Master_Plan) — coarse and possibly stale. */
export interface EpicLite {
  slug: string;
  title: string;
  epic: string | null;
}

/** One entry of the true /build-ac queue. */
export interface NextItem {
  id: string;
  title: string;
  component: string;
  complexity: string;
}

/** One row of the honest backlog waterfall. */
export interface WaterfallRow {
  bucket: string;
  label: string;
  count: number;
  description: string;
}

/** An AC that was built but whose work_status was never flipped to done. */
export interface BuiltItem {
  id: string;
  title: string;
  component: string;
  implementedBy: string[];
}
