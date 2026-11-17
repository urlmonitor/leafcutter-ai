"use client";

import * as React from "react";
import { usePathname } from "next/navigation";
import type { Flow, MockData } from "@/lib/data/types";
import type { FinderState } from "@/lib/flow-finder/types";
import { FLOWS_TITLE } from "@/lib/flow-finder/titles";
import { FlowsView } from "../flows-view";
import { pushFlowAddress } from "../flow-history";
import { FinderPane } from "./finder-pane";
import { useDocumentTitle } from "./use-document-title";

/**
 * The client shell app/flows/page.tsx mounts (UXP-617-2-i): the finder, until a
 * result is opened. Opening pushes the flow's address with native history.pushState
 * (never the router) and swaps in the Flows view, which then owns Back and Forward
 * (a pop onto exactly /flows returns the finder, as it was left).
 */
export function FlowsShell({
  flows,
  mocks,
  screenTitles,
  initial,
}: {
  flows: Flow[];
  mocks: Record<string, MockData | null>;
  screenTitles: Record<string, string>;
  initial: FinderState;
}) {
  const [opened, setOpened] = React.useState<{ flow: Flow; step: string | null } | null>(null);
  useDocumentTitle(opened ? null : FLOWS_TITLE);

  // An App Router navigation to /flows (the sidebar link, any /flows?q=... link) keeps this
  // instance mounted: it delivers a new `initial`, or moves the pathname back to /flows.
  // Either way the address names the finder, so drop the opened flow and show it.
  const pathname = usePathname();
  React.useEffect(() => setOpened(null), [initial]);
  React.useEffect(() => {
    if (pathname === "/flows") setOpened(null);
  }, [pathname]);

  if (opened) {
    const { flow, step } = opened;
    return (
      <FlowsView
        key={`${flow.id}?${step ?? ""}`}
        flows={flows}
        mocks={mocks}
        screenTitles={screenTitles}
        flowId={flow.id}
        crumbs={[flow.id]}
        filters={{ source: flow.source, kind: flow.kind, realization: "all" }}
        step={step}
      />
    );
  }

  const open = (flowId: string, step: string | null) => {
    const flow = flows.find((f) => f.id === flowId);
    if (!flow) return;
    pushFlowAddress(flow.id, { crumbs: [flow.id], filters: { source: flow.source, kind: flow.kind, realization: "all" } }, step);
    setOpened({ flow, step });
  };
  return <FinderPane flows={flows} screenTitles={screenTitles} initial={initial} onOpen={open} />;
}
