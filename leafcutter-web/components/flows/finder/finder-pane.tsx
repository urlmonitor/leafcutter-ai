"use client";

import * as React from "react";
import { PageHeader } from "@/components/ui/kit";
import { buildFinderHref } from "@/lib/flow-finder/address";
import { buildFinderIndex } from "@/lib/flow-finder/build-index";
import type { FinderState } from "@/lib/flow-finder/types";
import type { Flow } from "@/lib/data/types";
import { FinderScreen } from "./finder-screen";

/** The finder as the Flows view shows it when Back or Forward lands on exactly /flows. */
export function FinderPane({
  flows,
  screenTitles,
  initial,
}: {
  flows: Flow[];
  screenTitles: Record<string, string>;
  initial: FinderState;
}) {
  const index = React.useMemo(() => buildFinderIndex(flows, screenTitles), [flows, screenTitles]);
  return (
    <div className="flex flex-col">
      <PageHeader
        eyebrow="Atlas · Flows"
        title="Flows"
        description="Search and filter every flow by name, step, field, AC, entity or screen."
      />
      <FinderScreen key={buildFinderHref(initial)} index={index} initial={initial} />
    </div>
  );
}
