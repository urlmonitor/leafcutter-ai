"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  GitBranch,
  Map as MapIcon,
  Workflow,
  Boxes,
  Route,
  Zap,
  ShieldCheck,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { LeafMark } from "./logo";

const NAV = [
  { href: "/", label: "Pulse", icon: Activity, desc: "Project health at a glance" },
  { href: "/now", label: "Now & Next", icon: Zap, desc: "In flight + what builds next" },
  { href: "/atlas", label: "AC Atlas", icon: GitBranch, desc: "How acceptance criteria connect" },
  { href: "/flows", label: "Flows", icon: Route, desc: "Product truth, coloured by build status" },
  { href: "/roadmap", label: "Roadmap", icon: MapIcon, desc: "Phases & what's next" },
  { href: "/coverage", label: "Coverage", icon: ShieldCheck, desc: "How many tests guard each AC" },
  { href: "/pipeline", label: "Pipeline", icon: Workflow, desc: "How leafcutter builds software" },
  { href: "/architecture", label: "Architecture", icon: Boxes, desc: "The component map" },
];

export function Sidebar() {
  const pathname = usePathname();
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

      <div className="border-t border-border/70 px-5 py-4">
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
          <span className="h-1.5 w-1.5 rounded-full bg-success animate-pulse" />
          Live · reads the repo on each request
        </div>
      </div>
    </aside>
  );
}

/** Mobile top nav (compact) shown below lg. */
export function MobileNav() {
  const pathname = usePathname();
  return (
    <div className="sticky top-0 z-30 flex items-center gap-1 overflow-x-auto border-b border-border/70 bg-card/70 px-3 py-2 backdrop-blur lg:hidden">
      <Link href="/" className="mr-2 flex items-center gap-2">
        <LeafMark className="h-6 w-6" />
        <span className="text-sm font-semibold">Atlas</span>
      </Link>
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
    </div>
  );
}
