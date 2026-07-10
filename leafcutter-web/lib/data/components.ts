import "server-only";
import { repoPath, readFileSafe } from "./repo";
import type { Component } from "./types";

/** Load docs/components.json — the code/architecture component registry. */
export function loadComponents(): Component[] {
  const raw = readFileSafe(repoPath("docs", "components.json"));
  if (!raw) return [];
  let doc: { components?: Record<string, unknown> };
  try {
    doc = JSON.parse(raw);
  } catch {
    return [];
  }
  const map = doc?.components ?? {};
  return Object.values(map)
    .map((c) => {
      const o = c as Record<string, unknown>;
      return {
        id: String(o.id ?? ""),
        name: String(o.name ?? o.id ?? ""),
        type: String(o.type ?? "other"),
        description: String(o.description ?? ""),
        detailRef: o.detail_ref ? String(o.detail_ref) : null,
        status: String(o.status ?? "active"),
        primaryCode: Array.isArray(o.primary_code)
          ? (o.primary_code as unknown[]).map((x) => String(x))
          : [],
      } satisfies Component;
    })
    .filter((c) => c.id)
    .sort((a, b) => a.name.localeCompare(b.name));
}

/** Distinct component types present, sorted. */
export function componentTypes(components: Component[]): string[] {
  return Array.from(new Set(components.map((c) => c.type))).sort();
}
