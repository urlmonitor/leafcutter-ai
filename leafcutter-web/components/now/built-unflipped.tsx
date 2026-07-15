"use client";

import * as React from "react";
import { motion } from "framer-motion";
import { CircleAlert, FileCheck2 } from "lucide-react";
import { colorForKey } from "@/lib/status";
import { humanize } from "@/lib/utils";
import { EmptyState } from "@/components/ui/kit";
import type { BuiltItem } from "./types";

/** Trim a repo-relative implemented_by ref to its readable tail. */
function shortRef(ref: string): string {
  const r = ref.trim();
  const tail = r.split("/").pop() ?? r;
  return tail.replace(/\.md$/, "");
}

function Card({ item, index }: { item: BuiltItem; index: number }) {
  return (
    <motion.li
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.04, ease: [0.22, 1, 0.36, 1] }}
      className="rounded-lg border border-warning/25 bg-warning/[0.04] p-4"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-medium text-foreground">{item.title}</div>
          <div className="mt-1 flex flex-wrap items-center gap-x-2.5 gap-y-1 text-[11px] text-muted-foreground">
            <span className="font-mono text-muted-foreground/80">{item.id}</span>
            <span className="inline-flex items-center gap-1.5">
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: `hsl(${colorForKey(item.component)})` }}
              />
              {humanize(item.component)}
            </span>
          </div>
        </div>
        <FileCheck2 className="h-4 w-4 shrink-0 text-warning/70" />
      </div>
      {item.implementedBy.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          {item.implementedBy.slice(0, 4).map((ref) => (
            <span
              key={ref}
              className="max-w-[16rem] truncate rounded-md border border-border/70 bg-muted/40 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground"
              title={ref}
            >
              {shortRef(ref)}
            </span>
          ))}
          {item.implementedBy.length > 4 && (
            <span className="text-[10px] text-muted-foreground/70">
              +{item.implementedBy.length - 4} more
            </span>
          )}
        </div>
      )}
    </motion.li>
  );
}

export function BuiltUnflipped({ items }: { items: BuiltItem[] }) {
  if (items.length === 0) {
    return (
      <EmptyState
        title="Every delivered AC has its status flipped"
        hint="No leaf AC resolves to real source or a done ticket while still flagged todo."
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-2.5 rounded-lg border border-warning/30 bg-warning/[0.06] px-3.5 py-3">
        <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
        <div className="text-xs text-muted-foreground">
          <span className="font-medium text-foreground">
            Status-switching is best-effort — these {items.length} are built but still flagged todo.
          </span>{" "}
          The pipeline&rsquo;s mark-done step (<span className="font-mono">finalize-feature</span> →{" "}
          <span className="font-mono">mark_ac_done.py</span>) is non-fatal, so when it doesn&rsquo;t
          fire a small set of delivered ACs — each resolving to real source or a done ticket — never
          gets flipped. This is the evidence-backed answer to &ldquo;do we actually switch AC
          status?&rdquo;: mostly yes, but not guaranteed.
        </div>
      </div>
      <ol className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {items.map((item, i) => (
          <Card key={item.id} item={item} index={i} />
        ))}
      </ol>
    </div>
  );
}
