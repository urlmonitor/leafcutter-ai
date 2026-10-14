import { PageHeader, EmptyState } from "@/components/ui/kit";
import { FlowsView } from "@/components/flows/flows-view";
import { DEFAULT_ENTRY_FLOW_ID } from "@/lib/flow-url";
import { Workflow } from "lucide-react";
import { loadFlowsViewData } from "./flows-data";

// The Flows view — living maps of the product-truth flows, each step coloured by
// the LIVE work_status of the acceptance criteria it implements. Server
// component: reads the repo via getFlows(), resolves every flow's mock data, and
// hands a serializable slice to the client <FlowsView> (which owns the flow
// selector + graph). buildFlowGraph runs client-side (pure) from these flows.
//
// The bare /flows address keeps its address and opens the default entry flow
// (UXP-591-1-i), with the same flat initial props as a canonical address.
export default function FlowsPage() {
  const { flows, mocks, screenTitles } = loadFlowsViewData();

  if (flows.length === 0) {
    return (
      <div className="flex flex-col">
        <PageHeader
          eyebrow="Product truth"
          title="Flows"
          description="Interactive maps of how a product actually behaves, step by step."
        />
        <EmptyState
          icon={<Workflow className="h-6 w-6" />}
          title="No flows found"
          hint="Add a *.flow.json under docs/product-truth/flows/ to see it here."
        />
      </div>
    );
  }

  const entry = flows.find((f) => f.id === DEFAULT_ENTRY_FLOW_ID) ?? flows[0];

  return (
    <FlowsView
      flows={flows}
      mocks={mocks}
      screenTitles={screenTitles}
      flowId={entry.id}
      crumbs={[entry.id]}
      filters={{ source: entry.source, kind: entry.kind, realization: "all" }}
      step={null}
    />
  );
}
