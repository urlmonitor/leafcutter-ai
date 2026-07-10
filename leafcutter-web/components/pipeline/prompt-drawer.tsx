"use client";

/**
 * Slide-in prompt inspector for a single pipeline agent. Lets you toggle the
 * data SOURCE (Mock / Real) and the VIEW (Template / Inputs / Assembled):
 *   - Template  = the agent's raw system prompt + its declared input contract.
 *   - Inputs    = those slots resolved to concrete values for the chosen example.
 *   - Assembled = the final prompt with the resolved context injected.
 * Assembly is pure (lib/prompt-render), so switching source recomputes instantly.
 */
import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X, Cpu, FileCode2, ListTree, Sparkles, Check, Copy, CircleAlert, Wrench } from "lucide-react";
import { Badge } from "@/components/ui/kit";
import { cn } from "@/lib/utils";
import type {
  AgentDef,
  AgentTemplate,
  FlowSource,
  PromptExample,
  ResolvedInput,
} from "@/lib/data/types";
import {
  assemblePrompt,
  effectiveBundle,
  hasPerAgentOverride,
  resolveInputs,
} from "@/lib/prompt-render";

const MODEL_LABEL: Record<string, string> = { opus: "Opus", sonnet: "Sonnet", haiku: "Haiku" };

type View = "template" | "inputs" | "assembled";

function Segmented<T extends string>({
  options,
  value,
  onChange,
  render,
}: {
  options: T[];
  value: T;
  onChange: (next: T) => void;
  render: (opt: T) => React.ReactNode;
}) {
  return (
    <div className="inline-flex flex-wrap gap-1 rounded-lg border border-border/70 bg-card/60 p-1">
      {options.map((opt) => {
        const active = opt === value;
        return (
          <button
            key={opt}
            type="button"
            onClick={() => onChange(opt)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
              active
                ? "bg-primary/15 text-foreground"
                : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
            )}
          >
            {render(opt)}
          </button>
        );
      })}
    </div>
  );
}

function SlotList({ template }: { template: AgentTemplate }) {
  const groups: { title: string; items: { name: string; detail: string; required: boolean }[] }[] = [
    {
      title: "Inputs",
      items: template.inputs.map((s) => ({ name: s.name, detail: s.description || s.type, required: s.required })),
    },
    {
      title: "Pre-flight reads",
      items: template.preFlightReads.map((s) => ({
        name: s.source,
        detail: s.condition ?? "read at flight time",
        required: s.required,
      })),
    },
    {
      title: "Config keys",
      items: template.configKeys.map((s) => ({ name: s.key, detail: s.description, required: s.required })),
    },
  ].filter((g) => g.items.length > 0);

  if (groups.length === 0) {
    return <p className="text-xs text-muted-foreground">This agent declares no input slots.</p>;
  }

  return (
    <div className="space-y-3">
      {groups.map((g) => (
        <div key={g.title}>
          <div className="mb-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">
            {g.title}
          </div>
          <div className="space-y-1">
            {g.items.map((it) => (
              <div
                key={g.title + it.name}
                className="rounded-md border border-border/60 bg-background/40 px-2.5 py-1.5"
              >
                <div className="flex items-center gap-2">
                  <code className="font-mono text-[11px] text-primary">{it.name}</code>
                  {it.required ? (
                    <span className="rounded bg-warning/15 px-1 text-[9px] font-medium uppercase text-warning">
                      required
                    </span>
                  ) : (
                    <span className="rounded bg-muted/50 px-1 text-[9px] font-medium uppercase text-muted-foreground">
                      optional
                    </span>
                  )}
                </div>
                {it.detail && <p className="mt-0.5 text-[11px] leading-snug text-muted-foreground">{it.detail}</p>}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function SkillList({ template }: { template: AgentTemplate }) {
  if (template.skills.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        This agent declares no project skills — it relies on its tools alone.
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-1.5">
      {template.skills.map((s) => (
        <div
          key={s.name}
          className="rounded-md border border-border/60 bg-background/40 px-2.5 py-1.5"
        >
          <code className="font-mono text-[11px] text-info">/{s.name}</code>
          {s.note && (
            <p className="mt-0.5 text-[11px] leading-snug text-muted-foreground">{s.note}</p>
          )}
        </div>
      ))}
    </div>
  );
}

function InputRow({ row }: { row: ResolvedInput }) {
  const multiline = row.value.includes("\n");
  return (
    <div className="rounded-md border border-border/60 bg-background/40 px-2.5 py-1.5">
      <div className="flex items-center gap-2">
        <code className="font-mono text-[11px] text-primary">{row.name}</code>
        <span className="text-[9px] uppercase tracking-wide text-muted-foreground">{row.detail}</span>
        {!row.resolved && <CircleAlert className="h-3 w-3 text-warning" aria-label="unresolved" />}
      </div>
      {multiline ? (
        <pre className="mt-1 max-h-56 overflow-auto whitespace-pre-wrap break-words rounded bg-background/60 p-2 font-mono text-[11px] leading-relaxed text-foreground/90">
          {row.value}
        </pre>
      ) : (
        <p
          className={cn(
            "mt-0.5 break-words font-mono text-[11px] leading-snug",
            row.resolved ? "text-foreground/90" : "italic text-muted-foreground",
          )}
        >
          {row.value}
        </p>
      )}
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = React.useState(false);
  const onCopy = React.useCallback(() => {
    void navigator.clipboard?.writeText(text).then(
      () => {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1500);
      },
      () => setCopied(false),
    );
  }, [text]);
  return (
    <button
      type="button"
      onClick={onCopy}
      className="inline-flex items-center gap-1 rounded-md border border-border/70 px-2 py-1 text-[11px] text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
    >
      {copied ? <Check className="h-3 w-3 text-success" /> : <Copy className="h-3 w-3" />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

export function PromptDrawer({
  agent,
  template,
  examples,
  onClose,
}: {
  agent: AgentDef | null;
  template: AgentTemplate | null;
  examples: Record<FlowSource, PromptExample>;
  onClose: () => void;
}) {
  const [source, setSource] = React.useState<FlowSource>("mock");
  const [view, setView] = React.useState<View>("template");

  const agentId = agent?.id ?? "";
  const example = examples[source];
  const bundle = React.useMemo(
    () => (agent ? effectiveBundle(example, agentId) : null),
    [example, agentId, agent],
  );
  const rows = React.useMemo(
    () => (template && bundle ? resolveInputs(template, bundle) : []),
    [template, bundle],
  );
  const assembled = React.useMemo(
    () => (template && bundle ? assemblePrompt(template, bundle) : ""),
    [template, bundle],
  );
  const overridden = agent ? hasPerAgentOverride(example, agentId) : false;

  return (
    <AnimatePresence>
      {agent && (
        <>
          <motion.div
            key="scrim"
            className="fixed inset-0 z-40 bg-background/50 backdrop-blur-[2px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.aside
            key="drawer"
            className="fixed right-0 top-0 z-50 flex h-full w-full max-w-2xl flex-col border-l border-border/80 bg-card/95 shadow-2xl backdrop-blur-md"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 320 }}
          >
            {/* header */}
            <div className="flex items-start justify-between gap-3 border-b border-border/70 p-5">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-semibold leading-snug text-foreground">{agent.name}</h3>
                  {agent.model && (
                    <span className="inline-flex items-center gap-1 rounded-md border border-border/70 bg-secondary/40 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                      <Cpu className="h-2.5 w-2.5" />
                      {MODEL_LABEL[agent.model] ?? agent.model}
                    </span>
                  )}
                  {template?.produces && (
                    <Badge>produces: {template.produces}</Badge>
                  )}
                </div>
                <div className="mt-0.5 font-mono text-[11px] text-muted-foreground">{agent.id}</div>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="shrink-0 rounded-md border border-border/70 p-1.5 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {template ? (
              <>
                {/* controls */}
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/70 px-5 py-3">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground/80">
                      Source
                    </span>
                    <Segmented<FlowSource>
                      options={["mock", "real"]}
                      value={source}
                      onChange={setSource}
                      render={(o) => <span>{o === "mock" ? "Mock" : "Real"}</span>}
                    />
                  </div>
                  <Segmented<View>
                    options={["template", "inputs", "assembled"]}
                    value={view}
                    onChange={setView}
                    render={(o) => (
                      <span className="inline-flex items-center gap-1">
                        {o === "template" && <FileCode2 className="h-3 w-3" />}
                        {o === "inputs" && <ListTree className="h-3 w-3" />}
                        {o === "assembled" && <Sparkles className="h-3 w-3" />}
                        {o === "template" ? "Template" : o === "inputs" ? "Inputs" : "Assembled"}
                      </span>
                    )}
                  />
                </div>

                {/* example banner (Inputs / Assembled) */}
                {view !== "template" && bundle && (
                  <div className="flex items-center gap-2 border-b border-border/60 bg-background/30 px-5 py-2 text-[11px] text-muted-foreground">
                    <span>
                      {source === "mock" ? "Mock example" : "Live example"}:{" "}
                      <span className="font-medium text-foreground">{bundle.label}</span>
                    </span>
                    {overridden && (
                      <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                        per-agent
                      </span>
                    )}
                  </div>
                )}

                {/* body */}
                <div className="flex-1 overflow-y-auto p-5">
                  {view === "template" && (
                    <div className="space-y-5">
                      <div>
                        <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">
                          System prompt (raw template)
                        </div>
                        <pre className="max-h-[45vh] overflow-auto whitespace-pre-wrap break-words rounded-lg border border-border/70 bg-background/50 p-3 font-mono text-[11px] leading-relaxed text-foreground/90">
                          {template.systemPrompt}
                        </pre>
                      </div>
                      <div>
                        <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">
                          Declared input contract
                        </div>
                        <SlotList template={template} />
                      </div>
                      <div>
                        <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">
                          <Wrench className="h-3 w-3" />
                          Skills the agent may use
                        </div>
                        <SkillList template={template} />
                      </div>
                    </div>
                  )}

                  {view === "inputs" && (
                    <div className="space-y-2">
                      {rows.length === 0 ? (
                        <p className="text-xs text-muted-foreground">
                          This agent declares no input slots — its prompt is the system prompt alone.
                        </p>
                      ) : (
                        rows.map((r) => <InputRow key={r.kind + r.name} row={r} />)
                      )}
                    </div>
                  )}

                  {view === "assembled" && (
                    <div>
                      <div className="mb-1.5 flex items-center justify-between">
                        <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">
                          Final prompt for {source === "mock" ? "the mock" : "this live"} example
                        </span>
                        <CopyButton text={assembled} />
                      </div>
                      <pre className="overflow-auto whitespace-pre-wrap break-words rounded-lg border border-border/70 bg-background/50 p-3 font-mono text-[11px] leading-relaxed text-foreground/90">
                        {assembled}
                      </pre>
                    </div>
                  )}
                </div>
              </>
            ) : (
              /* no template on disk (e.g. worktree-agent) */
              <div className="flex-1 space-y-3 overflow-y-auto p-5">
                <div className="flex items-center gap-2 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning">
                  <CircleAlert className="h-4 w-4 shrink-0" />
                  No agent template found at templates/agents/{agent.id}.md — this agent has no
                  inspectable prompt in this repo.
                </div>
                {agent.description && (
                  <div>
                    <div className="mb-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/80">
                      Registry description
                    </div>
                    <p className="text-sm leading-relaxed text-foreground/90">{agent.description}</p>
                  </div>
                )}
              </div>
            )}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
