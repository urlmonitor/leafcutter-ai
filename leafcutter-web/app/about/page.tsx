import * as React from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { PageHeader, Panel, SectionHeader } from "@/components/ui/kit";
import { cn } from "@/lib/utils";
import {
  FLIGHT_LEVELS,
  READINESS,
  TICKET_FOLDERS,
  GATES,
  CROSS_LINKS,
  AC_YAML,
  TICKET_FRONTMATTER,
} from "./data";

/* ── Internal helper ──────────────────────────────────────────── */

function CodeBlock({ label, code }: { label: string; code: string }) {
  return (
    <div className="overflow-hidden rounded-xl border border-border/70">
      <div className="border-b border-border/70 bg-muted/60 px-4 py-2.5">
        <span className="eyebrow">{label}</span>
      </div>
      <pre
        className="overflow-x-auto bg-background/80 p-5 text-[11.5px] leading-[1.75] text-muted-foreground"
        style={{ fontFamily: "var(--font-geist-mono, ui-monospace, monospace)" }}
      >
        <code>{code}</code>
      </pre>
    </div>
  );
}

/* ── Page ─────────────────────────────────────────────────────── */

export const metadata = {
  title: "About — Leafcutter Atlas",
  description: "What leafcutter is, how its vocabulary works, and how to read its two key file formats.",
};

export default function AboutPage() {
  return (
    <div className="animate-fade-in space-y-14">
      <PageHeader
        eyebrow="What is Leafcutter"
        title="About Leafcutter"
        description="Leafcutter is a portable, self-hosting agentic software-delivery pipeline. It installs into any project by compiling a templates/ directory into that project's .leafcutter/, then drives work from a plain-language feature request all the way to a merged PR — through slash commands, a supervisor loop, specialised phase agents, and mechanical pre-commit and finalize gates. The acceptance-criteria store is the authoritative backlog; tickets are derived from ACs, never authored first."
      />

      {/* ── The vocabulary ──────────────────────────────────────────── */}
      <section className="space-y-8">
        <SectionHeader
          eyebrow="The vocabulary"
          title="Concepts every Leafcutter user meets"
          description="These five models repeat across every view in Atlas. Learn them once and the live data pages become legible."
        />

        {/* Flight levels */}
        <div>
          <p className="mb-3 text-sm font-medium text-foreground">
            Flight levels — how ACs are stratified
          </p>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {FLIGHT_LEVELS.map((fl) => (
              <Panel key={fl.level} className="relative overflow-hidden">
                <div
                  className="pointer-events-none absolute -right-6 -top-8 h-20 w-20 rounded-full opacity-[0.15] blur-2xl"
                  style={{ background: `hsl(${fl.accent})` }}
                />
                <div className="eyebrow mb-2">{fl.level}</div>
                <p className="mb-1 text-sm font-semibold text-foreground">{fl.label}</p>
                <p className="text-xs leading-relaxed text-muted-foreground">{fl.desc}</p>
              </Panel>
            ))}
          </div>
        </div>

        {/* Readiness lifecycle */}
        <div>
          <p className="mb-3 text-sm font-medium text-foreground">
            Readiness lifecycle — what gates ticket generation
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {READINESS.map((r, i) => (
              <Panel key={r.state}>
                <div className="mb-2 flex items-center gap-2">
                  <span className={cn("font-mono text-sm font-semibold", r.colorClass)}>
                    {r.state}
                  </span>
                  {i < READINESS.length - 1 && (
                    <ArrowRight className="h-3 w-3 shrink-0 text-muted-foreground/40" />
                  )}
                </div>
                <p className="text-xs leading-relaxed text-muted-foreground">{r.desc}</p>
              </Panel>
            ))}
          </div>
        </div>

        {/* Gate catalog */}
        <div>
          <p className="mb-3 text-sm font-medium text-foreground">
            The gate catalog — what runs before every commit lands on main
          </p>
          <Panel>
            <div className="divide-y divide-border/50">
              {GATES.map((g) => (
                <div key={g.name} className="py-3.5 first:pt-0 last:pb-0">
                  <p className="mb-0.5 text-sm font-semibold text-foreground">{g.name}</p>
                  <p className="text-xs leading-relaxed text-muted-foreground">{g.desc}</p>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        {/* Ticket lifecycle */}
        <div>
          <p className="mb-3 text-sm font-medium text-foreground">
            Ticket lifecycle — where tickets live on disk
          </p>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {TICKET_FOLDERS.map((f) => (
              <Panel key={f.folder}>
                <p className="mb-1 font-mono text-xs text-primary">{f.folder}</p>
                <p className="mb-1 text-sm font-semibold text-foreground">{f.label}</p>
                <p className="text-xs leading-relaxed text-muted-foreground">{f.desc}</p>
              </Panel>
            ))}
          </div>
        </div>

        {/* Package model */}
        <div>
          <p className="mb-3 text-sm font-medium text-foreground">
            The package model — how Leafcutter installs into a project
          </p>
          <Panel>
            <div className="grid gap-5 sm:grid-cols-2">
              <div>
                <div className="eyebrow mb-1.5">Install</div>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  Run{" "}
                  <code className="rounded bg-muted/80 px-1 py-0.5 font-mono text-[11px] text-foreground">
                    scripts/build.py --target-dir .
                  </code>{" "}
                  to compile{" "}
                  <code className="rounded bg-muted/80 px-1 py-0.5 font-mono text-[11px] text-foreground">
                    templates/
                  </code>{" "}
                  into your project&apos;s{" "}
                  <code className="rounded bg-muted/80 px-1 py-0.5 font-mono text-[11px] text-foreground">
                    .leafcutter/
                  </code>
                  . A shim step bridges to{" "}
                  <code className="rounded bg-muted/80 px-1 py-0.5 font-mono text-[11px] text-foreground">
                    .claude/
                  </code>{" "}
                  and other platform-native paths (ADR-004).
                </p>
              </div>
              <div>
                <div className="eyebrow mb-1.5">Configure</div>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  The{" "}
                  <code className="rounded bg-muted/80 px-1 py-0.5 font-mono text-[11px] text-foreground">
                    /onboard
                  </code>{" "}
                  wizard generates a project-local{" "}
                  <code className="rounded bg-muted/80 px-1 py-0.5 font-mono text-[11px] text-foreground">
                    skills_config.json
                  </code>
                  . Five sections: testing, packages, tickets, commands, project. No
                  config ships in the package itself.
                </p>
              </div>
              <div>
                <div className="eyebrow mb-1.5">Self-hosting</div>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  Leafcutter builds itself:{" "}
                  <code className="rounded bg-muted/80 px-1 py-0.5 font-mono text-[11px] text-foreground">
                    ./build-self.sh
                  </code>
                  . The{" "}
                  <code className="rounded bg-muted/80 px-1 py-0.5 font-mono text-[11px] text-foreground">
                    leafcutter-ai/
                  </code>{" "}
                  subdirectory is the git repo root; the parent workspace is untracked build output (ADR-001).
                </p>
              </div>
              <div>
                <div className="eyebrow mb-1.5">Current phase</div>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  <span className="font-semibold text-foreground">phase_1</span> — Stable MVP.
                  Exit criteria: clean install on a blank project;{" "}
                  <code className="rounded bg-muted/80 px-1 py-0.5 font-mono text-[11px] text-foreground">
                    build.py --validate-only
                  </code>{" "}
                  returns 0; consecutive builds produce zero diff (idempotent); self-hosting parity.
                </p>
              </div>
            </div>
          </Panel>
        </div>
      </section>

      {/* ── What a record looks like ──────────────────────────────── */}
      <section>
        <SectionHeader
          eyebrow="What a record looks like"
          title="The two key file formats"
          description="Every AC is a YAML file in docs/acceptance-criteria/. Every ticket is a Markdown file whose YAML frontmatter drives the supervisor. Reading these two formats unlocks every other view in Atlas."
        />
        <div className="grid gap-5 lg:grid-cols-2">
          <CodeBlock
            label="AC YAML — docs/acceptance-criteria/{component}/{id}.yaml"
            code={AC_YAML}
          />
          <CodeBlock
            label="Ticket frontmatter — tickets/00_inbox/{name}.md"
            code={TICKET_FRONTMATTER}
          />
        </div>
      </section>

      {/* ── Explore the live views ─────────────────────────────── */}
      <section>
        <SectionHeader
          eyebrow="Explore"
          title="Wherever a concept has a live view"
          description="Atlas reads the repo on every request. Each page below shows a concept from this guide as real, up-to-date data."
        />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {CROSS_LINKS.map((item) => {
            const Icon = item.icon;
            return (
              <Link key={item.href} href={item.href} className="group block">
                <Panel hover className="h-full">
                  <Icon className="mb-3 h-5 w-5 text-primary transition-transform duration-200 group-hover:scale-110" />
                  <p className="mb-1 text-sm font-semibold text-foreground">{item.label}</p>
                  <p className="text-xs leading-relaxed text-muted-foreground">{item.desc}</p>
                  <div className="mt-3 flex items-center gap-1 text-xs font-medium text-primary opacity-0 transition-opacity duration-200 group-hover:opacity-100">
                    Open <ArrowRight className="h-3 w-3" />
                  </div>
                </Panel>
              </Link>
            );
          })}
        </div>
      </section>
    </div>
  );
}
