"""
MODULE: unit_tests/ac_store/test_authored_test_spec_survives_generation.py
GOAL: An authored ``test_spec`` reaches the generated ticket regardless of what
    the assigned agent produces.

WHY THIS EXISTS
    ``generate_ticket_from_ac.py`` gated the ENTIRE ``## Test Requirements``
    section on ``_computed_map_has_production_code_producer(agents)`` — i.e. on
    whether some agent in the computed map declares ``produces:
    production_code`` in ``config/agent_registry.json``. Exactly nine agents do
    (the coders). Every other assigned agent — ``llm-expert``,
    ``documentation-expert``, ``business-analyst``, and, most damningly,
    ``test-writer`` itself — caused the block to be omitted.

    The it-po had already authored a precise test contract on those records.
    The generator discarded it, ``test-writer`` was never injected into the
    agents map, and ``--verify`` reported the discard as a PASS:

        [PASS] non-code AC — no test contract required

    Measured on the real store at 06ce1c43 (2026-08-25): 85 ACs carry an
    authored ``test_spec`` whose assigned agent is not a production_code
    producer, totalling 308 discarded test descriptors. 65 are ``approved``;
    37 are approved-and-todo, i.e. buildable that day. By assigned agent:
    llm-expert 43, test-writer 13, documentation-expert 12, none 9,
    business-analyst 4, test-failure-triage 2, architecture-diagram-author 2.

    This is a phantom-done vector in the tool that generates the work, and it
    selects for the worst possible population: the ACs that specify the test
    and prompt infrastructure are precisely the ones whose test contracts were
    thrown away. BP-1100g-1 ("Every kind of proof the plan can ask for is a
    kind the test writer has been taught") is the worked example — four
    authored descriptors covering the criterion / real_artifact / failure /
    reachability angles, none of which reached its ticket.

WHAT IS AND IS NOT CHANGED
    Only the AUTHORED-``test_spec`` route is un-gated. The
    derive-from-criteria fallback stays gated on the production-code
    classification, so a doc-only or diagram-only ticket with no authored
    contract does NOT start receiving generated test stubs. That boundary is
    pinned by a negative control below; without it this fix would trade a
    silent omission for a silent fabrication.

ANTI-SYNTHETIC-FIXTURE POSTURE
    The primary gates drive the generator's REAL entry point
    (``generate_ticket_from_ac.py --ac <id> --dry-run`` as a subprocess) against
    the REAL on-disk store, and the store-wide gate DISCOVERS its records by
    scanning rather than naming them. A hand-typed ``{'test_spec': [...],
    'assigned_agent': 'llm-expert'}`` would prove only that the generator CAN
    emit the block for such a record — not that the records actually in the
    store now receive one. Follows the posture established in
    test_derived_test_reachability_floor.py.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GEN_SCRIPT = _REPO_ROOT / "scripts" / "ac_store" / "generate_ticket_from_ac.py"
_REAL_AC_ROOT = _REPO_ROOT / "docs" / "acceptance-criteria"

# The worked example from the AC that motivated this fix.
_ANCHOR_AC = "BP-1100g-1"


_CLI_CACHE: dict[tuple[str, str], str] = {}


def _generate_ticket_via_cli(ac_id: str, ac_root: Path | None = None) -> str:
    """Run the generator's REAL entry point and return its stdout.

    Memoised per (ac_id, ac_root). Three tests below assert different
    properties of the SAME generated ticket, and each subprocess re-parses the
    whole AC store, so running it three times costs ~2 minutes to produce three
    byte-identical strings.

    Caching is sound here specifically because ``--dry-run`` is deterministic
    and side-effect-free: it writes no ticket and back-writes no
    ``implemented_by`` (verified 2026-08-25 by running it and checking no file
    appeared). The REAL entry point is still exercised once per distinct input,
    which is the property these tests exist for — what is skipped is repetition,
    not coverage. If a future change makes generation non-deterministic, this
    cache would hide it; that would be a defect worth its own test rather than a
    reason to pay the cost here.

    Args:
        ac_id: AC id to generate a ticket for.
        ac_root: AC store root; defaults to the real on-disk store.

    Returns:
        The generator's stdout (frontmatter + ticket body).
    """
    root = str(ac_root or _REAL_AC_ROOT)
    cache_key = (ac_id, root)
    if cache_key in _CLI_CACHE:
        return _CLI_CACHE[cache_key]
    proc = subprocess.run(
        [
            sys.executable,
            str(_GEN_SCRIPT),
            "--ac",
            ac_id,
            "--ac-root",
            root,
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_REPO_ROOT),
    )
    assert proc.returncode == 0, (
        f"generator CLI failed for {ac_id} (exit {proc.returncode})\n"
        f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    _CLI_CACHE[cache_key] = proc.stdout
    return proc.stdout


def _parse_test_entries(ticket_text: str) -> list[dict]:
    """Extract the ``tests:`` list from a ticket's Test Requirements block.

    Args:
        ticket_text: Full generated ticket text.

    Returns:
        The parsed list of test descriptors; empty when the section is absent.
    """
    match = re.search(
        r"## Test Requirements\s*\n+```yaml\n(.*?)\n```",
        ticket_text,
        re.DOTALL,
    )
    if not match:
        return []
    parsed = yaml.safe_load(match.group(1))
    if not isinstance(parsed, dict):
        return []
    tests = parsed.get("tests")
    return tests if isinstance(tests, list) else []


def _load_ac(ac_id: str) -> dict:
    """Load a record from the real store by id.

    Deliberately FAILS rather than skips when the record is absent. A skip here
    would let this whole file silently stop testing the moment the anchor AC is
    renamed or moved — which is precisely the silent-no-op failure mode the file
    exists to prevent, and it would be embarrassing to ship it here of all
    places.

    Args:
        ac_id: AC id to find.

    Returns:
        The parsed AC record.
    """
    for path in _REAL_AC_ROOT.rglob(f"{ac_id}.yaml"):
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    raise AssertionError(
        f"anchor record {ac_id} is not in the store — this file's premise is "
        "gone. Re-point the anchor at another AC carrying an authored test_spec "
        "under a non-production_code agent; do not delete the test."
    )


def _iter_store_records(require_substrings: tuple[str, ...] = ()):
    """Yield parsed AC records from the real store.

    Every candidate file is READ, but only files whose raw text contains all of
    ``require_substrings`` are PARSED. The filter is a cheap pre-pass over text,
    never a substitute for the real check: the caller still asserts against the
    parsed record, so a substring that appears in a comment or a prose field
    costs one wasted parse and cannot produce a false pass.

    Why it exists: the store holds 3,340 YAML files and a full
    ``yaml.safe_load`` sweep takes ~36 s. The done-proof gate runs an AC's
    linked tests under a 60 s budget, so an unfiltered sweep here does not
    merely make the suite slow — it makes the gate report every linked test as
    "not run", which reads as a coverage failure rather than a timeout. Measured
    2026-08-25: full parse 35.8 s; raw-text pre-filter 0.12 s narrowing to 743
    candidates; pre-filter plus parse of the survivors 7.3 s for 460 records.

    Args:
        require_substrings: Raw-text substrings a file must contain to be
            parsed. Empty tuple parses everything (the original behaviour).

    Yields:
        Tuples of (path, parsed record dict).
    """
    for path in sorted(_REAL_AC_ROOT.rglob("*.yaml")):
        if path.name == "index.yaml":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if any(needle not in text for needle in require_substrings):
            continue
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError:
            continue
        if isinstance(data, dict) and data.get("id"):
            yield path, data


def _import_generator_internals():
    """Import the generator's body builder and agents-map builder.

    Returns:
        Tuple of (_build_ticket_body, _build_agents_map) from the REAL module —
        imported from scripts/, not re-implemented here.
    """
    sys.path.insert(0, str(_REPO_ROOT / "scripts" / "ac_store"))
    import generate_ticket_from_ac as gen  # noqa: PLC0415

    return gen._build_ticket_body, gen._build_agents_map


def _has_authored_spec(record: dict) -> bool:
    """Return True when the record carries a non-empty authored test_spec.

    Args:
        record: Parsed AC record.

    Returns:
        True when test_spec is a non-empty list.
    """
    spec = record.get("test_spec")
    return isinstance(spec, list) and len(spec) > 0


class TestAuthoredSpecReachesTheTicket:
    def test_authored_test_spec_survives_a_non_coder_assigned_agent(self) -> None:
        # covers: TKT-500g-1
        """Every descriptor the it-po authored on BP-1100g-1 reaches the ticket.

        BP-1100g-1 is assigned to llm-expert, which produces prompts rather than
        production_code. Before the fix its four descriptors appeared zero times
        in the generated ticket.
        """
        record = _load_ac(_ANCHOR_AC)
        authored = record.get("test_spec") or []
        assert authored, f"{_ANCHOR_AC} must carry an authored test_spec for this test"
        assert record.get("assigned_agent") == "llm-expert", (
            "this test's premise is a NON-coder assigned agent; "
            f"{_ANCHOR_AC} now says {record.get('assigned_agent')!r}"
        )

        ticket = _generate_ticket_via_cli(_ANCHOR_AC)
        emitted = _parse_test_entries(ticket)
        assert emitted, (
            f"{_ANCHOR_AC} authored {len(authored)} test(s) and the generated "
            "ticket has no ## Test Requirements block at all"
        )

        authored_names = {t["name"] for t in authored if isinstance(t, dict)}
        emitted_names = {t["name"] for t in emitted if isinstance(t, dict)}
        missing = authored_names - emitted_names
        assert not missing, (
            f"authored descriptors dropped from the ticket: {sorted(missing)}"
        )

    def test_authored_angles_survive_with_the_descriptors(self) -> None:
        # covers: TKT-500g-1
        """The angle classification is carried through, not flattened.

        The whole point of authoring four descriptors is that they answer four
        different proof questions. A fix that emits the names but drops the
        angles would satisfy the previous test and still lose the contract.
        """
        record = _load_ac(_ANCHOR_AC)
        authored = {
            t["name"]: t.get("angle")
            for t in (record.get("test_spec") or [])
            if isinstance(t, dict) and t.get("angle")
        }
        assert authored, f"{_ANCHOR_AC} must author at least one angle"

        emitted = {
            t["name"]: t.get("angle")
            for t in _parse_test_entries(_generate_ticket_via_cli(_ANCHOR_AC))
            if isinstance(t, dict)
        }
        for name, angle in authored.items():
            assert emitted.get(name) == angle, (
                f"angle for {name!r} did not survive: authored {angle!r}, "
                f"ticket carries {emitted.get(name)!r}"
            )

    def test_test_writer_is_dispatched_when_a_contract_is_emitted(self) -> None:
        # covers: TKT-500g-1
        """A Test Requirements block with nobody assigned to write the tests is
        no better than no block at all.

        test-writer was injected into the agents map only alongside a
        production_code agent, so a prompt AC would have carried the contract
        and dispatched nobody to satisfy it.
        """
        ticket = _generate_ticket_via_cli(_ANCHOR_AC)
        assert _parse_test_entries(ticket), "precondition: the block must be emitted"
        assert re.search(r"^\s*test-writer:\s*needed\s*$", ticket, re.MULTILINE), (
            "a Test Requirements block was emitted but test-writer is not "
            "'needed' in the agents map — nobody is dispatched to write them"
        )


class TestTheUnGatingIsBoundedToAuthoredContracts:
    """NEGATIVE CONTROLS. Without these, the fix trades a silent omission for a
    silent fabrication — generated stubs on tickets nobody asked to be tested."""

    def test_no_authored_spec_and_a_non_coder_agent_still_emits_nothing(self) -> None:
        # covers: TKT-500g-3
        """The derive-from-criteria fallback stays gated.

        Discovered from the real store rather than named, so it cannot be
        satisfied by a fixture chosen to agree with the author.
        """
        # Lazy: this control needs ONE qualifying record, not all of them, and
        # the qualifying condition is a disjunction over assigned_agent that the
        # raw-text pre-filter cannot express. Stopping at the first match keeps
        # the sweep off the full 3,340-file parse. Still a discovery, not a
        # fixture — the store decides which record this runs against.
        matches = (
            rec
            for _path, rec in _iter_store_records()
            if not _has_authored_spec(rec)
            and rec.get("assigned_agent") in {"documentation-expert", "llm-expert"}
            and rec.get("criteria")
        )
        first = next(matches, None)
        candidates = [first] if first is not None else []
        assert candidates, (
            "no doc/prompt AC without an authored test_spec found in the store. "
            "That is not a reason to skip — it means this negative control has "
            "no subject and the un-gating is unbounded. Investigate rather than "
            "letting the control pass vacuously."
        )

        record = candidates[0]
        ticket = _generate_ticket_via_cli(record["id"])
        assert not _parse_test_entries(ticket), (
            f"{record['id']} authored NO test_spec and is assigned to "
            f"{record.get('assigned_agent')!r}, but the generator invented a "
            "test contract for it — the un-gating must reach authored specs only"
        )

    def test_test_required_false_still_suppresses_an_authored_spec(self) -> None:
        # covers: TKT-500g-4
        """``test_required: false`` remains the explicit opt-out and outranks a
        stale authored spec."""
        store = _REPO_ROOT / "unit_tests" / "ac_store" / "_tmp_trf_store"
        component = store / "build-pipeline"
        component.mkdir(parents=True, exist_ok=True)
        record = {
            "id": "ZZ-9001",
            "component": "build-pipeline",
            "components": ["build_pipeline"],
            "title": "Opt-out outranks a stale authored spec",
            "level": "L2",
            "status": "active",
            "readiness": "draft",
            "work_status": "todo",
            "assigned_agent": "llm-expert",
            "criteria": "Given x,\nWhen y,\nThen z.\n",
            "test_required": False,
            "test_spec": [
                {"name": "test_zz_9001_stale", "target_dir": "unit_tests/ac_store/"},
            ],
            "origin_agent": "BrainCandy",
        }
        target = component / "ZZ-9001.yaml"
        target.write_text(yaml.safe_dump(record, sort_keys=False), encoding="utf-8")
        try:
            ticket = _generate_ticket_via_cli("ZZ-9001", ac_root=store)
            assert not _parse_test_entries(ticket), (
                "test_required: false must suppress the block even when a "
                "test_spec is present"
            )
        finally:
            target.unlink(missing_ok=True)
            component.rmdir()
            store.rmdir()


class TestNoRecordInTheStoreSilentlyLosesItsContract:
    def test_every_approved_authored_spec_reaches_its_ticket(self) -> None:
        # covers: TKT-500g-1
        """STORE-WIDE GATE — the population, not the worked example.

        Scans the real store for approved records carrying an authored
        test_spec and asserts none loses its contract. This is the test that
        would have failed on all 65 approved records before the fix, and it
        keeps failing if a future agent is added to the registry without a
        production_code declaration.

        Calls the body builder IN-PROCESS rather than paying the CLI's
        subprocess cost ~65 times (which exceeds the suite's time budget). The
        records are still the real ones read from disk, and the CLI path
        itself is proven separately by the anchor tests above — this sweep is
        about population coverage, not about the entry point.
        """
        build_body, build_map = _import_generator_internals()

        offenders: list[str] = []
        checked = 0
        # The pre-filter is a speed pass only; the real conditions are still
        # asserted on the parsed record immediately below, so a substring
        # appearing in prose costs a wasted parse and cannot let an offender
        # through. Without it this sweep parses all 3,340 files (~36 s) and
        # blows the done-proof gate's 60 s budget, which surfaces as "linked
        # test not run" — a timeout wearing a coverage failure's clothes.
        for _path, record in _iter_store_records(
            require_substrings=("test_spec:", "readiness: approved")
        ):
            if record.get("readiness") != "approved":
                continue
            if not _has_authored_spec(record):
                continue
            if record.get("test_required") is False:
                continue
            checked += 1
            agents = build_map(
                record.get("assigned_agent", "python-coder"),
                change_targets=(
                    [record["change_target"]]
                    if isinstance(record.get("change_target"), str)
                    else record.get("change_target")
                ),
                risk_surface=record.get("risk_surface") or None,
                declares_side_effect=bool(record.get("declares_side_effect", False)),
            )
            body = build_body(record, record["id"], agents_map=agents)
            if not _parse_test_entries(body):
                offenders.append(
                    f"{record['id']} (agent={record.get('assigned_agent')!r}, "
                    f"{len(record['test_spec'])} descriptor(s) dropped)"
                )

        assert checked, "no approved AC with an authored test_spec was examined"
        assert not offenders, (
            f"{len(offenders)} of {checked} approved ACs with an authored test "
            "contract generate a ticket with no ## Test Requirements block:\n  "
            + "\n  ".join(offenders)
        )


class TestVerifyDoesNotReportTheDiscardAsAPass:
    def test_verify_does_not_call_an_authored_contract_unnecessary(self) -> None:
        # covers: TKT-500g-5
        """The report said ``[PASS] non-code AC — no test contract required`` on
        a record carrying four authored tests.

        A success-shaped message on a silent discard is worse than no message:
        it is the thing that let 85 records reach ``approved`` with nobody
        noticing.
        """
        proc = subprocess.run(
            [
                sys.executable,
                str(_GEN_SCRIPT),
                "--ac",
                _ANCHOR_AC,
                "--ac-root",
                str(_REAL_AC_ROOT),
                "--verify",
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(_REPO_ROOT),
        )
        assert "no test contract required" not in proc.stdout, (
            f"--verify reports {_ANCHOR_AC} as needing no test contract while it "
            f"authors {len(_load_ac(_ANCHOR_AC)['test_spec'])} tests:\n{proc.stdout}"
        )
        assert "test_spec authored" in proc.stdout, (
            "--verify should acknowledge the authored contract:\n" + proc.stdout
        )
