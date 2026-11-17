import { getAtlas } from "@/lib/data/atlas";
import { flowAppearancesByAc } from "@/lib/data/flows";
import { PageHeader } from "@/components/ui/kit";
import { AtlasExplorer } from "@/components/atlas/atlas-explorer";
import { fmt } from "@/lib/utils";

// The AC Atlas — the hero view. Server component: reads the live repo via
// getAtlas() and hands a serializable AC slice to the client graph explorer.
export default function AtlasPage({
  searchParams,
}: {
  searchParams?: Record<string, string | string[] | undefined>;
}) {
  const { acs, acCounts } = getAtlas();
  const componentCount = Object.keys(acCounts.byComponent).length;
  const flowIndex = flowAppearancesByAc();
  // /atlas?ac=<id> (the step drawer's criterion chips) opens that criterion; an unknown id is ignored.
  const ac = Array.isArray(searchParams?.ac) ? searchParams?.ac[0] : searchParams?.ac;

  return (
    <div className="flex flex-col">
      <PageHeader
        eyebrow="Acceptance criteria"
        title="AC Atlas"
        description="A living map of how acceptance criteria connect. Start in the component galaxy, then drill into any namespace to trace its dependency, contract, and coverage graph."
      >
        <div className="flex items-center gap-5">
          <div className="text-right">
            <div className="text-2xl font-semibold tabular-nums text-foreground">
              {fmt(acs.length)}
            </div>
            <div className="eyebrow">criteria</div>
          </div>
          <div className="text-right">
            <div className="text-2xl font-semibold tabular-nums text-foreground">
              {fmt(componentCount)}
            </div>
            <div className="eyebrow">components</div>
          </div>
        </div>
      </PageHeader>

      <AtlasExplorer acs={acs} flowIndex={flowIndex} initialAc={ac} />
    </div>
  );
}
