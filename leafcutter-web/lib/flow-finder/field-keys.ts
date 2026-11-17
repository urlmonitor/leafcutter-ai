/**
 * Field keys of a step's io_contracts (UXP-617-1-i): <contract>.<JSON-pointer
 * segments joined by '.'>, just <contract> for the whole value. The label reads
 * as the drawer's Inputs/Outputs tables do: the contract title, then the segments
 * joined by ' › ' ('Whole value' for the root).
 */
import type { FlowContractBinding } from "@/lib/data/flow-contracts";

/** "decision_record" -> "Decision record" (underscores and hyphens as spaces). */
export const contractTitle = (key: string) =>
  key.replace(/[_-]+/g, " ").replace(/^./, (c) => c.toUpperCase());

/** The segments of a JSON pointer, unescaped ("" -> no segments). */
export function pointerSegments(path: string): string[] {
  if (path === "") return [];
  return path
    .slice(1)
    .split("/")
    .map((s) => s.replace(/~1/g, "/").replace(/~0/g, "~"));
}

export interface FieldRef {
  key: string;
  label: string;
}

/** Every field the bindings name, once each and in stored order. */
export function fieldRefs(bindings: FlowContractBinding[] | undefined): FieldRef[] {
  const seen = new Set<string>();
  const out: FieldRef[] = [];
  for (const binding of bindings ?? []) {
    for (const field of binding.fields) {
      const segs = pointerSegments(field.path);
      const key = [binding.contract, ...segs].join(".");
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({
        key,
        label: `${contractTitle(binding.contract)} › ${segs.length ? segs.join(" › ") : "Whole value"}`,
      });
    }
  }
  return out;
}
