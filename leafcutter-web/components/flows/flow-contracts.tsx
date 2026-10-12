import React from "react";
import type { FlowContractBinding, FlowContractDefinition, FlowContractField, FlowIoContracts, FlowJsonType } from "@/lib/data/flow-contracts";

const TYPE_LABEL: Record<FlowJsonType, string> = {
  string: "Text", integer: "Integer", number: "Number", boolean: "Boolean",
  object: "Object", array: "Array", null: "Null",
};
const title = (key: string) => key.replace(/[_-]+/g, " ").replace(/^./, (letter) => letter.toUpperCase());
const hasDefault = (field: FlowContractField) => Object.prototype.hasOwnProperty.call(field, "default");

function FieldName({ path }: { path: string }) {
  const parts = path.slice(1).split("/").map((part) => part.replace(/~1/g, "/").replace(/~0/g, "~"));
  return <>
    <code className="break-words text-[11px]" title={`JSON pointer: ${path || "(root)"}`}>
      {path === "" ? "Whole value" : parts.join(" › ")}
    </code>
  </>;
}

function ContractTable({ binding, definition }: { binding: FlowContractBinding; definition: FlowContractDefinition }) {
  const defaults = binding.fields.some(hasDefault);
  const nested = binding.fields.some((field) => field.path.slice(1).includes("/"));
  const authority = definition.authority === "illustrative_design" ? "Proposed design"
    : definition.authority === "source_reviewed" ? "Source reviewed" : "Runtime contract";
  return <div className="min-w-0 rounded-lg border border-border/70 bg-background/30">
    <div className="space-y-1 border-b border-border/60 px-3 py-2.5">
      <h4 className="text-sm font-semibold text-foreground">{title(binding.contract)}</h4>
      <p className={`text-[11px] font-medium ${authority === "Runtime contract" ? "text-muted-foreground" : "text-warning"}`}>{authority}</p>
      {definition.note && <p className="break-words text-[11px] leading-relaxed text-muted-foreground">{definition.note}</p>}
    </div>
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left text-[11px]" aria-label={`${title(binding.contract)} fields`}>
        <thead className="text-muted-foreground"><tr>
          {["Field", "Type", "Required", ...(defaults ? ["Default"] : [])].map((label) => <th key={label} scope="col" className="px-3 py-2 font-medium">{label}</th>)}
        </tr></thead>
        <tbody>{binding.fields.map((field) => <tr key={field.path} className="border-t border-border/40 align-top">
          <td className="max-w-[12rem] px-3 py-2"><FieldName path={field.path} />
            {field.applies && <span className="mt-1 block text-[10px] text-muted-foreground">Payload schema: {title(field.applies)}</span>}
          </td>
          <td className="px-3 py-2">{field.types.map((type) => TYPE_LABEL[type]).join(" / ")}</td>
          <td className="px-3 py-2">{field.path.endsWith("/*") ? "Each present item/value" : field.required ? "Yes" : "No"}</td>
          {defaults && <td className="max-w-[8rem] break-words px-3 py-2 font-mono">{hasDefault(field) ? JSON.stringify(field.default) : "—"}</td>}
        </tr>)}</tbody>
      </table>
    </div>
    {nested && <p className="px-3 pb-2 text-[10px] leading-relaxed text-muted-foreground">Required applies within the field’s parent. * describes each present item/value; it does not require a nonempty container.</p>}
    <details className="border-t border-border/40 px-3 py-2 text-[10px] text-muted-foreground">
      <summary className="cursor-pointer">Contract source</summary>
      <div className="mt-1.5 space-y-1 break-all">
        <p>Contract key: <code>{binding.contract}</code></p>
        {definition.model && <p>Runtime model: <code>{definition.model}</code></p>}
        {definition.schema && <p>Schema: <code>{definition.schema}</code></p>}
      </div>
    </details>
  </div>;
}

/** Render only authored values: no label-string parsing, wrapper keys, or HTML execution. */
export function FlowContracts({ contracts, definitions }: {
  contracts: FlowIoContracts;
  definitions: Record<string, FlowContractDefinition>;
}) {
  return <div className="min-w-0 space-y-5">
    {contracts.not_applicable && <section className="rounded-lg border border-border/70 p-3 text-sm">
      <h4 className="mb-1 font-medium">No JSON handoff</h4>
      <p className="whitespace-pre-wrap break-words text-muted-foreground">{contracts.not_applicable}</p>
    </section>}
    {([['Inputs', contracts.consumes], ['Outputs', contracts.produces]] as const).map(([label, bindings]) => bindings && bindings.length > 0 &&
      <section key={label} className="space-y-2" aria-label={label}>
        <h3 className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{label}</h3>
        {bindings.map((binding, index) => <ContractTable key={`${binding.contract}:${index}`} binding={binding} definition={definitions[binding.contract]} />)}
      </section>)}
    {contracts.examples && contracts.examples.length > 0 && <section className="space-y-3" aria-label="JSON examples">
      <h3 className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">JSON examples</h3>
      {contracts.examples.map((example, index) => <figure key={index} className="min-w-0 rounded-lg border border-border/70 bg-background/40">
        <figcaption className="space-y-1 px-3 py-2.5 text-[11px]">
          <p className="font-medium text-foreground">{example.label}</p>
          <p className="text-muted-foreground">{title(example.contract)} · <span>{title(example.origin)}</span></p>
          <p className="text-muted-foreground">{example.mode === "projection" ? "Projection — selected fields, not a complete payload. Omitted required and defaulted fields remain in the linked contract." : "Full payload"}</p>
          {example.source && <p className="break-all text-muted-foreground">Source: <code>{example.source.path}{example.source.pointer ? `#${example.source.pointer}` : " (root)"}</code></p>}
        </figcaption>
        <pre className="max-h-80 overflow-auto border-t border-border/50 p-3 text-[11px] leading-relaxed"><code>{JSON.stringify(example.value, null, 2)}</code></pre>
      </figure>)}
    </section>}
    {contracts.missing_bindings?.map((gap, index) => <section key={index} className="space-y-1 rounded-lg border border-warning/40 bg-warning/5 p-3 text-[11px]">
      <p className="font-medium text-warning">Proposed — missing JSON binding</p>
      <h4 className="text-sm font-medium">{gap.name}</h4>
      <p className="text-muted-foreground">{gap.direction === "both" ? "Input and output" : gap.direction === "consumes" ? "Input" : "Output"}</p>
      <p className="whitespace-pre-wrap break-words">{gap.reason}</p>
      <p className="break-all text-muted-foreground">Source: <code>{gap.source}</code></p>
    </section>)}
  </div>;
}
