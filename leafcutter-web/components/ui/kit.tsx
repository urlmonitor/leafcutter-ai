/**
 * Leafcutter Atlas UI kit — shared presentational primitives.
 * Plain (server-safe) components; no client hooks. Import freely in any view.
 */
import * as React from "react";
import { cn } from "@/lib/utils";
import type { Tone } from "@/lib/status";

/* ---------- Panel ---------- */
export function Panel({
  className,
  children,
  hover,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { hover?: boolean }) {
  return (
    <div className={cn("panel p-5", hover && "panel-hover", className)} {...props}>
      {children}
    </div>
  );
}

/* ---------- Section header (eyebrow + title + optional action) ---------- */
export function SectionHeader({
  eyebrow,
  title,
  description,
  action,
  className,
}: {
  eyebrow?: string;
  title: React.ReactNode;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mb-5 flex items-end justify-between gap-4", className)}>
      <div>
        {eyebrow && <div className="eyebrow mb-1.5">{eyebrow}</div>}
        <h2 className="text-lg font-semibold tracking-tight text-foreground">{title}</h2>
        {description && (
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

/* ---------- Badge ---------- */
export function Badge({
  tone,
  children,
  className,
  dot,
}: {
  tone?: Tone;
  children: React.ReactNode;
  className?: string;
  dot?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium",
        tone ? cn(tone.text, tone.bg, tone.border) : "border-border bg-muted/40 text-muted-foreground",
        className,
      )}
    >
      {dot && tone && <span className={cn("h-1.5 w-1.5 rounded-full", tone.dot)} />}
      {children}
    </span>
  );
}

/* ---------- Stat card ---------- */
export function StatCard({
  label,
  value,
  sub,
  icon,
  accent = "150 64% 52%",
  className,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  icon?: React.ReactNode;
  accent?: string;
  className?: string;
}) {
  return (
    <Panel className={cn("relative overflow-hidden", className)}>
      <div
        className="pointer-events-none absolute -right-6 -top-8 h-24 w-24 rounded-full opacity-20 blur-2xl"
        style={{ background: `hsl(${accent})` }}
      />
      <div className="flex items-start justify-between">
        <div className="eyebrow">{label}</div>
        {icon && <span style={{ color: `hsl(${accent})` }}>{icon}</span>}
      </div>
      <div className="mt-2 text-3xl font-semibold tracking-tight tabular-nums text-foreground">
        {value}
      </div>
      {sub && <div className="mt-1 text-xs text-muted-foreground">{sub}</div>}
    </Panel>
  );
}

/* ---------- Legend ---------- */
export function Legend({
  items,
  className,
}: {
  items: { label: string; hsl: string }[];
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-center gap-x-4 gap-y-1.5", className)}>
      {items.map((it) => (
        <span key={it.label} className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="h-2.5 w-2.5 rounded-[3px]" style={{ background: `hsl(${it.hsl})` }} />
          {it.label}
        </span>
      ))}
    </div>
  );
}

/* ---------- Meter (thin progress bar) ---------- */
export function Meter({
  value,
  className,
  color = "150 64% 52%",
}: {
  value: number; // 0-100
  className?: string;
  color?: string;
}) {
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-muted/60", className)}>
      <div
        className="h-full rounded-full transition-all"
        style={{ width: `${Math.max(0, Math.min(100, value))}%`, background: `hsl(${color})` }}
      />
    </div>
  );
}

/* ---------- Empty state ---------- */
export function EmptyState({
  title,
  hint,
  icon,
}: {
  title: string;
  hint?: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border/70 py-14 text-center">
      {icon && <div className="mb-3 text-muted-foreground/60">{icon}</div>}
      <p className="text-sm font-medium text-foreground">{title}</p>
      {hint && <p className="mt-1 max-w-sm text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

/* ---------- Page header (per-view hero strip) ---------- */
export function PageHeader({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  children?: React.ReactNode;
}) {
  return (
    <header className="mb-8">
      <div className="eyebrow mb-2 flex items-center gap-2">
        <span className="inline-block h-px w-6 bg-primary/60" />
        {eyebrow}
      </div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
            {title}
          </h1>
          {description && (
            <p className="mt-2 max-w-2xl text-sm text-muted-foreground">{description}</p>
          )}
        </div>
        {children && <div className="shrink-0">{children}</div>}
      </div>
    </header>
  );
}
