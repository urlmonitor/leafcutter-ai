/**
 * Finder search (UXP-617-1-i). One tokenizer serves the query and every target:
 * lower-cased, split at every character that is not a letter or a digit, so
 * snake_case, kebab-case, dotted field keys and AC ids split. The one-target rule:
 * a target matches when EVERY query word starts a word of that ONE target; targets
 * are never pooled, so words found in two different targets do not match.
 */
import type { FinderFlow, FinderIndex, FinderNode } from "./types";

export const wordsOf = (s: string): string[] => s.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? [];

export const startsAWord = (queryWords: string[], targetWords: string[]): boolean =>
  queryWords.every((q) => targetWords.some((w) => w.startsWith(q)));

/** A searchable target and the reason shown on a step row that matched it. */
export interface Target {
  reason: string;
  words: string[];
}

const nodeCache = new WeakMap<FinderNode, Target[]>();
const flowCache = new WeakMap<FinderFlow, Target[]>();

const target = (reason: string, text: string): Target => ({ reason, words: wordsOf(text) });

/** A step's or branch's targets, highest-ranked reason first. */
export function nodeTargets(index: FinderIndex, node: FinderNode): Target[] {
  const hit = nodeCache.get(node);
  if (hit) return hit;
  const fieldLabel = (key: string) => index.fields[key] ?? key;
  const out: Target[] = [
    target(node.nodeKind === "branch" ? "Branch label" : "Step label", node.label),
    ...node.acIds.map((id) => target(`AC ${id}`, id)),
    ...node.produces.map((k) => target(`Output · ${fieldLabel(k)}`, k)),
    ...node.uses.map((k) => target(`Input · ${fieldLabel(k)}`, k)),
    ...(node.screen ? [target(`Screen · ${node.screen.title}`, `${node.screen.id} ${node.screen.title}`)] : []),
    ...node.entities.map((e) => target(`Entity · ${e}`, e)),
    target("Text", `${node.text} ${node.condition ?? ""}`),
  ];
  nodeCache.set(node, out);
  return out;
}

/** The reason of the highest-ranked target the query matched, or null. */
export function nodeMatch(index: FinderIndex, node: FinderNode, queryWords: string[]): string | null {
  return nodeTargets(index, node).find((t) => startsAWord(queryWords, t.words))?.reason ?? null;
}

/** A flow's own targets: its name with its id, then each declared entity. */
export function flowTargets(flow: FinderFlow): Target[] {
  const hit = flowCache.get(flow);
  if (hit) return hit;
  const out = [target("Name", `${flow.name} ${flow.id}`), ...flow.declaredEntities.map((e) => target(`Entity · ${e}`, e))];
  flowCache.set(flow, out);
  return out;
}

/** 'Name' or 'Entity · <name>' when the query matches the flow itself, else null. */
export function flowMatch(flow: FinderFlow, queryWords: string[]): string | null {
  return flowTargets(flow).find((t) => startsAWord(queryWords, t.words))?.reason ?? null;
}
