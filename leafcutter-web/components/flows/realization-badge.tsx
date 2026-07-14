/**
 * Realization badge — the honest "does this system EXIST yet?" marker.
 *
 * A flow's `realization` is a different axis from its per-step impl_status: a
 * flow can be fully "done" against its ACs and still describe a system that has
 * never been built. Without this badge a reviewer reads a spec flow as a live
 * map and concludes the product "works" when no real request flows through it.
 *
 * Styled DELIBERATELY unlike the impl_status tone badges (which are subtle,
 * tinted pills): this is a solid, high-contrast, uppercase chip so it reads as a
 * warning first, not as another status dot. "built" renders nothing.
 */
import * as React from "react";
import { FlaskConical, Beaker } from "lucide-react";
import { cn } from "@/lib/utils";
import type { FlowRealization } from "@/lib/data/types";

interface RealizationMeta {
  label: string;      // full, on the header
  short: string;      // compact, on a step card
  hsl: string;        // solid fill hue
  description: string; // tooltip / secondary line
  icon: React.ComponentType<{ className?: string }>;
}

const META: Record<Exclude<FlowRealization, "built">, RealizationMeta> = {
  spec: {
    label: "Spec · not built yet",
    short: "Spec",
    hsl: "280 68% 62%",
    description:
      "This flow is a specification — the system it maps does not exist yet. No real request flows through it.",
    icon: FlaskConical,
  },
  mock: {
    label: "Sample",
    short: "Sample",
    hsl: "199 85% 55%",
    description:
      "This flow uses sample / demo product content, not a real system. It illustrates the shape, not live behaviour.",
    icon: Beaker,
  },
};

/** Look up the display metadata for a realization, or null for "built". */
export function realizationMeta(realization: FlowRealization) {
  return realization === "built" ? null : META[realization];
}

export function RealizationBadge({
  realization,
  size = "md",
  className,
}: {
  realization: FlowRealization;
  size?: "sm" | "md";
  className?: string;
}) {
  const meta = realizationMeta(realization);
  if (!meta) return null;
  const Icon = meta.icon;
  const label = size === "sm" ? meta.short : meta.label;
  return (
    <span
      title={meta.description}
      className={cn(
        "inline-flex items-center gap-1 rounded-md font-bold uppercase tracking-wide shadow-sm",
        size === "sm" ? "px-1.5 py-0.5 text-[9px]" : "px-2.5 py-1 text-[11px]",
        className,
      )}
      style={{
        background: `hsl(${meta.hsl})`,
        color: "hsl(160 30% 7%)",
        border: `1px solid hsl(${meta.hsl})`,
      }}
    >
      <Icon className={size === "sm" ? "h-2.5 w-2.5" : "h-3.5 w-3.5"} />
      {label}
    </span>
  );
}
