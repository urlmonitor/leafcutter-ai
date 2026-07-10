import "server-only";
import { repoPath, readFileSafe } from "./repo";
import type { AgentDef } from "./types";

function asArray(v: unknown): string[] {
  if (Array.isArray(v)) return v.map((x) => String(x)).filter(Boolean);
  if (v == null || v === "") return [];
  return [String(v)];
}

/** Load config/agent_registry.json — the phase/supervisor agent roster. */
export function loadAgents(): AgentDef[] {
  const raw = readFileSafe(repoPath("config", "agent_registry.json"));
  if (!raw) return [];
  let doc: { agents?: unknown[] };
  try {
    doc = JSON.parse(raw);
  } catch {
    return [];
  }
  const list = Array.isArray(doc?.agents) ? doc.agents : [];
  return list
    .map((a) => {
      const o = a as Record<string, unknown>;
      return {
        id: String(o.id ?? ""),
        name: String(o.name ?? o.id ?? ""),
        category: o.category ? String(o.category) : null,
        tier: o.tier ? String(o.tier) : null,
        role: o.role ? String(o.role) : null,
        description: String(o.description ?? ""),
        isTicketPhase: Boolean(o.is_ticket_phase),
        model: o.model ? String(o.model) : null,
        produces: o.produces ? String(o.produces) : null,
        spawnAllowlist: asArray(o.spawn_allowlist),
        spawnedBy: asArray(o.spawned_by),
        skillsUsed: asArray(o.skills_used),
        deprecated: Boolean(o.deprecated),
      } satisfies AgentDef;
    })
    .filter((a) => a.id);
}
