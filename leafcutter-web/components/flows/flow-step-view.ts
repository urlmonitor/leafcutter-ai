/** Shared drawer view model and the pure projection from a loaded flow. */
import type { FlowContractDefinition, FlowIoContracts } from "@/lib/data/flow-contracts";
import type { AcRef, Flow, FlowRealization, FlowScenario, WorkStatus } from "@/lib/data/types";

export interface StepView {
  id: string;
  label: string;
  human: string;
  screen: string | null;
  screenTitle?: string | null;    // resolved mockup title for the screen slug
  realization?: FlowRealization;  // does the parent flow's system exist yet
  variant: "step" | "branch";
  condition?: string;
  status: WorkStatus;
  agent?: string | null;
  produces?: string[];
  consumes?: string[];
  ioContracts?: FlowIoContracts;
  contractDefinitions?: Record<string, FlowContractDefinition>;
  reads: string[];
  writes: string[];
  acs: AcRef[];
  scenarios: FlowScenario[];
  expandsTo?: string | null;      // child flow id this step drills into
  expandsToName?: string | null;  // resolved child flow name (null if unresolved)
}

/** Preserve identical contract metadata for ordinary steps and conditional branches. */
export function buildStepViews(
  flow: Flow,
  screenTitleFor: (slug: string | null) => string | null,
  nameFor: (id: string | null) => string | null,
): Map<string, StepView> {
  const m = new Map<string, StepView>();
  for (const s of flow.steps) {
    m.set(`step:${s.id}`, {
      id: s.id,
      label: s.label,
      human: s.human,
      screen: s.screen,
      screenTitle: screenTitleFor(s.screen),
      realization: flow.realization,
      variant: "step",
      status: s.implStatus,
      agent: s.agent,
      produces: s.produces,
      consumes: s.consumes,
      ioContracts: s.ioContracts,
      contractDefinitions: flow.contractDefinitions,
      reads: s.reads,
      writes: s.writes,
      acs: s.acs,
      scenarios: flow.scenarios.filter((sc) => sc.for === s.id),
      expandsTo: s.expandsTo,
      expandsToName: nameFor(s.expandsTo),
    });
  }
  for (const b of flow.branches) {
    m.set(`step:${b.id}`, {
      id: b.id,
      label: b.label,
      human: b.human,
      screen: b.screen,
      screenTitle: screenTitleFor(b.screen),
      realization: flow.realization,
      variant: "branch",
      condition: b.condition,
      status: b.implStatus,
      agent: b.agent,
      produces: b.produces,
      consumes: b.consumes,
      ioContracts: b.ioContracts,
      contractDefinitions: flow.contractDefinitions,
      reads: b.reads,
      writes: b.writes,
      acs: b.acs,
      scenarios: flow.scenarios.filter((sc) => sc.for === b.id),
      expandsTo: b.expandsTo,
      expandsToName: nameFor(b.expandsTo),
    });
  }
  return m;
}
