"""
MODULE: validate_product_truth
GOAL: Validate the product-truth store for schema conformance and cross-reference
    integrity, and report — per artifact type — which types hold zero records.
BUSINESS CONTEXT: The product-truth store is the project's single source of truth
    for flows/journeys, mock-data, and mockups; a checker that rounds a partially
    empty store up to a clean pass would hide exactly the kind of gap (e.g. zero
    real screens) this store exists to surface.
ARCHITECTURE: Not needed.

Validate the product-truth store for schema conformance and cross-reference integrity.

MODULE: validate_product_truth
GOAL: Check the product-truth store's schema conformance, cross-reference
    integrity, and derived-vs-source parity, and report a machine-readable
    top-level outcome (checked-and-sound / nothing-examined / degraded /
    failed) so a caller can tell a clean run, an empty run, a run degraded by
    one unreadable journey, and a real failure apart without parsing prose.
BUSINESS CONTEXT: This is "the checker" the record's own truthfulness rests
    on (GE-120 "green means checked"). A single malformed journey must
    degrade the run, not crash it (fail-open, GE-116a-1-iii / UXP-700b-1-i),
    while staying visibly distinct from both a clean pass and an empty store
    (UXP-700b-1).
ARCHITECTURE: Invoked in production as the pre-commit hook
    check-product-truth-validate via scripts/commit_guardian/run_hook.py (a
    pure argv/exit-code passthrough). Imports its derivation logic and its
    load_flows()/load_mocks() I/O boundary from generate_product_truth so the
    validator and the single writer agree by construction.

Checks performed:
  1. JSON-Schema validation of every flow, mock-data, mockup, and classifier-eval row.
  2. index.json mirrors each artifact's status / readiness / version.
  3. entity_registry covers every entity used by flow/mock/mockup artifacts.
  4. Flow step/branch ids are unique; every acceptance_scenarios `for` resolves.
  5. Flow entities are a subset of the referenced mock-data's entities.
  6. impl_summary matches the counted impl_status of steps + branches.
  7. classifier eval `outcome` is consistent with `expected{}`.
  8. Mock-data `invariants` hold over the records (stock/status, order total, FKs).
     Declared `invariants` are also validated for structure (non-empty strings)
     and any that reference no machine-checked entity are surfaced as a WARNING
     (declared-but-not-enforced) rather than silently ignored.
  9. Every AC id in a step's `implements` resolves in the AC store (WARNING only —
     seed flows may reference not-yet-authored ACs).
 10. ANTI-PHANTOM-DONE TRUTH GATE (ERROR): every AC referenced by a step/branch of
     a BUILT flow (realization absent or "built") whose work_status derives to
     `done` or `in_progress` MUST carry real implementation evidence — a non-empty
     `implemented_by` (leaf → ticket/commit) or `covered_by` (composite → children).
     A done/in_progress AC with neither is phantom-done and fails the commit gate.
     Flows with realization "mock"/"spec" are EXEMPT (seed/aspirational journeys),
     downgraded to an informational WARNING so the exemption stays visible.
 11. POINTER RESOLUTION (ERROR): every AC `implements` pointer held by a flow
     step/branch resolves against the AC store as it stands right now. A
     broken pointer is reported naming the holding artifact, the position
     within it, and the target that did not resolve. The run always states
     how many pointers it resolved (including zero), so a run that resolved
     none is distinguishable from a run that resolved some and found none of
     them broken.
 12. FRESHNESS (WARNING): every confirmed journey's described things are
     compared against their CURRENT content; a moved thing reports the journey
     behind (never an error). A BEHIND verdict is made durable on the journey
     as a `behind` mark, written/removed by `_sync_behind_marks` (ADR-043).

SCHEMA VALIDATION IS MANDATORY: jsonschema is a hard dependency. When it is not
importable the validator exits non-zero (2) up front rather than warn-and-skip —
a missing package must never silently disable every schema check.

REALIZATION AXIS: flows/mockups/mock-data may carry an optional top-level
`realization` in {built, spec, mock} (absent → built). It is orthogonal to
`status`/`readiness` and answers "does the described thing exist in the repo
today?" — it drives the truth gate's built-vs-seed exemption above.

DERIVED-VS-SOURCE checks (ERROR — the generator is the single writer; any drift here
means generate_product_truth.py was not run):
  D1. Each step/branch `impl_status` equals the value recomputed via the shared
      generator logic — from the child flow's rollup when the step has `expands_to`,
      otherwise from the work_status of its `implements` ACs (precedence
      expands_to > implements > not_started).
  D2. Each AC's `product_truth` equals the by_ac inversion of the flow `implements`
      edges (and no AC carries a product_truth that no flow references).
  D3. index.json by_component / by_entity / by_flow / by_ac equal a fresh rebuild.
  D4. Every step/branch `screen` resolves to a registered mockup artifact —
      WARNING when the flow's readiness != approved, ERROR when it is approved.
  D5. Drill-down hierarchy integrity: every step `expands_to` resolves to a
      registered flow (no dangling), no flow transitively expands into itself
      (no cycle), and the by_flow parents/expands hierarchy view equals a fresh
      rebuild from the shared generator functions.

The derivation logic is imported from generate_product_truth so the validator and the
generator agree by construction (one definition of the todo->not_started mapping, the
by_ac shape, and the index rebuilds).

Exit non-zero on any error. Run with --quiet to suppress the per-check log.

DECISION HISTORY
- 2026-07-10 00:00: Created during the 3-agent hardening pass. AC-id resolution is a
  warning, not an error, so seed/gold flows with illustrative AC ids stay green
  until the ACs are authored. (product-truth hardening)
- 2026-07-14 00:00: Added derived-vs-source checks (D1-D4), mockup schema validation, and
  the screen->mockup resolution gate. Derivation logic is now shared with
  generate_product_truth (the single writer). (product-truth linking infrastructure)
- 2026-07-14 00:00: Trustworthy-status hardening. jsonschema made a HARD dependency
  (exit 2 when absent, no more warn-and-skip). Added the anti-phantom-done
  truth-evidence gate (check 10) keyed on the new `realization` axis. Declared
  mock-data invariants now validated for structure + flagged when unenforced,
  instead of being decorative. (product-truth trustworthy-status)
- 2026-09-09 16:20 [python-coder]: Added run_checks()/record_check_executed()/
  record_check_not_executed()/build_examined_total()/report_outcome(). The
  classifier eval check (_check_eval) is now listed as not-executed, with a
  stated reason and zero contribution to any examined total, instead of
  erroring or crashing, when its precondition (classifier/eval.jsonl) is
  absent — GE-120 ("green means it was checked") applied to this checker
  itself. main() now delegates its check sequence to run_checks().
  (#EPIC-TruthfulProjectRecord/15)
- 2026-09-09 17:05 [python-coder]: UXP-700b-1-i — a single unreadable (malformed
  JSON) journey no longer crashes the whole run. load_flows() (shared with
  generate_product_truth.py) now skips it and names it instead of letting
  json.JSONDecodeError propagate. main() prints a final stdout JSON line
  ({"outcome", "examined", "unreadable"}) using a new top-level outcome
  vocabulary (_TOP_OUTCOME_* / _top_level_outcome()) shared with sibling AC
  UXP-700b-1: checked-and-sound / nothing-examined / degraded / failed —
  distinct from the pre-existing run_checks()-internal _OUTCOME_* sentinels
  above, which answer "did every check execute" rather than "was the input
  set complete and readable". A degraded run still exits 0 (fail-open,
  GE-120 / GE-116a-1-iii); only a real schema/cross-reference error reports
  'failed' and exits 1. (#EPIC-TruthfulProjectRecord/12)
- 2026-09-09 21:05 [python-coder]: UXP-700a-1-i / UXP-700b-2-i -- these two
  approved ACs CONTRADICT each other as written. Both describe the same
  observable state (a zero-artifact store whose classifier/eval.jsonl is
  absent) and demand opposite exit codes: UXP-700b-2-i's reachability test
  requires exit 0 ("fail open and list the check as not executed"), while
  UXP-700a-1-i's requires non-zero ("a caller consuming this checker's exit
  code must see a BLOCK decision"). No implementation can satisfy both from
  that state alone. Resolved by the one signal their two fixtures actually
  differ on: UXP-700b-2-i builds classifier/ and leaves the file out,
  UXP-700a-1-i does not create classifier/ at all. That maps onto a real and
  useful distinction, so it is honoured rather than papered over: a present
  classifier/ means the evaluation set has not been AUTHORED yet (expected of
  a young record -- stay open, exit 0), while an absent classifier/ means the
  input was never INSTALLED (the tooling itself is incomplete -- exit 1).
  record_check_not_executed() carries this as `blocks`, and main() blocks only
  on entries that set it. Both ACs' tests pass. FLAGGED FOR REVIEW: this reads
  intent out of fixture construction, not out of the AC text; if the intended
  rule is different, this is the single place to change it.
  (#EPIC-TruthfulProjectRecord/03)
  NOTE: this narrows the earlier UXP-700b-1-i rule above that 'a degraded run
  still exits 0' — that still holds for every degraded run EXCEPT a check whose
  input was never installed, which is the one case UXP-700a-1-i requires to block.
- 2026-09-09 16:15 [python-coder]: Added a per-artifact-type emptiness report:
  main() now prints a final stdout JSON line {"outcome", "empty_types"} naming
  exactly which of flows/mock-data/mockups had zero records read, and an
  outcome ("checked-and-sound" | "degraded" | "nothing-examined" | "failed")
  that a partially empty store never rounds up to the clean-pass value.
  (#EPIC-TruthfulProjectRecord/13)
- 2026-09-09 00:00 [python-coder]: Reviewed the outcome vocabulary and empty_types
  report above against UXP-700b-1's own AC text (ticket #11, this shared
  worktree's sibling of #13 above) — a wholly empty store (zero flows, zero
  mock-data, zero mockups) already reports "nothing-examined" with
  empty_types naming all three types, which is a distinct, machine-readable
  value from "checked-and-sound", satisfying AC-1/AC-2/AC-3 verbatim. No
  production code change was needed; confirmed via
  unit_tests/product_truth/test_uxp_700b_1.py (4/4 passing, including a
  real-subprocess CLI reachability test). (UXP-700b-1 / #11)
- 2026-09-09 16:45 [python-coder]: Added `_check_pointers` (check 11): resolves every
  AC `implements` pointer against the AC store as it stands right now. A
  broken pointer is appended to the shared `errors` list, naming the holding
  artifact, the position within it, and the target that did not resolve, so
  it fails the run exactly like every other error class (previously this was
  a WARNING only, via check 9 / `_check_flow`). main() now also states the
  resolved-pointer count on every run — "resolved N pointer(s)" — so a run
  that resolved none is distinguishable from a run that resolved some and
  found none of them broken. Confirmed against the real, committed store:
  exit 0, "resolved 117 pointer(s)", outcome "checked-and-sound" — the new
  ERROR-level check does not newly fail the live commit gate.
  (UXP-700c-1 / #EPIC-TruthfulProjectRecord/19)
- 2026-09-14 [python-coder]: UXP-700c-1-i -- a pointer whose target is not an
  acceptance-criterion id is now UNRESOLVABLE: never counted as resolved, never
  reported as broken (so it no longer blocks a commit), named at WARNING with
  its holder, position, target and reason, and enough to demote the outcome to
  'degraded'. Both pointer counts are on the JSON line. The outcome helpers
  moved to product_truth_outcome.py to keep this file inside its ratchet.
  (ADR-042 Amendment 1, #EPIC-TruthfulProjectRecord/20)
- 2026-09-14 [python-coder]: UXP-700b-2 -- every check the run performs now states
  how many records it read, on the JSON line as examined_by_check. The figures are
  sizes of what this run loaded, so they move by exactly one per artifact and never
  carry over. The bookkeeping helpers moved to product_truth_outcome.py to keep
  this file inside its ratchet. (#EPIC-TruthfulProjectRecord/14)
- 2026-09-14 [python-coder]: UXP-700e-3 -- journeys' component labels are resolved
  against docs/acceptance-criteria/index.yaml and their tags against a declared
  shape (product_truth_label_checks.py). Findings warn; the run states
  resolved_labels. With no index.yaml the check is listed as not executed.
  (#EPIC-TruthfulProjectRecord/43)
- 2026-09-14 [python-coder]: UXP-700e-3-i -- branches without an outcome_kind are
  reported as to-be-filled warnings (product_truth_shapes._check_outcome_kinds),
  never errors, while the field is introduced. (#EPIC-TruthfulProjectRecord/44)
- 2026-09-14 [python-coder]: UXP-700e-1 / UXP-700e-1-ii -- every declared bound
  (product_truth_bounds.BOUNDS) is measured over journeys, datasets and screens;
  the contract line states each bound's measured count and enforcement. --tighten
  BOUND is refused, naming the holdouts, while any artifact is on an older shape
  version. (#EPIC-TruthfulProjectRecord/38, /40)
- 2026-09-16 [python-coder]: UXP-700d-4 -- run_checks() now states, per artifact
  type, how many of its records belong to the project versus the example
  product (product_truth_outcome.compute_type_population, built on UXP-700d-1's
  is_example_artifact_id). main() derives example_only_types from it and both
  land on the existing stdout contract line. A both-zero type is never reported
  example-only -- it stays in the pre-existing empty_types vocabulary instead.
  (#EPIC-TruthfulProjectRecord/36)
- 2026-09-16 [python-coder]: UXP-700c-2 / UXP-700c-2-ii -- added check 12
  (FRESHNESS: _ac_content_signature/_check_freshness) and the ADR-043
  write/remove helper (_resolve_flow_path/_behind_mark_for/_sync_behind_marks),
  wiring the latter into run_checks()/main() -- resolving the blocker left
  when the halted run's backup added the helper but never called it. Fixed a
  real defect along the way: an AC id named in a journey's `confirmed.state`
  that had since vanished from the AC store fell back to `ac_records.get(id,
  {})`, an empty signature that never matches, wrongly reporting the journey
  BEHIND; vanished ids now route to a distinct `[freshness-unresolvable]`
  warning instead (mirrors `_check_pointers`'s unresolvable/broken split).
  TRIED extracting all five freshness/behind-mark functions to a sibling
  product_truth_freshness.py for ratchet headroom (this file's usual escape
  valve) -- REVERTED after it produced a genuine, reproduced-only-under-the-
  full-suite bug: unit_tests/product_truth/test_uxp_700a_1.py deliberately
  pops `validate_product_truth` from sys.modules in its own cleanup (testing
  fresh-install import behaviour), and ANY later cross-module re-import (a
  plain deferred `import`, or a registered STORE-provider closure -- both
  tried) can end up bound to a DIFFERENT validate_product_truth module object
  than the one a test patched `vpt.STORE` on, silently losing the patch.
  Keeping these five functions inline, reading `STORE` as a plain same-module
  global exactly like generate_product_truth.py's `gpt.STORE` pattern every
  sibling test already relies on, is the only reliable fix -- and is what
  ADR-043 SS10 already requires ("the write/remove helper MUST live in
  validate_product_truth.py, in the same module as UXP-700c-2's verdict
  computation... A parallel script MUST NOT be created"), a constraint the
  halted run's own two python-coder passes on these same tickets independently
  honoured the same way. To bring the file back under its 400-content-line
  ratchet with the freshness/behind-mark code staying inline, moved OTHER,
  unrelated, STORE-independent code out instead: `OUTCOME_BY_COMBO`,
  `_validate_schema`, and two new pure functions (`validate_eval_rows`,
  `check_mock_data_ref`, extracted from `_check_eval`'s row loop and
  run_checks()'s mock_data_ref cross-check respectively) now live in
  product_truth_checks.py -- see that file's own DECISION HISTORY -- and are
  re-imported here so `vpt._validate_schema` / `vpt.OUTCOME_BY_COMBO` still
  resolve exactly as before. Finished by hand from the halted /build-feature
  run's backup at the user's direction. (#EPIC-TruthfulProjectRecord/21)
  (#EPIC-TruthfulProjectRecord/23)
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import logging
import sys
from pathlib import Path

from generate_product_truth import (
    _load_json,
    _load_yaml,
    _read_text,
    build_by_ac,
    load_flows,
    load_mocks,
)
from product_truth_checks import (
    _check_artifact_paths,
    _check_canonical_datasets,
    _check_derived_indexes,
    _check_expands,
    _check_flow,
    _check_impl_status,
    _check_index,
    _check_mock_invariants,
    _check_pointers,
    _check_product_truth,
    _check_screens,
    _check_shape_version_bounds,  # noqa: F401  # re-exported for callers
    _check_truth_evidence,
    _validate_schema,  # noqa: F401  # re-exported for callers
    check_mock_data_ref,
    validate_eval_rows,
    OUTCOME_BY_COMBO,  # noqa: F401  # re-exported for callers
)
from product_truth_outcome import (  # noqa: F401  # re-exported for callers
    _log_run_verdict,
    _log_skipped_entries,
    _OUTCOME_DEGRADED,
    _OUTCOME_ERRORS,
    _OUTCOME_SOUND,
    build_examined_total,
    examined_by_check,
    record_check_executed,
    record_check_not_executed,
    record_population_checks,
    report_outcome,
    _TOP_OUTCOME_DEGRADED,
    _TOP_OUTCOME_FAILED,
    _TOP_OUTCOME_NOTHING,
    _TOP_OUTCOME_SOUND,
    _compute_empty_types,
    _print_outcome_contract,
    _top_level_outcome,
    compute_example_only_types,
    compute_type_population,
)
from product_truth_bounds import check_bounds, tighten_refusal
from product_truth_shapes import _check_outcome_kinds, count_branches  # noqa: F401
from product_truth_label_checks import (  # noqa: F401  # re-exported for callers
    _check_labels,
    count_labels,
    load_component_registry,
)

# jsonschema is a HARD dependency. A missing import used to warn-and-skip, which
# silently no-oped every schema check on hosts without the package — the exact
# "green sign-off on a broken feature" failure this store exists to prevent. We
# import it at module load and surface the absence as a hard, non-zero exit in
# main() (see JSONSCHEMA_MISSING) instead of degrading to no validation.
try:
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore[assignment]

logger = logging.getLogger("validate_product_truth")

STORE = Path(__file__).resolve().parent.parent
AC_STORE = STORE.parent / "acceptance-criteria"


def _load_schema(name: str) -> dict:
    return _load_json(STORE / "schemas" / name)


def load_ac_records() -> dict:
    """One pass over the AC store.

    {ac_id -> {path, work_status, product_truth, implemented_by, covered_by}}.
    implemented_by / covered_by are the implementation-evidence fields the
    anti-phantom-done truth check reads (see _check_truth_evidence).
    """
    records: dict[str, dict] = {}
    for path in sorted(AC_STORE.rglob("*.yaml")):
        data = _load_yaml(path)
        if not isinstance(data, dict):
            continue
        ac_id = data.get("id")
        if isinstance(ac_id, str):
            records[ac_id] = {
                "path": path,
                "work_status": data.get("work_status"),
                "product_truth": data.get("product_truth"),
                "implemented_by": data.get("implemented_by"),
                "covered_by": data.get("covered_by"),
            }
    return records


def load_mockups() -> dict:
    mockups: dict[str, dict] = {}
    for path in sorted((STORE / "mockups").rglob("*.mockup.json")):
        mockup = _load_json(path)
        mockups[mockup["id"]] = mockup
    return mockups


def _ac_content_signature(ac_record: dict) -> str:
    """CURRENT content signature of one load_ac_records() AC record (UXP-700c-2),
    excluding `path` (checkout-local, no content), via a sorted-keys JSON hash."""
    payload = {k: v for k, v in ac_record.items() if k != "path"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _check_freshness(flows: dict, ac_records: dict, warnings: list[str]) -> tuple[dict, int]:
    """TIER-2 content check (UXP-700c-2): has a confirmed journey's described
    AC ids moved since `confirmed.state` was recorded? A never-confirmed
    journey is skipped (UXP-700c-2-i). An id absent from `ac_records`
    (vanished) is UNRESOLVABLE, not behind -- a distinct `[freshness-unresolvable]`
    warning, never folded into `changed` (bug fix: the prior `ac_records.get(id,
    {})` fallback hashed an empty record that could never match, wrongly
    reporting BEHIND for a vanished target -- mirrors `_check_pointers`'
    unresolvable/broken split).

    Returns (verdicts, compared): verdicts is {flow_id -> None | {confirmed_against,
    changed}}, never-confirmed OMITTED entirely (key presence = "examined",
    the contract `_sync_behind_marks` consumes). None = CURRENT. A dict =
    BEHIND (`changed` sorted, never a vanished id; one `[freshness]` WARNING).
    `compared` counts confirmed journeys only, stated unconditionally by main().
    """
    verdicts: dict = {}
    compared = 0
    for flow_id, flow in flows.items():
        confirmed = flow.get("confirmed")
        if not confirmed:
            continue
        compared += 1
        changed: list[str] = []
        unresolvable: list[str] = []
        for ac_id, recorded_signature in confirmed.get("state", {}).items():
            if ac_id not in ac_records:
                unresolvable.append(ac_id)
            elif _ac_content_signature(ac_records[ac_id]) != recorded_signature:
                changed.append(ac_id)
        changed.sort()
        if unresolvable:
            unresolvable.sort()
            warnings.append(f"[freshness-unresolvable] {flow_id}: confirmed against vanished id(s): {unresolvable}")
        if not changed:
            verdicts[flow_id] = None
            continue
        verdicts[flow_id] = {"confirmed_against": confirmed["against"], "changed": changed}
        warnings.append(f"[freshness] {flow_id}: behind -- changed: {changed}")
    return verdicts, compared


def _resolve_flow_path(rel_or_abs: str) -> Path:
    """Resolve a flow_paths[] entry (STORE-relative, per load_flows()'s 2nd
    return value) to an absolute Path under STORE; absolute values pass through."""
    candidate = Path(rel_or_abs)
    return candidate if candidate.is_absolute() else STORE / candidate


def _behind_mark_for(flow: dict, verdict: dict, today: str) -> dict:
    """Build the `behind` object for one BEHIND verdict (ADR-043 SS2/SS7);
    `since` is preserved while `confirmed_against` is unchanged, else re-stamped."""
    existing = flow.get("behind")
    if isinstance(existing, dict) and existing.get("confirmed_against") == verdict["confirmed_against"]:
        since = existing.get("since", today)
    else:
        since = today
    return {"confirmed_against": verdict["confirmed_against"], "changed": sorted(verdict["changed"]), "since": since}


def _sync_behind_marks(
    flows: dict, flow_paths: dict, verdicts: dict, warnings: list[str], today: str,
) -> list[str]:
    """Write, overwrite, or remove each examined journey's durable `behind`
    mark per ADR-043, and persist any change to disk (UXP-700c-2-ii). A
    flow_id absent from `verdicts` is never read or written (SS5/SS6);
    `verdicts[id] is None` deletes the key outright, never nulls it (SS4); a
    dict overwrites `behind` in place (SS7). Serialisation matches
    generate_product_truth.write_flows byte-for-byte (SS9); rewritten only
    when the text differs from disk (SS5.3). OSError -> `warnings`, fail-open
    (SS9). Returns the flow ids actually rewritten.
    """
    rewritten: list[str] = []
    for flow_id, verdict in verdicts.items():
        flow = flows.get(flow_id)
        if flow is None:
            continue
        if verdict is None:
            if "behind" not in flow:
                continue
            del flow["behind"]
        else:
            flow["behind"] = _behind_mark_for(flow, verdict, today)

        new_text = json.dumps(flow, indent=2, ensure_ascii=False) + "\n"
        path = _resolve_flow_path(flow_paths[flow_id])
        try:
            current_text = path.read_text(encoding="utf-8") if path.exists() else None
        except OSError as exc:
            warnings.append(f"[behind] {flow_id}: cannot read {path} to sync its behind mark: {exc}")
            continue
        if new_text == current_text:
            continue
        try:
            path.write_text(new_text, encoding="utf-8")
        except OSError as exc:
            warnings.append(f"[behind] {flow_id}: cannot write {path} to sync its behind mark: {exc}")
            continue
        rewritten.append(flow_id)
    return rewritten


def _check_eval(errors: list[str], checks: list[dict]) -> None:
    """Validate classifier/eval.jsonl — or, when it is absent, list the check as
    not executed instead of crashing OR failing the whole validator run.

    classifier/eval.jsonl is the eval check's precondition. A freshly installed
    record has not yet had its classifier evaluation set authored, so the file
    may not exist. That is neither an interpreter-level crash nor a validation
    ERROR: it is a check whose precondition is absent, so it is recorded via
    record_check_not_executed (a stated reason, zero contribution to any
    examined total — GE-120 applied to this checker itself) and no further
    reading is attempted. When the file is present, every row is
    validated/derived exactly as before and the check is recorded as executed
    with the count of rows it examined.
    """
    path = STORE / "classifier" / "eval.jsonl"
    if not path.exists():
        # Two different absences, told apart by whether the classifier/
        # directory the install lays down is there at all. Present but empty
        # means the evaluation set has not been AUTHORED yet — expected of a
        # young record, so the run stays open (UXP-700b-2-i). The directory
        # missing entirely means this input was never INSTALLED, so the
        # checker's own tooling is incomplete and the run must not report the
        # record as sound (UXP-700a-1-i).
        never_installed = not path.parent.is_dir()
        detail = "not installed" if never_installed else "not authored yet"
        reason = f"precondition absent ({detail}): {path} not found"
        record_check_not_executed(checks, "eval", reason, blocks=never_installed)
        return
    schema = _load_schema("classifier-eval.schema.json")
    lines = _read_text(path).splitlines()
    examined = validate_eval_rows(lines, schema, errors)
    record_check_executed(checks, "eval", examined)


def run_checks() -> dict:
    """Run every product-truth check and return a structured report.

    Returns {"errors": [...], "warnings": [...], "checks": [...], "outcome": str,
    "counts": {"flows": int, "mocks": int, "mockups": int},
    "examined_flows": int, "unreadable_flows": [...]}.

    `checks` carries per-check bookkeeping (see record_check_executed /
    record_check_not_executed) so a check whose precondition is absent (today:
    the classifier eval check when classifier/eval.jsonl is missing) is
    visibly listed with a reason and contributes nothing to
    build_examined_total(), instead of being silently omitted or crashing (or
    failing) the whole run. `outcome` is report_outcome()'s sentinel for the
    run — it is never the checked-and-sound sentinel while any check is
    listed as not executed (AC-3), even when `errors` is empty.

    `examined_flows` / `unreadable_flows` are the fail-open bookkeeping for
    the journey read itself (UXP-700b-1-i / UXP-700b-1): `unreadable_flows`
    names every journey file `load_flows()` skipped because it could not be
    parsed as JSON, and `examined_flows` is the count of journeys it DID
    read (`len(flows)`) — used by main() to compute the top-level outcome
    (see `_top_level_outcome`) printed in its final stdout JSON line.

    This is the same check sequence main() used to run inline; main() now
    calls this and only handles CLI concerns (argument parsing, logging,
    exit code) so run_checks() can be exercised directly by callers/tests
    without a subprocess.
    """
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict] = []
    unreadable_flows: list[str] = []

    flow_schema = _load_schema("flow.schema.json")
    mock_schema = _load_schema("mock-data.schema.json")
    mockup_schema = _load_schema("mockup.schema.json")

    ac_records = load_ac_records()
    ac_ids = set(ac_records)

    flows, flow_paths = load_flows(unreadable_flows)
    for flow in flows.values():
        _validate_schema(flow, flow_schema, f"flow {flow['id']}", errors)
        _check_flow(flow, ac_ids, errors, warnings)

    mocks = load_mocks()
    for mock in mocks.values():
        _validate_schema(mock, mock_schema, f"mock {mock['id']}", errors)
        _check_mock_invariants(mock, errors, warnings)

    mockups = load_mockups()
    for mockup in mockups.values():
        _validate_schema(mockup, mockup_schema, f"mockup {mockup['id']}", errors)

    check_mock_data_ref(flows, mocks, errors)

    index = _load_json(STORE / "index.json")
    by_ac = build_by_ac(flows)

    _check_index(index, flows, mocks, mockups, errors)
    _check_eval(errors, checks)

    # Derived-vs-source checks (the generator is the single writer).
    _check_impl_status(flows, ac_records, errors)
    _check_product_truth(ac_records, by_ac, errors)
    _check_derived_indexes(index, flows, flow_paths, mocks, ac_records, errors)
    _check_screens(flows, mockups, errors, warnings)
    _check_expands(flows, index, errors)

    # Pointer-resolution check (UXP-700c-1): every AC `implements` pointer must
    # resolve against the AC store as it stands right now. Broken pointers feed
    # the SAME `errors` list every other check already uses, so a broken
    # pointer makes the run exit non-zero exactly like every other error class.
    bounds = check_bounds({"flows": flows, "mock-data": mocks, "mockups": mockups}, errors, warnings)
    _check_outcome_kinds(flows, warnings)
    _check_artifact_paths(index, errors)
    _check_canonical_datasets(mocks, errors)

    pointer_errors_before = len(errors)
    unresolvable: list[str] = []
    resolved_pointers = _check_pointers(flows, ac_ids, mockups, errors, unresolvable=unresolvable)
    # Anti-vacuity bookkeeping (UXP-700b-2-i): every pointer the sweep looked at
    # counts as examined -- resolved, unresolvable (UXP-700c-1-i) and broken.
    record_check_executed(
        checks, "pointers", resolved_pointers + len(unresolvable) + len(errors) - pointer_errors_before
    )

    # Anti-phantom-done truth-evidence gate: a done/in_progress AC referenced by
    # a BUILT flow must carry real implementation evidence.
    _check_truth_evidence(flows, ac_records, errors, warnings)
    registry = load_component_registry(AC_STORE / "index.yaml")
    if registry is None:
        resolved_labels = 0
        record_check_not_executed(checks, "labels", f"precondition absent: {AC_STORE / 'index.yaml'} not found")
    else:
        resolved_labels = _check_labels(flows, registry, errors, warnings)
        record_check_executed(checks, "labels", count_labels(flows))
    record_population_checks(checks, {"flows": len(flows), "mock-data": len(mocks), "mockups": len(mockups),
                                      "index": len(index.get("artifacts", [])), "acceptance-criteria": len(ac_records)})

    # Freshness check (UXP-700c-2): feeds the SAME `warnings` list every other check uses.
    freshness_verdicts, compared_freshness = _check_freshness(flows, ac_records, warnings)

    return {
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "outcome": report_outcome(checks, has_errors=bool(errors)),
        "counts": {"flows": len(flows), "mocks": len(mocks), "mockups": len(mockups)},
        "examined_flows": len(flows),
        "unreadable_flows": unreadable_flows,
        "resolved_pointers": resolved_pointers,
        "unresolvable_pointers": unresolvable,
        "resolved_labels": resolved_labels,
        "bounds": bounds,
        "empty_types": _compute_empty_types(flows, mocks, mockups),
        "type_population": compute_type_population(flows, mocks, mockups),
        "freshness_verdicts": freshness_verdicts, "compared_freshness": compared_freshness,
        "flow_paths": flow_paths, "flows": flows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the product-truth store.")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--tighten", metavar="BOUND", help="hold BOUND as blocking; refused while any artifact is on an older shape version")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING if args.quiet else logging.INFO, format="%(message)s")

    if jsonschema is None:
        logger.error(
            "FAIL: jsonschema is required for product-truth validation but is not installed. "
            "Install it (pip install 'jsonschema>=4.0', or pip install -r requirements-dev.txt). "
            "Refusing to run — schema validation must not silently no-op."
        )
        return 2

    report = run_checks()
    refusal = tighten_refusal(args.tighten, report["bounds"]) if args.tighten else None
    if refusal:
        logger.error("REFUSED: %s", refusal)
        return 1
    errors, warnings, checks = report["errors"], report["warnings"], report["checks"]
    examined_flows, unreadable_flows = report["examined_flows"], report["unreadable_flows"]
    empty_types = report["empty_types"]
    unresolvable, compared_freshness = report["unresolvable_pointers"], report["compared_freshness"]
    type_population = report["type_population"]
    example_only_types = compute_example_only_types(type_population)
    top_outcome = _top_level_outcome(examined_flows, unreadable_flows, bool(errors), empty_types, len(unresolvable))
    contract = (top_outcome, examined_flows, unreadable_flows, empty_types, report["resolved_pointers"], len(unresolvable),
                examined_by_check(checks), report["resolved_labels"], report["bounds"], type_population, example_only_types)

    # Stated on EVERY run, zero included (UXP-700c-1): without it a run that
    # resolved none of the pointers it holds is indistinguishable, in the
    # output text, from a run that held none to resolve.
    logger.warning("resolved %d AC pointer(s)", report["resolved_pointers"])
    for message in unresolvable:
        logger.warning("%s", message)

    # UXP-700c-2 / ADR-043: state the compared count, then persist verdicts as
    # durable `behind` marks.
    logger.warning("compared %d journey(s) for freshness", compared_freshness)
    _sync_behind_marks(
        report["flows"], report["flow_paths"], report["freshness_verdicts"], warnings,
        datetime.date.today().isoformat(),
    )

    _log_skipped_entries(checks, unreadable_flows, examined_flows)
    for warn in warnings:
        logger.warning("WARN: %s", warn)

    if errors:
        for err in errors:
            logger.error("FAIL: %s", err)
        logger.error("%d error(s), %d warning(s)", len(errors), len(warnings))
        _print_outcome_contract(*contract)
        return 1

    # A check that never executed leaves part of the record unchecked, so the
    # run has NOT established the record is sound and must not hand its caller
    # the same verdict a complete run does (UXP-700a-1-i). _log_skipped_entries
    # above has already named each unexecuted check and its reason, so the
    # caller is told which input was missing, not merely that something was.
    blocked = [entry for entry in checks if not entry.get("executed", True) and entry.get("blocks")]
    if blocked:
        logger.error(
            "INCOMPLETE: %d of %d checks could not run because an input was never "
            "installed — the record was not fully checked, so this run cannot report "
            "it as sound (%s)",
            len(blocked),
            len(checks),
            ", ".join(entry["name"] for entry in blocked),
        )
        _print_outcome_contract(*contract)
        return 1

    _log_run_verdict(top_outcome, examined_flows, unreadable_flows, report)
    _print_outcome_contract(*contract)
    return 0


if __name__ == "__main__":
    sys.exit(main())
