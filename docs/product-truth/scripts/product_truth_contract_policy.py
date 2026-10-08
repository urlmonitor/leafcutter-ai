"""Non-optional retrieval-needs handoffs, in addition to universal node documentation.

GOAL: Every flow node needs checked metadata; the runtime experiment also pins its own flow.
BUSINESS CONTEXT: Deleting documentation or changing a realization flag cannot evade the gate.
ARCHITECTURE: A repository capability marker pins reviewed runtime identities without legacy exemptions.
"""
PINNED_FLOW = "leafcutter/retrieval-needs-interpretation"
CAPABILITY_MARKER = "integrations/retrieval_needs_llm.py"
PINNED_MODELS = {
    "prepare-request": {"retrieval_needs_request", "task_input", "scope", "actor"},
    "start-run": {"task_input", "capability_invocation"},
    "wait-for-host": {"capability_invocation", "run_envelope", "host_work_request"},
    "interpret": {"retrieval_needs_request", "retrieval_needs_output", "host_work_request"},
    "submit": {"retrieval_needs_output", "interaction_submission", "host_work_request"},
    "validate": {"interaction_submission", "capability_invocation"},
    "accept-and-resume": {"interaction_submission", "submission_record"},
    "normalize-needs": {"interaction_submission", "retrieval_needs_request", "retrieval_needs_output"},
    "return-needs": {"retrieval_needs_output", "capability_result", "run_envelope"},
}
