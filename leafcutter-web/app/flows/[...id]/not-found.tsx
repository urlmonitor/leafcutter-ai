import { headers } from "next/headers";
import { FlowsView } from "@/components/flows/flows-view";
import { RAW_FLOW_ID_HEADER, flowNotFoundNotice } from "@/lib/flow-url";
import { loadFlowsViewData } from "../flows-data";

// 'Flow not found' (404): the Flows view with the selector at Real / User, no
// flow drawn, and a notice quoting the id exactly as requested. The raw id comes
// from the header middleware forwards; it is rendered as text only.
export default function FlowNotFound() {
  const rawId = headers().get(RAW_FLOW_ID_HEADER) ?? "";
  const { flows, mocks, screenTitles } = loadFlowsViewData();

  return (
    <FlowsView
      flows={flows}
      mocks={mocks}
      screenTitles={screenTitles}
      flowId={null}
      crumbs={[]}
      filters={{ source: "real", kind: "user", realization: "all" }}
      step={null}
      notice={flowNotFoundNotice(rawId)}
    />
  );
}
