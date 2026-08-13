import Link from "next/link";
import { LeafMark } from "./logo";
import { DesktopNavLinks, MobileNavLinksList } from "./nav-links";
import { isMockActive } from "@/lib/data/mock";

/**
 * Mock/live badge — UXP-607.
 *
 * Derived from isMockActive() — the SAME resolved per-request decision the
 * data layer (lib/data/repo.ts → repoRoot()) reads to decide whether to serve
 * fixtures or the live repo. This is the single source of truth: the badge
 * must never lag or contradict the override in either direction, so it may
 * NOT read the build-time NEXT_PUBLIC_LEAFCUTTER_MOCK constant (that flag is
 * presentation-only and frozen at build time — it cannot reflect a runtime
 * ?mock= override or the production default-deny gate).
 */
export async function Sidebar() {
  const mockActive = isMockActive();
  return (
    <aside className="sticky top-0 hidden h-svh w-64 shrink-0 flex-col border-r border-border/70 bg-card/40 backdrop-blur-sm lg:flex">
      <Link href="/" className="flex items-center gap-2.5 px-5 py-5">
        <LeafMark />
        <div className="leading-tight">
          <div className="text-sm font-semibold tracking-tight text-foreground">
            Leafcutter <span className="text-primary">Atlas</span>
          </div>
          <div className="text-[11px] text-muted-foreground">Project intelligence</div>
        </div>
      </Link>

      <DesktopNavLinks />

      {/* Mock-mode badge — UXP-607. Driven by the resolved isMockActive()
          decision (same seam the data layer reads), not a build-time flag. */}
      {mockActive && (
        <div className="mx-3 mb-3 flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2.5">
          <span className="h-2 w-2 shrink-0 rounded-full bg-warning animate-pulse" />
          <span className="text-[11px] font-semibold uppercase tracking-widest text-warning">
            Mock mode
          </span>
        </div>
      )}

      <div className="border-t border-border/70 px-5 py-4">
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
          {mockActive ? (
            <>
              <span className="h-1.5 w-1.5 rounded-full bg-warning" />
              Fixtures · bundled mock data
            </>
          ) : (
            <>
              <span className="h-1.5 w-1.5 rounded-full bg-success animate-pulse" />
              Live · reads the repo on each request
            </>
          )}
        </div>
      </div>
    </aside>
  );
}

/** Mobile top nav (compact) shown below lg. */
export async function MobileNav() {
  const mockActive = isMockActive();
  return (
    <div className="sticky top-0 z-30 flex items-center gap-1 overflow-x-auto border-b border-border/70 bg-card/70 px-3 py-2 backdrop-blur lg:hidden">
      <Link href="/" className="mr-2 flex shrink-0 items-center gap-2">
        <LeafMark className="h-6 w-6" />
        <span className="text-sm font-semibold">Atlas</span>
      </Link>
      {/* Mock-mode badge — UXP-607 */}
      {mockActive && (
        <span className="mr-2 shrink-0 rounded border border-warning/40 bg-warning/15 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-widest text-warning">
          Mock
        </span>
      )}
      <MobileNavLinksList />
    </div>
  );
}
