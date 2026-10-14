import { PageHeader, EmptyState } from "@/components/ui/kit";
import { FinderScreen } from "@/components/flows/finder/finder-screen";
import { buildFinderHref, parseFinderQuery } from "@/lib/flow-finder/address";
import { buildFinderIndex } from "@/lib/flow-finder/build-index";
import { Workflow } from "lucide-react";
import { getFlows, getScreenTitles } from "@/lib/data/flows";

// The Flows view opens on the FINDER (UXP-617-1): one search box and counted
// filters over every flow, results grouped by flow. Bare /flows draws no flow;
// a flow opens at /flows/<product>/<flow>[?step=<id>]. Server component: it reads
// the finder state from the address, builds the index from the same flows the
// Flows view loads, and renders the first paint (summary and results included).
// The client <FinderScreen> recomputes from that index on every edit.
export default async function FlowsPage({
  searchParams = {},
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}) {
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

  const initial = parseFinderQuery(searchParams);
  const index = buildFinderIndex(flows, getScreenTitles());

  return (
    <div className="flex flex-col">
      <PageHeader
        eyebrow="Atlas · Flows"
        title="Flows"
        description="Search and filter every flow by name, step, field, AC, entity or screen."
      />
      {/* keyed by the address, so following a link to another finder address starts from it */}
      <FinderScreen key={buildFinderHref(initial)} index={index} initial={initial} />
    </div>
  );
}
