"use client";

/**
 * Slide-in detail drawer for a single AC (framer-motion). Renders the full
 * record: badges, the Gherkin criteria in a mono block, and every relationship
 * as a chip. Chips whose target exists in the current graph are clickable and
 * re-select that node; the rest render as static references.
 */
import * as React from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import {
  X,
  FileText,
  GitBranch,
  ArrowRight,
  ArrowLeft,
  ShieldCheck,
  Bot,
  Link2,
  Route,
  FlaskConical,
  AlertTriangle,
} from "lucide-react";
import { Badge } from "@/components/ui/kit";
import { cn, humanize } from "@/lib/utils";
import {
  LEVEL_TONE,
  PRIORITY_TONE,
  READINESS_TONE,
  WORK_STATUS_TONE,
} from "@/lib/status";
import type { AC, FlowAppearance } from "@/lib/data/types";

function Chip({
  label,
  present,
  onClick,
  title,
}: {
  label: string;
  present: boolean;
  onClick?: () => void;
  title?: string;
}) {
  return (
    <button
      type="button"
      disabled={!present}
      onClick={present ? onClick : undefined}
      title={title ?? (present ? "Jump to this AC" : "Not in current view")}
      className={cn(
        "inline-flex max-w-full items-center gap-1 rounded-md border px-2 py-1 font-mono text-[11px] transition-colors",
        present
          ? "cursor-pointer border-primary/40 bg-primary/10 text-primary hover:bg-primary/20"
          : "cursor-default border-border/70 bg-muted/30 text-muted-foreground",
      )}
    >
      <span className="truncate">{label}</span>
    </button>
  );
}

function Section({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">
        {icon}
        {title}
      </div>
      {children}
    </div>
  );
}

/** Test-coverage block: prominent count, unguarded warning, ref list, rollup. */
function TestCoverage({ ac }: { ac: AC }) {
  const count = ac.testCount ?? 0;
  const refs = ac.testRefs ?? [];
  const rolledUp = ac.testRolledUpCount ?? 0;
  const isComposite = ac.isLeaf === false;
  const tone =
    count === 0
      ? "356 72% 56%" // red — unguarded
      : count < 3
        ? "38 92% 58%" // amber — thin
        : "150 60% 48%"; // green — solid

  return (
    <div className="space-y-2">
      <div className="flex items-baseline gap-2">
        <span
          className="text-2xl font-semibold tabular-nums leading-none"
          style={{ color: `hsl(${tone})` }}
        >
          {count}
        </span>
        <span className="text-[11px] text-muted-foreground">
          {count === 1 ? "test references this AC" : "tests reference this AC"}
        </span>
        {isComposite && rolledUp > count && (
          <span className="ml-auto rounded-md border border-border/60 bg-background/40 px-2 py-0.5 font-mono text-[11px] text-muted-foreground">
            {rolledUp} incl. descendants
          </span>
        )}
      </div>

      {count === 0 ? (
        <div className="flex items-start gap-1.5 rounded-md border border-warning/40 bg-warning/10 px-2 py-1.5 text-[11px] text-warning">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>Unguarded — no test references this AC</span>
        </div>
      ) : (
        <div className="space-y-1">
          {refs.map((r) => (
            <div
              key={r}
              className="truncate rounded-md border border-border/60 bg-background/40 px-2 py-1 font-mono text-[11px] text-muted-foreground"
              title={r}
            >
              {r}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function DetailDrawer({
  ac,
  presentIds,
  onSelect,
  onClose,
  flowAppearances,
}: {
  ac: AC | null;
  presentIds: Set<string>;
  onSelect: (id: string) => void;
  onClose: () => void;
  flowAppearances?: FlowAppearance[];
}) {
  return (
    <AnimatePresence>
      {ac && (
        <>
          <motion.div
            key="scrim"
            className="absolute inset-0 z-20 bg-background/40 backdrop-blur-[1px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.aside
            key="drawer"
            className="absolute right-0 top-0 z-30 flex h-full w-full max-w-md flex-col border-l border-border/80 bg-card/95 shadow-2xl backdrop-blur-md"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 320 }}
          >
            {/* header */}
            <div className="flex items-start justify-between gap-3 border-b border-border/70 p-5">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-primary">{ac.id}</span>
                  <span className="text-[11px] text-muted-foreground">
                    {humanize(ac.component)}
                  </span>
                </div>
                <h3 className="mt-1 text-sm font-semibold leading-snug text-foreground">
                  {ac.title || "Untitled acceptance criterion"}
                </h3>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="shrink-0 rounded-md border border-border/70 p-1.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* body */}
            <div className="flex-1 space-y-5 overflow-y-auto p-5">
              <div className="flex flex-wrap gap-1.5">
                <Badge tone={LEVEL_TONE[ac.level]} dot>
                  {LEVEL_TONE[ac.level]?.label ?? ac.level}
                </Badge>
                <Badge tone={WORK_STATUS_TONE[ac.workStatus]} dot>
                  {ac.workStatusRaw || WORK_STATUS_TONE[ac.workStatus]?.label}
                </Badge>
                <Badge tone={PRIORITY_TONE[ac.priority]}>
                  {PRIORITY_TONE[ac.priority]?.label ?? ac.priority}
                </Badge>
                <Badge tone={READINESS_TONE[ac.readiness]}>
                  {READINESS_TONE[ac.readiness]?.label ?? ac.readiness}
                </Badge>
                {ac.complexity !== "unknown" && (
                  <Badge>{ac.complexity}</Badge>
                )}
              </div>

              {ac.criteria && (
                <Section icon={<FileText className="h-3 w-3" />} title="Criteria">
                  <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-lg border border-border/70 bg-background/60 p-3 font-mono text-[11px] leading-relaxed text-foreground/90">
                    {ac.criteria}
                  </pre>
                </Section>
              )}

              <Section
                icon={<FlaskConical className="h-3 w-3" />}
                title="Tests guarding this AC"
              >
                <TestCoverage ac={ac} />
              </Section>

              {ac.dependsOn.length > 0 && (
                <Section icon={<GitBranch className="h-3 w-3" />} title="Depends on">
                  <div className="flex flex-wrap gap-1.5">
                    {ac.dependsOn.map((id) => (
                      <Chip
                        key={id}
                        label={id}
                        present={presentIds.has(id)}
                        onClick={() => onSelect(id)}
                      />
                    ))}
                  </div>
                </Section>
              )}

              {ac.deliversTo && (
                <Section icon={<ArrowRight className="h-3 w-3" />} title="Delivers to">
                  <Chip
                    label={ac.deliversTo}
                    present={presentIds.has(ac.deliversTo)}
                    onClick={() => ac.deliversTo && onSelect(ac.deliversTo)}
                  />
                </Section>
              )}

              {ac.expectsFrom.length > 0 && (
                <Section icon={<ArrowLeft className="h-3 w-3" />} title="Expects from">
                  <div className="space-y-1.5">
                    {ac.expectsFrom.map((e) => (
                      <div key={e.id} className="flex flex-col gap-1">
                        <Chip
                          label={e.id}
                          present={presentIds.has(e.id)}
                          onClick={() => onSelect(e.id)}
                        />
                        {e.reason && (
                          <span className="pl-1 text-[11px] leading-snug text-muted-foreground">
                            {e.reason}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </Section>
              )}

              {ac.coveredBy.length > 0 && (
                <Section icon={<GitBranch className="h-3 w-3 rotate-90" />} title="Covered by">
                  <div className="flex flex-wrap gap-1.5">
                    {ac.coveredBy.map((id) => (
                      <Chip
                        key={id}
                        label={id}
                        present={presentIds.has(id)}
                        onClick={() => onSelect(id)}
                      />
                    ))}
                  </div>
                </Section>
              )}

              {ac.implementedBy.length > 0 && (
                <Section icon={<ShieldCheck className="h-3 w-3" />} title="Implemented by">
                  <div className="space-y-1">
                    {ac.implementedBy.map((p) => (
                      <div
                        key={p}
                        className="truncate rounded-md border border-border/60 bg-background/40 px-2 py-1 font-mono text-[11px] text-muted-foreground"
                        title={p}
                      >
                        {p}
                      </div>
                    ))}
                  </div>
                </Section>
              )}

              {flowAppearances && flowAppearances.length > 0 && (
                <Section icon={<Route className="h-3 w-3" />} title="Appears in flows">
                  <div className="space-y-1.5">
                    {flowAppearances.map((f) => (
                      <Link
                        key={`${f.flowId}:${f.stepId}`}
                        href={`/flows?flow=${encodeURIComponent(f.flowId)}&step=${encodeURIComponent(f.stepId)}`}
                        title={`Open "${f.stepLabel}" in ${f.flowName}`}
                        className="flex items-center justify-between gap-2 rounded-md border border-primary/40 bg-primary/10 px-2 py-1.5 text-[11px] text-primary transition-colors hover:bg-primary/20"
                      >
                        <span className="truncate font-medium">{f.stepLabel}</span>
                        <span className="shrink-0 truncate text-[10px] text-primary/70">
                          {f.flowName}
                        </span>
                      </Link>
                    ))}
                  </div>
                </Section>
              )}

              {ac.assignedAgent && (
                <Section icon={<Bot className="h-3 w-3" />} title="Assigned agent">
                  <span className="inline-flex items-center gap-1.5 rounded-md border border-border/60 bg-background/40 px-2 py-1 font-mono text-[11px] text-foreground">
                    {ac.assignedAgent}
                  </span>
                </Section>
              )}

              {ac.docLinks.length > 0 && (
                <Section icon={<Link2 className="h-3 w-3" />} title="Doc links">
                  <div className="space-y-1">
                    {ac.docLinks.map((d) => (
                      <div
                        key={d}
                        className="truncate rounded-md border border-border/60 bg-background/40 px-2 py-1 font-mono text-[11px] text-muted-foreground"
                        title={d}
                      >
                        {d}
                      </div>
                    ))}
                  </div>
                </Section>
              )}

              <Section icon={<FileText className="h-3 w-3" />} title="Source">
                <div
                  className="truncate rounded-md border border-border/60 bg-background/40 px-2 py-1 font-mono text-[11px] text-muted-foreground"
                  title={ac.filePath}
                >
                  {ac.filePath}
                </div>
              </Section>
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
