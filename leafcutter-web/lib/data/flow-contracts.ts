/** Authored contract metadata. Keep JSON values and pointer paths literal. */
export type FlowJsonValue = null | boolean | number | string | FlowJsonValue[] | { [key: string]: FlowJsonValue };
export type FlowJsonType = "object" | "array" | "string" | "integer" | "number" | "boolean" | "null";

export interface FlowContractDefinition {
  model?: string;
  schema?: string;
  authority?: "runtime" | "source_reviewed" | "illustrative_design";
  note?: string;
}
export interface FlowContractField {
  path: string;
  types: FlowJsonType[];
  required: boolean;
  default?: FlowJsonValue;
  applies?: string;
}
export interface FlowContractBinding { contract: string; fields: FlowContractField[] }
export interface FlowContractExample {
  contract: string;
  mode: "full" | "projection";
  origin: "observed" | "illustrative" | "reconstructed";
  label: string;
  source?: { path: string; pointer: string };
  value: FlowJsonValue;
}
export interface FlowMissingBinding {
  name: string;
  direction: "consumes" | "produces" | "both";
  reason: string;
  source: string;
}
export interface FlowIoContracts {
  consumes?: FlowContractBinding[];
  produces?: FlowContractBinding[];
  examples?: FlowContractExample[];
  missing_bindings?: FlowMissingBinding[];
  not_applicable?: string;
}

const JSON_TYPES = new Set(["object", "array", "string", "integer", "number", "boolean", "null"]);
const own = (value: object, key: string) => Object.prototype.hasOwnProperty.call(value, key);
const record = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === "object" && !Array.isArray(value);
const text = (value: unknown): value is string => typeof value === "string" && value.trim().length > 0;
const pointer = (value: unknown): value is string => typeof value === "string" && (value === "" || value.startsWith("/"));
const only = (value: Record<string, unknown>, keys: string[]) => Object.keys(value).every((key) => keys.includes(key));

function jsonValue(value: unknown): value is FlowJsonValue {
  return value === null || typeof value === "string" || typeof value === "boolean"
    || (typeof value === "number" && Number.isFinite(value))
    || (Array.isArray(value) && value.every(jsonValue))
    || (record(value) && Object.values(value).every(jsonValue));
}

/** Shape checks protect the view; canonical schema/model validation remains in the CLI. */
export function parseContractDefinitions(value: unknown): Record<string, FlowContractDefinition> | undefined {
  if (!record(value) || !Object.values(value).every((item) => record(item)
    && only(item, ["model", "schema", "authority", "note"])
    && (text(item.model) || text(item.schema))
    && (!own(item, "model") || text(item.model)) && (!own(item, "schema") || text(item.schema))
    && (!own(item, "note") || text(item.note))
    && (!own(item, "authority") || (typeof item.authority === "string" && ["runtime", "source_reviewed", "illustrative_design"].includes(item.authority)))
    && (!item.authority || item.authority === "runtime" || text(item.note)))) return undefined;
  return value as Record<string, FlowContractDefinition>;
}

/** Accept metadata only when every displayed reference resolves; otherwise the drawer keeps the legacy label fallback. */
export function parseIoContracts(value: unknown, definitions: unknown): FlowIoContracts | undefined {
  if (!record(value)) return undefined;
  if (own(value, "not_applicable")) {
    return only(value, ["not_applicable"]) && text(value.not_applicable) ? value as FlowIoContracts : undefined;
  }
  if (!only(value, ["consumes", "produces", "examples", "missing_bindings"])) return undefined;
  const defs = parseContractDefinitions(definitions);
  const known = (key: unknown) => text(key) && defs !== undefined && own(defs, key);
  const field = (item: unknown) => record(item) && pointer(item.path) && Array.isArray(item.types)
    && item.types.length > 0 && item.types.every((type) => typeof type === "string" && JSON_TYPES.has(type))
    && typeof item.required === "boolean" && (!own(item, "default") || jsonValue(item.default))
    && (!own(item, "applies") || known(item.applies));
  const bindings = (items: unknown): items is FlowContractBinding[] => Array.isArray(items)
    && items.every((item) => record(item) && known(item.contract) && Array.isArray(item.fields)
      && item.fields.length > 0 && item.fields.every(field));
  const examples = (items: unknown): items is FlowContractExample[] => Array.isArray(items) && items.length > 0
    && items.every((item) => record(item) && known(item.contract) && typeof item.mode === "string" && ["full", "projection"].includes(item.mode)
      && typeof item.origin === "string" && ["observed", "illustrative", "reconstructed"].includes(item.origin)
      && text(item.label) && own(item, "value") && jsonValue(item.value)
      && (!own(item, "source") || (record(item.source) && text(item.source.path) && pointer(item.source.pointer)))
      && (item.origin !== "observed" || own(item, "source")));
  const hasWire = ["consumes", "produces", "examples"].some((key) => own(value, key));
  if (hasWire && (!bindings(value.consumes) || !bindings(value.produces) || !examples(value.examples)
    || value.consumes.length + value.produces.length === 0)) return undefined;
  const gaps = value.missing_bindings;
  if (own(value, "missing_bindings") && (!Array.isArray(gaps) || gaps.length === 0 || !gaps.every((gap) => record(gap)
    && text(gap.name) && text(gap.reason) && text(gap.source)
    && typeof gap.direction === "string" && ["consumes", "produces", "both"].includes(gap.direction)))) return undefined;
  return hasWire || own(value, "missing_bindings") ? value as FlowIoContracts : undefined;
}
