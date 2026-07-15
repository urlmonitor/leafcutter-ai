import * as React from "react";
import Link from "next/link";
import { Boxes, User } from "lucide-react";
import { fmt } from "@/lib/utils";
import type { NamespaceFacet } from "./lib";

/** Secondary section: the 13 AC-store namespaces, tying specs to architecture. */
export function AcFacet({ facets }: { facets: NamespaceFacet[] }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {facets.map((f) => (
        <FacetCard key={f.id} f={f} />
      ))}
    </div>
  );
}

function FacetCard({ f }: { f: NamespaceFacet }) {
  const total = f.byStatus.reduce((n, s) => n + s.count, 0) || 1;
  return (
    <div className="panel panel-hover flex flex-col p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="rounded-md border border-primary/25 bg-primary/10 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-primary">
              {f.prefix}
            </span>
            <h3 className="truncate text-sm font-semibold tracking-tight text-foreground">
              {f.label}
            </h3>
          </div>
          <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
            {f.description || "No description registered."}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <div className="text-xl font-semibold tabular-nums text-foreground">{fmt(f.acCount)}</div>
          <div className="eyebrow">ACs</div>
        </div>
      </div>

      {/* Stacked status bar */}
      <div className="mt-3">
        <div className="flex h-2 w-full overflow-hidden rounded-full bg-muted/50">
          {f.byStatus.map((s) => (
            <span
              key={s.key}
              className="h-full first:rounded-l-full last:rounded-r-full"
              style={{ width: `${(s.count / total) * 100}%`, background: `hsl(${s.hsl})` }}
              title={`${s.label}: ${s.count}`}
            />
          ))}
        </div>
        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1">
          {f.byStatus.map((s) => (
            <span key={s.key} className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: `hsl(${s.hsl})` }} />
              {s.label}
              <span className="tabular-nums text-foreground/80">{s.count}</span>
            </span>
          ))}
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between gap-2 border-t border-border/50 pt-3 text-[11px] text-muted-foreground">
        <span className="inline-flex min-w-0 items-center gap-1.5">
          {f.owner ? (
            <>
              <User className="h-3 w-3 shrink-0" />
              <span className="truncate">
                owner <code className="font-mono text-muted-foreground/90">{f.owner}</code>
              </span>
            </>
          ) : (
            <span className="text-muted-foreground/60">no owner</span>
          )}
        </span>
        {f.mappedComponent ? (
          <span className="inline-flex shrink-0 items-center gap-1 text-primary/80" title="Maps to an architecture component">
            <Boxes className="h-3 w-3" />
            component
          </span>
        ) : (
          <Link href="/atlas" className="shrink-0 text-primary/80 hover:text-primary">
            view specs →
          </Link>
        )}
      </div>
    </div>
  );
}
