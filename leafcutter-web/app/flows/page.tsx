import { getFlows, mockById, getScreenTitles } from "@/lib/data/flows";
import { PageHeader, EmptyState } from "@/components/ui/kit";
import { FlowsView } from "@/components/flows/flows-view";
import type { MockData } from "@/lib/data/types";
import { Workflow } from "lucide-react";

// The Flows view — living maps of the product-truth flows, each step coloured by
// the LIVE work_status of the acceptance criteria it implements. Server
// component: reads the repo via getFlows(), resolves every flow's mock data, and
// hands a serializable slice to the client <FlowsView> (which owns the flow
// selector + graph). buildFlowGraph runs client-side (pure) from these flows.
export default function FlowsPage() {
  const flows = getFlows();

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

  const mocks: Record<string, MockData | null> = {};
  for (const f of flows) {
    mocks[f.id] = f.mockDataRef ? mockById(f.mockDataRef) ?? null : null;
  }

  const screenTitles = getScreenTitles();

  return <FlowsView flows={flows} mocks={mocks} screenTitles={screenTitles} />;
}
