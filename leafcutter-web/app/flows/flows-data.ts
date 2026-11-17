import { getFlows, mockById, getScreenTitles } from "@/lib/data/flows";
import type { MockData } from "@/lib/data/types";

// Everything the client <FlowsView> needs, shared by the bare /flows page, the
// canonical /flows/<product>/<flow> page and its not-found boundary.
export function loadFlowsViewData() {
  const flows = getFlows();
  const mocks: Record<string, MockData | null> = {};
  for (const f of flows) {
    mocks[f.id] = f.mockDataRef ? mockById(f.mockDataRef) ?? null : null;
  }
  return { flows, mocks, screenTitles: getScreenTitles() };
}
