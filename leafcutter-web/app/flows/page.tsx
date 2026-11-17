import { PageHeader, EmptyState } from "@/components/ui/kit";
import { FlowsShell } from "@/components/flows/finder/flows-shell";
import { parseFinderQuery } from "@/lib/flow-finder/address";
import { FLOWS_TITLE } from "@/lib/flow-finder/titles";
import { Workflow } from "lucide-react";
import { loadFlowsViewData } from "./flows-data";

export const metadata = { title: { absolute: FLOWS_TITLE } };

// The Flows view opens on the FINDER (UXP-617-1): one search box and counted
// filters over every flow, results grouped by flow. Bare /flows draws no flow;
// a flow opens at /flows/<product>/<flow>[?step=<id>]. Server component: it reads
// the finder state from the address and renders the first paint (summary and
// results included). The client <FlowsShell> recomputes on every edit and opens a
// result in place with native history (UXP-617-2, UXP-617-2-i).
export default async function FlowsPage({
  searchParams = {},
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}) {
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

  return <FlowsShell flows={flows} mocks={mocks} screenTitles={screenTitles} initial={parseFinderQuery(searchParams)} />;
}
