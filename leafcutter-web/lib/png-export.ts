/**
 * Dependency-free PNG export for the artifact knowledge graph.
 *
 * React Flow renders HTML nodes, so the usual approach is html-to-image — a
 * dependency this project does not carry (and npm installs are unreliable on
 * the WSL dev boxes). Instead we redraw the graph onto a canvas from the SAME
 * node positions React Flow is using, which means the export honours whatever
 * the user has dragged, is deterministic, and needs no third-party code.
 *
 * Two entry points: copy the PNG to the clipboard (for pasting into a chat)
 * and download it as a file (clipboard-image writes are Chromium-only).
 */

import {
  artifactEdgeStyle,
  INGESTABILITY_LEGEND,
  ARTIFACT_GROUP_HSL,
  ARTIFACT_GROUP_LABEL,
} from "@/components/atlas/edges";
import type { SelfRel } from "@/lib/data/types";

/** Minimal node shape the exporter needs. */
export interface PngNode {
  id: string;
  label: string;
  group: string;
  x: number;
  y: number;
  selfRels?: SelfRel[];
}

/** Minimal edge shape the exporter needs. */
export interface PngEdge {
  source: string;
  target: string;
  rel?: string;
  field?: string;
  enforcement?: string;
  shape?: string;
  /** "present" (default) | "absent" — a recorded gap, drawn as a missing link. */
  status?: string;
}

/** Provenance baked into the image so a shared PNG stands alone. */
export interface PngMeta {
  sourceDoc?: string;
  version?: number | string;
  nodeCount: number;
  edgeCount: number;
  selfCount: number;
}

const NODE_W = 200;
const NODE_H = 68;
const PAD = 90;
const TITLE_BAND = 62;
const LEGEND_H = 132;
const SCALE = 2; // retina-quality output

/** Rect used for label collision avoidance. */
interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

function overlaps(a: Rect, b: Rect): boolean {
  return a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
}

/** Point on a cubic bezier at parameter t — labels ride the real curve. */
function bezierPoint(
  t: number,
  p0: [number, number],
  p1: [number, number],
  p2: [number, number],
  p3: [number, number],
): [number, number] {
  const u = 1 - t;
  const a = u * u * u;
  const b = 3 * u * u * t;
  const c = 3 * u * t * t;
  const d = t * t * t;
  return [
    a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
    a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1],
  ];
}

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

/**
 * Draw the graph to an offscreen canvas and return it as a PNG blob.
 *
 * @param title Rendered top-left so a pasted image is self-identifying.
 */
export async function renderGraphPng(
  nodes: PngNode[],
  edges: PngEdge[],
  title: string,
  meta?: PngMeta,
): Promise<Blob> {
  if (nodes.length === 0) throw new Error("Nothing to export: the graph has no nodes.");

  const minX = Math.min(...nodes.map((n) => n.x));
  const minY = Math.min(...nodes.map((n) => n.y));
  const maxX = Math.max(...nodes.map((n) => n.x)) + NODE_W;
  const maxY = Math.max(...nodes.map((n) => n.y)) + NODE_H;

  // Bezier control points for a backward edge reach LEFT of the source node,
  // so sizing the canvas from node boxes alone clipped those curves off the
  // edge and left orphan arrow stubs. Reserve the deepest control-point
  // overhang on each side.
  let overhang = 0;
  const byId = new Map(nodes.map((n) => [n.id, n]));
  for (const e of edges) {
    const s = byId.get(e.source);
    const t = byId.get(e.target);
    if (!s || !t) continue;
    const dx = Math.max(40, Math.abs(t.x - (s.x + NODE_W)) * 0.45);
    overhang = Math.max(overhang, dx);
  }
  const sidePad = PAD + Math.min(overhang, 260);

  const width = maxX - minX + sidePad * 2;
  const height = maxY - minY + PAD * 2 + TITLE_BAND + LEGEND_H;

  const canvas = document.createElement("canvas");
  canvas.width = width * SCALE;
  canvas.height = height * SCALE;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas 2D context unavailable in this browser.");
  ctx.scale(SCALE, SCALE);

  // Background — matches the app's dark canvas so pasted images look native.
  ctx.fillStyle = "#0d1117";
  ctx.fillRect(0, 0, width, height);

  // ---------------- Title band + scope caption ----------------
  ctx.textBaseline = "top";
  ctx.fillStyle = "rgba(255,255,255,0.94)";
  ctx.font = "600 16px ui-sans-serif, system-ui, -apple-system, sans-serif";
  ctx.fillText(title, sidePad, 22);
  // Without this a viewer reasonably assumes the image shows live data.
  ctx.fillStyle = "rgba(190,205,215,0.62)";
  ctx.font = "500 10.5px ui-sans-serif, system-ui, sans-serif";
  ctx.fillText(
    "TYPE-level schema — nodes are artifact types, not instances. Labels name the field that encodes each edge.",
    sidePad,
    44,
  );

  // Translate so the graph's top-left sits below the title band.
  const ox = sidePad - minX;
  const oy = PAD - minY + TITLE_BAND;

  // Node rects, used both for drawing and for label collision avoidance.
  const nodeRects: Rect[] = nodes.map((n) => ({
    x: ox + n.x,
    y: oy + n.y,
    w: NODE_W,
    h: NODE_H,
  }));

  // -----------------------------------------------------------------
  // PASS 1 — curves only. Labels are deferred so they can never be
  // painted over by a later edge's stroke (this previously erased
  // TRACES_TO under TICKET_DEPENDS_ON).
  // -----------------------------------------------------------------
  interface PendingLabel {
    text: string;
    cx: number;
    cy: number;
    color: string;
  }
  const pending: PendingLabel[] = [];
  const pairSeen = new Map<string, number>();

  ctx.font = "600 9px ui-sans-serif, system-ui, sans-serif";
  for (const e of edges) {
    const s = byId.get(e.source);
    const t = byId.get(e.target);
    if (!s || !t) continue;

    const spec = artifactEdgeStyle(
      e.enforcement ?? "none",
      e.shape ?? "clean",
      e.status ?? "present",
    );
    const stroke = `hsl(${spec.hsl})`;

    const x1 = ox + s.x + NODE_W;
    const y1 = oy + s.y + NODE_H / 2;
    const x2 = ox + t.x;
    const y2 = oy + t.y + NODE_H / 2;

    // Separate coincident edges between the same pair by bowing each one more.
    const pairKey = [e.source, e.target].sort().join("::");
    const nth = pairSeen.get(pairKey) ?? 0;
    pairSeen.set(pairKey, nth + 1);
    const bow = nth * 26;

    const dx = Math.max(40, Math.abs(x2 - x1) * 0.45);
    const p0: [number, number] = [x1, y1];
    const p1: [number, number] = [x1 + dx, y1 - bow];
    const p2: [number, number] = [x2 - dx, y2 - bow];
    const p3: [number, number] = [x2, y2];

    ctx.strokeStyle = stroke;
    ctx.globalAlpha = spec.ingestability === "untrusted" ? 0.5 : 0.85;
    ctx.lineWidth = spec.ingestability === "ingestable" ? 1.6 : 1.2;
    // Mirror the canvas: an absent edge gets a long open dash so the gap
    // survives greyscale printing, where the red hue alone would not read.
    ctx.setLineDash(
      spec.ingestability === "absent" ? [2, 7] : spec.dashed ? [5, 4] : [],
    );
    ctx.beginPath();
    ctx.moveTo(p0[0], p0[1]);
    ctx.bezierCurveTo(p1[0], p1[1], p2[0], p2[1], p3[0], p3[1]);
    ctx.stroke();
    ctx.setLineDash([]);

    // Arrowhead at the target. The final control point shares the target's y
    // only when bow === 0; with a bow the curve still arrives near-horizontal,
    // so a fixed left-pointing triangle remains visually correct.
    ctx.fillStyle = stroke;
    ctx.beginPath();
    ctx.moveTo(x2, y2);
    ctx.lineTo(x2 - 7, y2 - 3.2);
    ctx.lineTo(x2 - 7, y2 + 3.2);
    ctx.closePath();
    ctx.fill();
    ctx.globalAlpha = 1;

    // Label rides the ACTUAL curve, not the straight-line midpoint — for any
    // edge spanning more than one column those differ substantially.
    const caption =
      spec.ingestability === "absent"
        ? `${spec.warnGlyph} ${e.rel ?? ""} — missing`
        : (e.field && e.field !== "—" ? e.field : e.rel ?? "") +
          (spec.warnGlyph ? ` ${spec.warnGlyph}` : "");
    if (caption) {
      const [cx, cy] = bezierPoint(0.5, p0, p1, p2, p3);
      pending.push({ text: caption, cx, cy, color: stroke });
    }
  }

  // -----------------------------------------------------------------
  // PASS 2 — labels, displaced so they clear node cards and each other.
  // -----------------------------------------------------------------
  const placed: Rect[] = [];
  ctx.font = "600 9px ui-sans-serif, system-ui, sans-serif";
  ctx.textBaseline = "middle";
  for (const lab of pending) {
    const w = ctx.measureText(lab.text).width;
    let rect: Rect = { x: lab.cx - w / 2 - 3, y: lab.cy - 6, w: w + 6, h: 12 };

    // Nudge vertically until clear of every card and previously-placed label.
    for (let attempt = 0; attempt < 14; attempt++) {
      const clash =
        nodeRects.some((r) => overlaps(rect, r)) || placed.some((r) => overlaps(rect, r));
      if (!clash) break;
      const dir = attempt % 2 === 0 ? 1 : -1;
      const step = Math.ceil((attempt + 1) / 2) * 13;
      rect = { ...rect, y: lab.cy - 6 + dir * step };
    }
    placed.push(rect);

    // Semi-transparent chip: residual overlap stays visible instead of
    // silently deleting whatever is underneath.
    ctx.fillStyle = "rgba(13,17,23,0.82)";
    ctx.fillRect(rect.x, rect.y, rect.w, rect.h);
    ctx.fillStyle = lab.color;
    ctx.globalAlpha = 0.95;
    ctx.fillText(lab.text, rect.x + 3, rect.y + rect.h / 2);
    ctx.globalAlpha = 1;
  }
  ctx.textBaseline = "top";

  // -----------------------------------------------------------------
  // Node cards
  // -----------------------------------------------------------------
  for (const n of nodes) {
    const x = ox + n.x;
    const y = oy + n.y;
    const accent = `hsl(${ARTIFACT_GROUP_HSL[n.group] ?? "220 9% 62%"})`;

    ctx.fillStyle = "rgba(22,29,33,0.96)";
    roundRect(ctx, x, y, NODE_W, NODE_H, 10);
    ctx.fill();
    ctx.strokeStyle = accent;
    ctx.globalAlpha = 0.5;
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.globalAlpha = 1;

    // Left accent bar
    ctx.fillStyle = accent;
    roundRect(ctx, x + 1, y + 10, 3, NODE_H - 20, 2);
    ctx.fill();

    // Group chip
    ctx.font = "700 8px ui-sans-serif, system-ui, sans-serif";
    ctx.fillStyle = accent;
    ctx.fillText(
      (ARTIFACT_GROUP_LABEL[n.group] ?? n.group).toUpperCase(),
      x + 14,
      y + 11,
    );

    // Label
    ctx.font = "600 12.5px ui-sans-serif, system-ui, sans-serif";
    ctx.fillStyle = "rgba(255,255,255,0.93)";
    ctx.fillText(n.label, x + 14, y + 27);

    // Self-relationship rows. Each names its ENCODING FIELD, because AC's three
    // PARENT_OF entries are three different encodings — printing the relation
    // name alone made them look like a duplication bug.
    if (n.selfRels?.length) {
      let sy = y + 46;
      for (const sr of n.selfRels) {
        const sspec = artifactEdgeStyle(sr.enforcement, sr.shape);
        ctx.font = "700 8px ui-sans-serif, system-ui, sans-serif";
        ctx.fillStyle = `hsl(${sspec.hsl})`;
        ctx.fillText("↺", x + 14, sy);
        ctx.fillStyle = "rgba(235,242,245,0.82)";
        ctx.fillText(sr.rel, x + 24, sy);
        const relW = ctx.measureText(sr.rel).width;
        ctx.font = "500 7.5px ui-monospace, monospace";
        ctx.fillStyle = "rgba(190,205,215,0.6)";
        ctx.fillText(
          `${sr.field}${sspec.warnGlyph ? ` ${sspec.warnGlyph}` : ""}`,
          x + 28 + relW,
          sy,
        );
        sy += 11;
      }
    }
  }

  drawLegend(ctx, sidePad, height - LEGEND_H + 14, title, meta);

  return await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("Canvas toBlob returned null."))),
      "image/png",
    );
  });
}

/**
 * Legend, glyph key, provenance and counts — everything the image needs to be
 * interpretable on its own once it is pasted somewhere far from this app.
 */
function drawLegend(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  title: string,
  meta?: PngMeta,
): void {
  ctx.textBaseline = "top";

  // --- Node families -------------------------------------------------
  ctx.font = "700 8.5px ui-sans-serif, system-ui, sans-serif";
  ctx.fillStyle = "rgba(190,205,215,0.55)";
  ctx.fillText("NODE FAMILY", x, y);

  let cx = x;
  const famY = y + 15;
  ctx.font = "500 9.5px ui-sans-serif, system-ui, sans-serif";
  for (const [group, label] of Object.entries(ARTIFACT_GROUP_LABEL)) {
    ctx.fillStyle = `hsl(${ARTIFACT_GROUP_HSL[group] ?? "220 9% 62%"})`;
    ctx.fillRect(cx, famY + 2, 3, 9);
    ctx.fillStyle = "rgba(215,228,235,0.8)";
    ctx.fillText(label, cx + 8, famY);
    cx += ctx.measureText(label).width + 26;
  }

  // --- Edge trust (the ingestable_rule, applied verbatim) -------------
  const trustY = y + 38;
  ctx.font = "700 8.5px ui-sans-serif, system-ui, sans-serif";
  ctx.fillStyle = "rgba(190,205,215,0.55)";
  ctx.fillText("EDGE TRUST", x, trustY);

  let ty = trustY + 15;
  ctx.font = "500 9.5px ui-sans-serif, system-ui, sans-serif";
  for (const row of INGESTABILITY_LEGEND) {
    ctx.strokeStyle = `hsl(${row.hsl})`;
    ctx.lineWidth = 2;
    ctx.setLineDash(row.key === "untrusted" ? [4, 3] : []);
    ctx.beginPath();
    ctx.moveTo(x, ty + 6);
    ctx.lineTo(x + 22, ty + 6);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = "rgba(225,235,240,0.9)";
    ctx.fillText(row.label, x + 30, ty);
    const lw = ctx.measureText(row.label).width;
    ctx.fillStyle = "rgba(180,195,205,0.55)";
    ctx.font = "400 8.5px ui-sans-serif, system-ui, sans-serif";
    ctx.fillText(row.hint, x + 36 + lw, ty + 1);
    ctx.font = "500 9.5px ui-sans-serif, system-ui, sans-serif";
    ty += 15;
  }

  // --- Glyph key + provenance (right column) ---------------------------
  const rx = x + 300;
  ctx.font = "700 8.5px ui-sans-serif, system-ui, sans-serif";
  ctx.fillStyle = "rgba(190,205,215,0.55)";
  ctx.fillText("VALUE SHAPE", rx, trustY);
  ctx.font = "400 8.5px ui-sans-serif, system-ui, sans-serif";
  ctx.fillStyle = "rgba(200,214,222,0.75)";
  ctx.fillText("⚠ ambiguous — one field multiplexes several edge types; partition first", rx, trustY + 15);
  ctx.fillText("~ freetext — not programmatically resolvable", rx, trustY + 28);
  ctx.fillText("∅ often-empty — frequently blank in the live store", rx, trustY + 41);
  ctx.fillText("↺ self-referencing relationship (listed on the card)", rx, trustY + 54);

  // Provenance line — a schema map goes stale silently without it.
  const provY = y + LEGEND_H - 40;
  ctx.font = "400 8.5px ui-monospace, monospace";
  ctx.fillStyle = "rgba(170,185,195,0.5)";
  const bits: string[] = [];
  if (meta?.sourceDoc) bits.push(meta.sourceDoc);
  if (meta?.version !== undefined) bits.push(`v${meta.version}`);
  if (meta) {
    bits.push(
      `${meta.nodeCount} node types · ${meta.edgeCount} edges shown · ${meta.selfCount} self`,
    );
  }
  bits.push(`exported ${new Date().toISOString().slice(0, 10)}`);
  ctx.fillText(bits.join("  ·  "), x, provY);
  // Title repeated small so a cropped share still identifies the artifact.
  ctx.fillStyle = "rgba(170,185,195,0.35)";
  ctx.fillText(title, x, provY + 13);
}

/** Copy a PNG blob to the system clipboard. Chromium-only; throws elsewhere. */
export async function copyBlobToClipboard(blob: Blob): Promise<void> {
  if (typeof ClipboardItem === "undefined" || !navigator.clipboard?.write) {
    throw new Error("Clipboard image write is not supported in this browser.");
  }
  await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
}

/** Trigger a file download for a PNG blob. */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
