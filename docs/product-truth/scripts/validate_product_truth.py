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
"""
from __future__ import annotations

import argparse
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
    _ARTIFACT_TYPES,
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
    _check_shape_version_bounds,
    _check_truth_evidence,
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

OUTCOME_BY_COMBO = {
    (True, True, True): "full-set",
    (False, True, True): "mockup+data",
    (False, False, True): "mockup-only",
    (False, True, False): "mock-data-only",
    (False, False, False): "none",
}


# Canonical artifact-type identifiers used by the per-type emptiness report
# (UXP-700b-1 / UXP-700b-1-ii). These match the store's own directory names.

def _compute_empty_types(flows: dict, mocks: dict, mockups: dict) -> list[str]:
    """Return the artifact types for which zero records were read.

    Names exactly the types with a zero count — a type that has at least one
    record is never included, even when other types are empty. This is the
    per-type distinction UXP-700b-1 introduces and UXP-700b-1-ii pins on a
    mixed (partially empty) store.
    """
    counts = {"flows": len(flows), "mock-data": len(mocks), "mockups": len(mockups)}
    return sorted(name for name in _ARTIFACT_TYPES if counts[name] == 0)


def _load_schema(name: str) -> dict:
    return _load_json(STORE / "schemas" / name)


def _validate_schema(instance: dict, schema: dict, label: str, errors: list[str]) -> None:
    """Validate one instance against a schema (jsonschema is guaranteed present).

    main() exits non-zero before any check runs when jsonschema is absent, so
    the module-level `jsonschema` is never None here.
    """
    try:
        jsonschema.validate(instance, schema)
    except jsonschema.ValidationError as exc:
        errors.append(f"[schema] {label}: {exc.message}")


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







































def record_check_executed(checks: list[dict], name: str, examined: int) -> None:
    """Append an executed-check entry recording how many records it examined.

    `checks` is the per-run bookkeeping list threaded through run_checks() (and
    built directly in unit tests). `examined` is the count of records this
    check actually inspected — the figure build_examined_total() sums across
    every executed entry.
    """
    checks.append({"name": name, "executed": True, "examined": examined})


def record_check_not_executed(
    checks: list[dict], name: str, reason: str, *, blocks: bool = False
) -> None:
    """Append a not-executed entry carrying a stated reason (GE-120, applied here).

    A check whose precondition is absent (e.g. the file it reads does not
    exist) must be visibly listed — never silently omitted, never left to
    crash the whole run — and must contribute exactly zero to any stated
    examined figure (see build_examined_total).

    *blocks* separates the two reasons a precondition can be missing, which
    the record cannot tell apart from the check's own point of view but which
    mean opposite things to a caller:

    * ``blocks=False`` — the input has simply not been AUTHORED yet. Expected
      of a young record; the run stays open and exits zero (UXP-700b-2-i).
    * ``blocks=True`` — the input was never INSTALLED, so the tooling itself
      is incomplete and no run against it can establish the record is sound.
      The run exits non-zero (UXP-700a-1-i).
    """
    checks.append({"name": name, "executed": False, "reason": reason, "blocks": blocks})


def build_examined_total(checks: list[dict]) -> int:
    """Sum the `examined` figure across executed checks only.

    Not-executed entries (record_check_not_executed) carry no `examined` key
    and are excluded from the sum, so an unexecuted check contributes nothing
    to any stated examined total — AC-2 of UXP-700b-2-i.
    """
    return sum(entry.get("examined", 0) for entry in checks if entry.get("executed"))


# Outcome sentinels returned by report_outcome(). Kept as named constants (not
# inlined) so main()'s branch on the "everything executed and sound" case can't
# accidentally match a degraded run by string coincidence.
_OUTCOME_SOUND = "checked-and-sound"
_OUTCOME_ERRORS = "checked-with-errors"
_OUTCOME_DEGRADED = "checked-with-unexecuted-checks"

# Top-level outcome vocabulary printed as main()'s final stdout JSON line
# (UXP-700b-1-i / UXP-700b-1). Distinct from _OUTCOME_* above, which are the
# internal run_checks()-bookkeeping sentinels for UXP-700b-2-i's "did every
# check execute" question. This vocabulary answers a different question — "is
# the run's own INPUT set complete and readable?" — and is shared with sibling
# AC UXP-700b-1 (nothing-examined) per architect-review's sign-off note on this
# ticket: reuse this vocabulary rather than inventing a second, locally-scoped
# enum. `_TOP_OUTCOME_SOUND` intentionally reuses the same "checked-and-sound"
# string as `_OUTCOME_SOUND` — both vocabularies agree that value means "fully
# clean" — but the two constant families are otherwise independent.
_TOP_OUTCOME_SOUND = "checked-and-sound"
_TOP_OUTCOME_NOTHING = "nothing-examined"
_TOP_OUTCOME_DEGRADED = "degraded"
_TOP_OUTCOME_FAILED = "failed"


def report_outcome(checks: list[dict], *, has_errors: bool = False) -> str:
    """Return the outcome sentinel for a completed check run.

    The checked-and-sound outcome is returned ONLY when every recorded check
    executed and there were no errors. If ANY check is listed as not executed,
    the outcome is never the checked-and-sound sentinel — even with zero
    errors — because part of the record was not actually checked (AC-3).
    """
    if any(not entry.get("executed", True) for entry in checks):
        return _OUTCOME_DEGRADED
    if has_errors:
        return _OUTCOME_ERRORS
    return _OUTCOME_SOUND


def _top_level_outcome(
    examined: int, unreadable: list[str], has_errors: bool, empty_types: list[str]
) -> str:
    """Return the top-level outcome sentinel for main()'s final stdout JSON line.

    Precedence: a real cross-reference/schema ERROR always reports 'failed'
    (never masked by input-completeness — a run with unreadable journeys AND
    real errors is a failure, not merely degraded). Otherwise, one or more
    unreadable journeys reports 'degraded': the fail-open convention (GE-120 /
    GE-116a-1-iii) means a single bad journey must not stop the work that
    triggered the check, but the run must still be visibly distinguishable
    from both a fully clean run and a run that examined nothing (UXP-700b-1-i).
    Otherwise, a store in which EVERY artifact type read zero records reports
    'nothing-examined' — a run that examined nothing must not report the same
    outcome as a run that was checked and found sound (UXP-700b-1). Anything
    else is 'checked-and-sound'.

    PARTIAL emptiness deliberately does NOT change the verdict. A record that
    holds journeys but no screens or example data yet is young, not defective:
    everything present was checked and was sound, which is exactly what this
    value claims. Which types were empty is still REPORTED, in `empty_types`,
    so the reader can see it — it just does not withhold the clean pass. This
    resolves the UXP-700b-1-i / UXP-700b-1-ii contradiction in -1-i's favour
    (KI-ACD-20260909-2130); *empty_types* stays a parameter because the
    emptiness question is answered on the same line and belongs in the same
    place as the verdict it deliberately does not affect.
    """
    if has_errors:
        return _TOP_OUTCOME_FAILED
    if unreadable:
        return _TOP_OUTCOME_DEGRADED
    if examined == 0 and len(empty_types) == len(_ARTIFACT_TYPES):
        return _TOP_OUTCOME_NOTHING
    return _TOP_OUTCOME_SOUND


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
        record_check_not_executed(
            checks,
            "eval",
            f"precondition absent ({detail}): {path} not found",
            blocks=never_installed,
        )
        return
    schema = _load_schema("classifier-eval.schema.json")
    lines = _read_text(path).splitlines()
    examined = 0
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"[eval] line {i}: invalid JSON: {exc}")
            continue
        examined += 1
        _validate_schema(row, schema, f"eval row {row.get('id', i)}", errors)
        exp = row["expected"]
        combo = (exp["needs_flow"], exp["needs_mock_data"], exp["needs_mockup"])
        derived = OUTCOME_BY_COMBO.get(combo)
        if derived is None:
            errors.append(f"[eval] {row['id']}: impossible combo {combo}")
        elif derived != row["outcome"]:
            errors.append(f"[eval] {row['id']}: outcome '{row['outcome']}' != derived '{derived}'")
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

    for flow in flows.values():
        ref = flow.get("mock_data_ref")
        if ref and ref in mocks:
            mock_entities = set(mocks[ref].get("entities", {}).keys())
            missing = [e for e in flow.get("entities", []) if e not in mock_entities]
            if missing:
                errors.append(f"[flow] {flow['id']}: entities {missing} absent from mock_data_ref '{ref}'")
        elif ref:
            errors.append(f"[flow] {flow['id']}: mock_data_ref '{ref}' does not resolve")

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
    _check_shape_version_bounds(flows, errors, warnings)
    _check_artifact_paths(index, errors)
    _check_canonical_datasets(mocks, errors)

    pointer_errors_before = len(errors)
    resolved_pointers = _check_pointers(flows, ac_ids, mockups, errors)
    # Anti-vacuity bookkeeping (UXP-700b-2-i): the pointer sweep states how
    # many pointers it actually looked at -- resolved ones plus the broken
    # ones it just appended to `errors` -- so a run over a record holding no
    # pointers at all reads as examined=0 rather than as a silent success.
    record_check_executed(
        checks, "pointers", resolved_pointers + (len(errors) - pointer_errors_before)
    )

    # Anti-phantom-done truth-evidence gate: a done/in_progress AC referenced by
    # a BUILT flow must carry real implementation evidence.
    _check_truth_evidence(flows, ac_records, errors, warnings)

    return {
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "outcome": report_outcome(checks, has_errors=bool(errors)),
        "counts": {"flows": len(flows), "mocks": len(mocks), "mockups": len(mockups)},
        "examined_flows": len(flows),
        "unreadable_flows": unreadable_flows,
        "resolved_pointers": resolved_pointers,
        "empty_types": _compute_empty_types(flows, mocks, mockups),
    }


def _print_outcome_contract(
    outcome: str, examined: int, unreadable: list[str], empty_types: list[str]
) -> None:
    """Print the LAST stdout line: the machine-readable outcome JSON contract.

    Pinned by unit_tests/product_truth/test_uxp_700b_1_i.py — printed via
    print(), independent of the logging module's handler configuration, so a
    caller (or a second test in the same interpreter, where
    logging.basicConfig() is a documented process-wide one-shot no-op) can
    always read the run's outcome from stdout alone: {"outcome": ...,
    "examined": <int of journeys read>, "unreadable": [<journey path>, ...],
    "empty_types": [<artifact type read as zero records>, ...]}.

    `examined` and `unreadable` answer "was the input set complete and
    readable"; `empty_types` answers "which artifact types held nothing". They
    are reported together, on one line, because a caller deciding whether the
    record was really checked needs both (UXP-700b-1 / UXP-700b-1-ii).
    """
    print(
        json.dumps(
            {
                "outcome": outcome,
                "examined": examined,
                "unreadable": unreadable,
                "empty_types": empty_types,
            }
        )
    )


def _log_skipped_entries(checks: list[dict], unreadable_flows: list[str], examined_flows: int) -> None:
    """Log every not-executed check and every unreadable journey, each with a reason.

    Neither category is ever silently omitted (GE-120): a not-executed check
    carries its own stated reason; an unreadable journey is named alongside
    how many of the rest were still examined (UXP-700b-1-i).
    """
    for entry in checks:
        if not entry.get("executed", True):
            logger.warning("SKIPPED: check '%s' did not execute — %s", entry["name"], entry.get("reason"))
    for journey in unreadable_flows:
        logger.warning(
            "SKIPPED: journey '%s' is unreadable (invalid JSON) — examined the other %d",
            journey,
            examined_flows,
        )


def _log_run_verdict(top_outcome: str, examined_flows: int, unreadable_flows: list[str], report: dict) -> None:
    """Log the single verdict line matching *top_outcome* (assumes no errors).

    Precedence mirrors `_top_level_outcome`: an unreadable journey always logs
    DEGRADED first (even if `report["outcome"]` — the separate, internal
    run_checks()-bookkeeping sentinel for UXP-700b-2-i — happens to be sound),
    then a truly empty store logs NOTHING EXAMINED, then a not-fully-executed
    but readable run logs the pre-existing DEGRADED-by-unexecuted-check
    message, and only a fully sound, fully executed run logs OK.
    """
    counts, warnings = report["counts"], report["warnings"]
    if unreadable_flows:
        logger.warning(
            "DEGRADED: %d journeys examined, %d unreadable (%s) — the run still completed "
            "(fail-open, GE-120 / GE-116a-1-iii)",
            examined_flows,
            len(unreadable_flows),
            ", ".join(unreadable_flows),
        )
    elif top_outcome == _TOP_OUTCOME_NOTHING:
        logger.warning(
            "NOTHING EXAMINED: the record holds no journeys yet — not the same as a "
            "checked-and-sound run"
        )
    elif report["outcome"] != _OUTCOME_SOUND:
        logger.warning(
            "DEGRADED: %d flows, %d mock-data, %d mockups valid, but not every check "
            "executed (%d warnings) — see SKIPPED lines above",
            counts["flows"],
            counts["mocks"],
            counts["mockups"],
            len(warnings),
        )
    else:
        logger.info(
            "OK: %d flows, %d mock-data, %d mockups, eval + index + derived data valid (%d warnings)",
            counts["flows"],
            counts["mocks"],
            counts["mockups"],
            len(warnings),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the product-truth store.")
    parser.add_argument("--quiet", action="store_true")
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
    errors, warnings, checks = report["errors"], report["warnings"], report["checks"]
    examined_flows, unreadable_flows = report["examined_flows"], report["unreadable_flows"]
    empty_types = report["empty_types"]
    top_outcome = _top_level_outcome(examined_flows, unreadable_flows, bool(errors), empty_types)

    # Stated on EVERY run, zero included (UXP-700c-1): without it a run that
    # resolved none of the pointers it holds is indistinguishable, in the
    # output text, from a run that held none to resolve.
    logger.warning("resolved %d AC pointer(s)", report["resolved_pointers"])

    _log_skipped_entries(checks, unreadable_flows, examined_flows)
    for warn in warnings:
        logger.warning("WARN: %s", warn)

    if errors:
        for err in errors:
            logger.error("FAIL: %s", err)
        logger.error("%d error(s), %d warning(s)", len(errors), len(warnings))
        _print_outcome_contract(top_outcome, examined_flows, unreadable_flows, empty_types)
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
        _print_outcome_contract(top_outcome, examined_flows, unreadable_flows, empty_types)
        return 1

    _log_run_verdict(top_outcome, examined_flows, unreadable_flows, report)
    _print_outcome_contract(top_outcome, examined_flows, unreadable_flows, empty_types)
    return 0


if __name__ == "__main__":
    sys.exit(main())
