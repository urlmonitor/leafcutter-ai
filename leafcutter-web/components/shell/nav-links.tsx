"use client";

/**
 * Client-side nav link islands for the app shell.
 *
 * Split out of sidebar.tsx (UXP-607) so that Sidebar/MobileNav can become
 * Server Components that resolve the mock/live badge from isMockActive()
 * (which reads next/headers — a server-only API) while the pathname-based
 * active-link highlighting — which needs the usePathname() client hook —
 * still works.
 */

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BookOpen,
  GitBranch,
  Map as MapIcon,
  Workflow,
  Boxes,
  Route,
  Zap,
  ShieldCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";

export const NAV = [
  { href: "/", label: "Pulse", icon: Activity, desc: "Project health at a glance" },
  { href: "/now", label: "Now & Next", icon: Zap, desc: "In flight + what builds next" },
  { href: "/atlas", label: "AC Atlas", icon: GitBranch, desc: "How acceptance criteria connect" },
  { href: "/flows", label: "Flows", icon: Route, desc: "Product truth, coloured by build status" },
  { href: "/roadmap", label: "Roadmap", icon: MapIcon, desc: "Phases & what's next" },
  { href: "/coverage", label: "Coverage", icon: ShieldCheck, desc: "How many tests guard each AC" },
  { href: "/about", label: "About", icon: BookOpen, desc: "What leafcutter is & how it works" },
  { href: "/pipeline", label: "Pipeline", icon: Workflow, desc: "How leafcutter builds software" },
  { href: "/architecture", label: "Architecture", icon: Boxes, desc: "The component map" },
];

/** Desktop sidebar nav list — active-link state derived from the current pathname. */
export function DesktopNavLinks() {
  const pathname = usePathname();
  return (
    <nav className="mt-2 flex-1 space-y-1 px-3">
      {NAV.map((item) => {
        const active =
          item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "group flex items-start gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors",
              active
                ? "bg-primary/10 text-foreground"
                : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
            )}
          >
            <Icon
              className={cn(
                "mt-0.5 h-4 w-4 shrink-0",
                active ? "text-primary" : "text-muted-foreground group-hover:text-foreground",
              )}
            />
            <span className="flex flex-col">
              <span className="font-medium">{item.label}</span>
              <span className="text-[11px] text-muted-foreground/80">{item.desc}</span>
            </span>
            {active && <span className="ml-auto mt-1 h-1.5 w-1.5 rounded-full bg-primary animate-pulse-ring" />}
          </Link>
        );
      })}
    </nav>
  );
}

/** Compact mobile top-nav link list — active-link state derived from the current pathname. */
export function MobileNavLinksList() {
  const pathname = usePathname();
  return (
    <>
      {NAV.map((item) => {
        const active =
          item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "whitespace-nowrap rounded-md px-2.5 py-1 text-xs font-medium",
              active ? "bg-primary/15 text-foreground" : "text-muted-foreground",
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </>
  );
}
