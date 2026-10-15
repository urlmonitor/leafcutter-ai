/** Page titles of the Flows routes (UXP-617-3-ii): server metadata and the client's document.title read these. */
export const FLOWS_TITLE = "Flows · Leafcutter Atlas";
export const NOT_FOUND_TITLE = `Flow not found · ${FLOWS_TITLE}`;
export const flowTitle = (flowName: string) => `${flowName} · ${FLOWS_TITLE}`;
