import { headers } from "next/headers";
import { notFound } from "next/navigation";
import { FlowsView } from "@/components/flows/flows-view";
import { RAW_FLOW_ID_HEADER } from "@/lib/flow-url";
import { loadFlowsViewData } from "../flows-data";

// The canonical flow address: /flows/<product>/<flow> opens that flow, selected
// and drawn. Anything that is not exactly a known two-segment id answers 404 —
// never a fallback to another flow.

// Middleware forwards the raw, still-encoded id. A percent-encoded '/' or a
// trailing slash decodes to the same params as the canonical address, so the
// raw id is the only way to tell them apart. Absent outside a real request.
function rawIdFromRequest(): string | null {
  try {
    return headers().get(RAW_FLOW_ID_HEADER);
  } catch {
    return null;
  }
}

export default function FlowPage({
  params,
}: {
  params: { id: string[] };
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  const segments = params.id;
  if (segments.length !== 2 || segments.some((s) => s === "" || s.includes("/"))) notFound();

  const id = segments.join("/");
  const raw = rawIdFromRequest();
  if (raw !== null && raw !== id) notFound();

  const { flows, mocks, screenTitles } = loadFlowsViewData();
  const flow = flows.find((f) => f.id === id);
  if (!flow) notFound();

  return (
    <FlowsView
      flows={flows}
      mocks={mocks}
      screenTitles={screenTitles}
      flowId={flow.id}
      crumbs={[flow.id]}
      filters={{ source: flow.source, kind: flow.kind, realization: "all" }}
      step={null}
    />
  );
}
