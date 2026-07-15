"use client";

import * as React from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { X, FileCode2, FileText, GitBranch, Boxes, ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { componentStatusTone, type ComponentVM } from "./lib";

/** Slide-in detail drawer for a single architecture component. */
export function ComponentDrawer({
  component,
  hsl,
  typeLabel,
  onClose,
}: {
  component: ComponentVM | null;
  hsl: string;
  typeLabel: string;
  onClose: () => void;
}) {
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const status = component ? componentStatusTone(component.status) : null;

  return (
    <AnimatePresence>
      {component && (
        <motion.div
          className="fixed inset-0 z-50 flex justify-end"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          <div
            className="absolute inset-0 bg-background/70 backdrop-blur-sm"
            onClick={onClose}
            aria-hidden
          />
          <motion.aside
            className="relative flex h-full w-full max-w-md flex-col overflow-hidden border-l border-border/80 bg-card/95 shadow-2xl"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 320, damping: 34 }}
            role="dialog"
            aria-label={`${component.name} details`}
          >
            {/* Accent header */}
            <div
              className="pointer-events-none absolute inset-x-0 top-0 h-28 opacity-25 blur-2xl"
              style={{ background: `radial-gradient(60% 100% at 80% 0%, hsl(${hsl}), transparent 70%)` }}
            />
            <div className="relative flex items-start justify-between gap-3 border-b border-border/60 px-6 py-5">
              <div className="min-w-0">
                <div
                  className="mb-2 inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium"
                  style={{
                    color: `hsl(${hsl})`,
                    borderColor: `hsl(${hsl} / 0.35)`,
                    background: `hsl(${hsl} / 0.12)`,
                  }}
                >
                  <span className="h-1.5 w-1.5 rounded-full" style={{ background: `hsl(${hsl})` }} />
                  {typeLabel}
                </div>
                <h2 className="truncate text-lg font-semibold tracking-tight text-foreground">
                  {component.name}
                </h2>
                <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                  {status && (
                    <span className="inline-flex items-center gap-1.5">
                      <span className="h-1.5 w-1.5 rounded-full" style={{ background: `hsl(${status.hsl})` }} />
                      {status.label}
                    </span>
                  )}
                  <span className="text-muted-foreground/40">·</span>
                  <code className="font-mono text-[11px] text-muted-foreground/80">{component.id}</code>
                </div>
              </div>
              <button
                onClick={onClose}
                className="shrink-0 rounded-lg border border-border/70 p-1.5 text-muted-foreground transition-colors hover:border-border hover:text-foreground"
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Body */}
            <div className="relative flex-1 space-y-6 overflow-y-auto px-6 py-6">
              <Section icon={<FileText className="h-3.5 w-3.5" />} title="Description">
                <p className="text-sm leading-relaxed text-foreground/90">
                  {component.description || "No description registered for this component."}
                </p>
              </Section>

              <Section icon={<Boxes className="h-3.5 w-3.5" />} title="Architecture doc">
                {component.detailRef ? (
                  <span className="inline-flex max-w-full items-center gap-1.5 rounded-md border border-border/70 bg-secondary/50 px-2.5 py-1.5 font-mono text-xs text-foreground/90">
                    <FileText className="h-3.5 w-3.5 shrink-0 text-primary" />
                    <span className="truncate">{component.detailRef}</span>
                  </span>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    No architecture doc linked yet.
                  </p>
                )}
              </Section>

              <Section
                icon={<FileCode2 className="h-3.5 w-3.5" />}
                title={`Primary code (${component.primaryCode.length})`}
              >
                {component.primaryCode.length ? (
                  <ul className="space-y-1.5">
                    {component.primaryCode.map((p) => (
                      <li
                        key={p}
                        className="flex items-center gap-2 rounded-md border border-border/50 bg-background/40 px-2.5 py-1.5 font-mono text-xs text-foreground/85"
                      >
                        <FileCode2 className="h-3.5 w-3.5 shrink-0 text-muted-foreground/70" />
                        <span className="truncate">{p}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-muted-foreground">No primary code paths registered.</p>
                )}
              </Section>

              <Section icon={<GitBranch className="h-3.5 w-3.5" />} title="Acceptance criteria">
                {component.acLink ? (
                  <Link
                    href="/atlas"
                    className="group flex items-center justify-between gap-3 rounded-lg border border-border/70 bg-secondary/40 px-3.5 py-3 transition-colors hover:border-primary/40 hover:bg-secondary/70"
                  >
                    <div className="min-w-0">
                      <div className="flex items-baseline gap-2">
                        <span className="text-xl font-semibold tabular-nums text-foreground">
                          {component.acLink.acCount}
                        </span>
                        <span className="text-xs text-muted-foreground">specs</span>
                      </div>
                      <div className="mt-0.5 truncate text-[11px] text-muted-foreground">
                        namespace{" "}
                        <code className="font-mono text-muted-foreground/90">{component.acLink.prefix}</code>{" "}
                        · {component.acLink.nsId}
                      </div>
                    </div>
                    <span className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-primary">
                      AC Atlas
                      <ArrowUpRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
                    </span>
                  </Link>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    No AC namespace maps to this component — its specs live under a different
                    vocabulary.
                  </p>
                )}
              </Section>
            </div>
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
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
  className?: string;
}) {
  return (
    <div>
      <div className={cn("eyebrow mb-2 flex items-center gap-1.5")}>
        <span className="text-muted-foreground/70">{icon}</span>
        {title}
      </div>
      {children}
    </div>
  );
}
