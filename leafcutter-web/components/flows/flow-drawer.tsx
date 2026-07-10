"use client";

/**
 * Slide-in detail drawer for a single flow step (or branch). Shows the plain-
 * language `human` line, the step's acceptance scenario(s), the entities it
 * reads/writes with their actual mock RECORDS, and its acceptance criteria as
 * chips coloured by each AC's LIVE work-status (clickable through to /atlas).
 */
import * as React from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import {
  X,
  FileText,
  Monitor,
  ArrowDownToLine,
  ArrowUpFromLine,
  ShieldCheck,
  Database,
  GitBranch,
} from "lucide-react";
import { Badge } from "@/components/ui/kit";
import { cn } from "@/lib/utils";
import { WORK_STATUS_TONE } from "@/lib/status";
import type {
  AcRef,
  FlowScenario,
  MockData,
  MockEntity,
  WorkStatus,
} from "@/lib/data/types";

export interface StepView {
  id: string;
  label: string;
  human: string;
  screen: string | null;
  variant: "step" | "branch";
  condition?: string;
  status: WorkStatus;
  reads: string[];
  writes: string[];
  acs: AcRef[];
  scenarios: FlowScenario[];
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

function AcChip({ ac }: { ac: AcRef }) {
  const st = WORK_STATUS_TONE[ac.workStatus] ?? WORK_STATUS_TONE.unknown;
  return (
    <Link
      href={`/atlas?ac=${encodeURIComponent(ac.id)}`}
      title={`${ac.title || ac.id} — ${st.label}. Open in AC Atlas.`}
      className={cn(
        "inline-flex max-w-full items-center gap-1.5 rounded-md border px-2 py-1 font-mono text-[11px] transition-colors",
        st.text,
        st.bg,
        st.border,
        "hover:brightness-125",
      )}
    >
      <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: `hsl(${st.hsl})` }} />
      <span className="truncate">{ac.id}</span>
      <span className="opacity-70">· {st.label}</span>
    </Link>
  );
}

/** Render the concrete mock records for a single entity as a compact table. */
function EntityRecords({ entity }: { entity: MockEntity }) {
  const cols = React.useMemo(() => {
    const keys = new Set<string>();
    for (const r of entity.records) for (const k of Object.keys(r)) keys.add(k);
    return Array.from(keys);
  }, [entity.records]);

  if (entity.records.length === 0) {
    return (
      <div className="rounded-md border border-border/60 bg-background/40 px-2 py-1.5 text-[11px] text-muted-foreground">
        {entity.name} — no records
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border/70 bg-background/50">
      <div className="border-b border-border/60 px-2.5 py-1.5 text-[11px] font-medium text-foreground">
        {entity.name}
        <span className="ml-1.5 font-mono text-[10px] text-muted-foreground">
          {entity.records.length} record{entity.records.length === 1 ? "" : "s"}
        </span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[10px]">
          <thead>
            <tr className="text-left text-muted-foreground">
              {cols.map((c) => (
                <th key={c} className="whitespace-nowrap px-2 py-1 font-medium">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {entity.records.map((r, i) => (
              <tr key={i} className="border-t border-border/40">
                {cols.map((c) => (
                  <td
                    key={c}
                    className="whitespace-nowrap px-2 py-1 font-mono text-foreground/90"
                  >
                    {r[c] === undefined || r[c] === null ? "—" : String(r[c])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function FlowDrawer({
  step,
  mock,
  onClose,
}: {
  step: StepView | null;
  mock: MockData | null;
  onClose: () => void;
}) {
  const touched = React.useMemo(() => {
    if (!step) return [] as MockEntity[];
    const names = new Set([...step.reads, ...step.writes]);
    return (mock?.entities ?? []).filter((e) => names.has(e.name));
  }, [step, mock]);

  const st = step
    ? WORK_STATUS_TONE[step.status] ?? WORK_STATUS_TONE.unknown
    : WORK_STATUS_TONE.unknown;

  return (
    <AnimatePresence>
      {step && (
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
                  <span className="inline-flex items-center gap-1 font-mono text-xs text-primary">
                    {step.variant === "branch" && <GitBranch className="h-3 w-3" />}
                    {step.id}
                  </span>
                  <Badge tone={st} dot>
                    {st.label}
                  </Badge>
                </div>
                <h3 className="mt-1 text-sm font-semibold leading-snug text-foreground">
                  {step.label}
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
              {step.human && (
                <p className="text-sm leading-relaxed text-foreground/90">
                  {step.human}
                </p>
              )}

              {step.variant === "branch" && step.condition && (
                <Section icon={<GitBranch className="h-3 w-3" />} title="Condition">
                  <div className="rounded-md border border-border/60 bg-background/40 px-2.5 py-1.5 text-[12px] text-foreground/90">
                    {step.condition}
                  </div>
                </Section>
              )}

              {step.screen && (
                <Section icon={<Monitor className="h-3 w-3" />} title="Screen">
                  <span className="inline-flex items-center gap-1.5 rounded-md border border-border/60 bg-background/40 px-2 py-1 font-mono text-[11px] text-foreground">
                    {step.screen}
                  </span>
                </Section>
              )}

              {step.acs.length > 0 && (
                <Section
                  icon={<ShieldCheck className="h-3 w-3" />}
                  title="Implements (live AC status)"
                >
                  <div className="flex flex-wrap gap-1.5">
                    {step.acs.map((ac) => (
                      <AcChip key={ac.id} ac={ac} />
                    ))}
                  </div>
                </Section>
              )}

              {step.scenarios.length > 0 && (
                <Section
                  icon={<FileText className="h-3 w-3" />}
                  title="Acceptance scenario"
                >
                  <div className="space-y-2">
                    {step.scenarios.map((sc, i) => (
                      <div
                        key={i}
                        className="rounded-lg border border-border/70 bg-background/50 p-3 text-[11px] leading-relaxed"
                      >
                        <p>
                          <span className="font-semibold text-primary">Given </span>
                          <span className="text-foreground/90">{sc.given}</span>
                        </p>
                        <p>
                          <span className="font-semibold text-primary">When </span>
                          <span className="text-foreground/90">{sc.when}</span>
                        </p>
                        <p>
                          <span className="font-semibold text-primary">Then </span>
                          <span className="text-foreground/90">{sc.then}</span>
                        </p>
                      </div>
                    ))}
                  </div>
                </Section>
              )}

              {step.reads.length > 0 && (
                <Section
                  icon={<ArrowDownToLine className="h-3 w-3" />}
                  title="Reads"
                >
                  <div className="flex flex-wrap gap-1.5">
                    {step.reads.map((e) => (
                      <span
                        key={e}
                        className="rounded-md border border-info/30 bg-info/10 px-2 py-1 font-mono text-[11px] text-info"
                      >
                        {e}
                      </span>
                    ))}
                  </div>
                </Section>
              )}

              {step.writes.length > 0 && (
                <Section
                  icon={<ArrowUpFromLine className="h-3 w-3" />}
                  title="Writes"
                >
                  <div className="flex flex-wrap gap-1.5">
                    {step.writes.map((e) => (
                      <span
                        key={e}
                        className="rounded-md border border-warning/30 bg-warning/10 px-2 py-1 font-mono text-[11px] text-warning"
                      >
                        {e}
                      </span>
                    ))}
                  </div>
                </Section>
              )}

              {touched.length > 0 && (
                <Section
                  icon={<Database className="h-3 w-3" />}
                  title="Mock data"
                >
                  <div className="space-y-2.5">
                    {touched.map((e) => (
                      <EntityRecords key={e.name} entity={e} />
                    ))}
                  </div>
                </Section>
              )}
            </div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
