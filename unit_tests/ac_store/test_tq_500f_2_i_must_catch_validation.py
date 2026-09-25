"""
MODULE: unit_tests/ac_store/test_tq_500f_2_i_must_catch_validation.py
COVERS: TQ-500f-2-i

GOAL (from the AC criteria): five requirements A-E share one test plan entry
(test_gate_blocks_on_missing_input) differing only in must_catch —
A: [], B: ["revert the fix", ""], C: ["   "], D: "revert the fix" (scalar,
not a list), E: ["revert the fix"] — plus a sixth requirement F with no test
plan at all (criteria-derived fallback). A-D must each be REJECTED by the
validator with a message naming the entry, the field 'must_catch', and which
rule failed (empty list / blank entry / not a list). E must be ACCEPTED and
its generated ticket must carry must_catch: ["revert the fix"]. F's
generated ticket must carry no must_catch key on any entry — the fallback
route never fabricates a wrong version.

RED BASELINE (2026-09-25, confirmed live at HEAD, direct probes against the
real validator CLI before this file was written):
  - A, B, C, D, and even E are ALL currently rejected — must_catch is not yet
    a recognised property anywhere in config/ac_store_schema.json's test_spec
    item schema (additionalProperties: false), so every variant fails with
    the SAME generic "is not valid under any of the given schemas" message,
    which names neither the rule that failed nor any of "empty"/"blank" —
    confirmed absent from the real stderr text for variant A.
  - E's ticket-carries-must_catch half is unreachable today because E itself
    is rejected before any ticket could be generated from it.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_VALIDATOR_CLI = _REPO_ROOT / "scripts" / "ac_store" / "validate_ac_schema.py"

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "ac_store"))

from _tkt_500f_support import generate_written, make_ac  # noqa: E402

_TESTS_BLOCK_RE = re.compile(
    r"##\s+Test\s+Requirements\b.*?```(?:yaml)?\s*(.*?)```",
    re.DOTALL | re.IGNORECASE,
)

_ENTRY_NAME = "test_gate_blocks_on_missing_input"


def _parse_tests_from_ticket(ticket_text: str) -> list[dict]:
    match = _TESTS_BLOCK_RE.search(ticket_text)
    assert match is not None, (
        f"no fenced ## Test Requirements YAML block found:\n{ticket_text[:1000]}"
    )
    parsed = yaml.safe_load(match.group(1))
    assert isinstance(parsed, dict) and isinstance(parsed.get("tests"), list)
    return [e for e in parsed["tests"] if isinstance(e, dict)]


def _run_validator(ac_yaml_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_VALIDATOR_CLI), str(ac_yaml_path)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_REPO_ROOT),
        timeout=30,
    )


def _base_ac_yaml(ac_id: str, must_catch) -> dict:
    entry = {"name": _ENTRY_NAME, "target_dir": "unit_tests/ac_store/"}
    if must_catch is not None:
        entry["must_catch"] = must_catch
    return {
        "id": ac_id,
        "title": "probe fixture for TQ-500f-2-i",
        "component": "testing-quality",
        "components": ["testing_quality"],
        "status": "active",
        "readiness": "approved",
        "priority": "high",
        "criteria": "Given x\nWhen y\nThen z\n",
        "test_spec": [entry],
    }


class TestValidatorCliRejectsEmptyBlankAndScalarMustCatch:
    """angle: reachability — production entry point: scripts/ac_store/
    validate_ac_schema.py CLI (the check-ac-schema commit gate)."""

    @pytest.mark.parametrize(
        "variant_id,ac_id_num,must_catch,rule_keyword",
        [
            ("A", 101, [], "empty"),
            ("B", 102, ["revert the fix", ""], "blank"),
            ("C", 103, ["   "], "blank"),
            ("D", 104, "revert the fix", "list"),
        ],
        ids=["A_empty_list", "B_blank_entry", "C_whitespace_only", "D_scalar_not_list"],
    )
    def test_validator_cli_rejects_empty_blank_and_scalar_must_catch(
        self, variant_id: str, ac_id_num: int, must_catch, rule_keyword: str
    ) -> None:
        # covers: TQ-500f-2-i
        # angle: reachability
        """WRONG VERSION THIS CATCHES: 'minLength 1 without a non-whitespace
        rule' (AC's own INTENDED must_catch note) — under that wrong
        version, variant C (["   "], a single non-empty-length string) would
        be wrongly ACCEPTED because the schema only checked string length,
        not blankness; the non-zero-exit assertion on C specifically catches
        that. A raw jsonschema dump that never says WHICH rule failed (empty
        / blank / not-a-list) — the current, confirmed-live behaviour — also
        fails the rule_keyword assertion below, which a plain
        additionalProperties widening would not fix by itself."""
        ac = _base_ac_yaml(f"ZZP-{ac_id_num}", must_catch)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"{variant_id}.yaml"
            path.write_text(yaml.dump(ac, allow_unicode=True), encoding="utf-8")
            result = _run_validator(path)

        assert result.returncode != 0, (
            f"variant {variant_id} (must_catch={must_catch!r}) must be "
            f"rejected by the real validator CLI.\nstdout:\n{result.stdout}"
        )
        stderr = result.stderr
        assert _ENTRY_NAME in stderr, (
            f"variant {variant_id}: rejection message must name the test_spec "
            f"entry {_ENTRY_NAME!r}:\n{stderr}"
        )
        assert "must_catch" in stderr, (
            f"variant {variant_id}: rejection message must name the field "
            f"'must_catch':\n{stderr}"
        )
        assert rule_keyword in stderr.lower(), (
            f"variant {variant_id}: rejection message must say which rule "
            f"failed (expected the word {rule_keyword!r} to appear):\n{stderr}"
        )


class TestSingleItemMustCatchIsAcceptedAndCarriedToTicket:
    """angle: criterion — E is the adversarial control against a validator
    that rejects every must_catch (per the AC's own notes: without E, a
    validator rejecting all of A-D would look identical to a correct one)."""

    def test_single_item_must_catch_is_accepted_and_carried_to_ticket(self) -> None:
        # covers: TQ-500f-2-i
        # angle: criterion
        """WRONG VERSION THIS CATCHES: 'reject any must_catch' (AC's own
        INTENDED must_catch note) — a validator that simply refuses the key
        outright (rather than validating its shape) would reject E exactly
        like A-D, which the returncode == 0 assertion below catches; a
        generator that never wires must_catch through at all would fail the
        ticket-carries-it assertion that follows."""
        ac = _base_ac_yaml("ZZP-105", ["revert the fix"])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "E.yaml"
            path.write_text(yaml.dump(ac, allow_unicode=True), encoding="utf-8")
            result = _run_validator(path)
        assert result.returncode == 0, (
            f"a single-item must_catch list must be ACCEPTED by the real "
            f"validator CLI (the adversarial control).\nstdout:\n{result.stdout}"
            f"\nstderr:\n{result.stderr}"
        )

        gen_ac = make_ac(assigned_agent="python-coder")
        gen_ac["criteria"] = "Given x\nWhen y\nThen z\n"
        gen_ac["test_spec"] = [
            {
                "name": _ENTRY_NAME,
                "target_dir": "unit_tests/ac_store/",
                "must_catch": ["revert the fix"],
            }
        ]
        gen = generate_written(gen_ac, "ZZP-E2")
        assert gen.exit_code == 0, f"generator CLI failed: {gen.warnings}"
        entries = _parse_tests_from_ticket(gen.text)
        target = next((e for e in entries if e.get("name") == _ENTRY_NAME), None)
        assert target is not None, f"expected entry not found among: {entries}"
        assert target.get("must_catch") == ["revert the fix"], (
            f"the accepted single-item must_catch must be carried through: "
            f"got {target.get('must_catch')!r}"
        )


class TestCriteriaFallbackTicketNeverCarriesMustCatch:
    """angle: failure — F: the criteria-derived fallback route (no test_spec
    authored) must fail safe by inventing nothing.

    NOTE ON RED STATE: unlike the tests above, this assertion is not forced
    red by HEAD's current behaviour — nothing in the fallback route
    (_derive_tests_from_criteria) has ever read or emitted must_catch, on
    either side of this AC's fix, so 'no must_catch key anywhere' already
    holds true today by construction. It is retained (per the AC's explicit
    test_spec and as a regression guard against the specific wrong version
    named below) with the strongest assertion available pre-implementation:
    it pins down the exact derived-descriptor shape so a future change to
    the fallback route cannot silently start fabricating must_catch without
    tripping this test.
    """

    def test_criteria_fallback_ticket_never_carries_must_catch(self) -> None:
        # covers: TQ-500f-2-i
        # angle: failure
        """WRONG VERSION THIS CATCHES: 'fallback copies criteria phrases
        into must_catch' (AC's own INTENDED must_catch note) — if
        _derive_tests_from_criteria were changed to scrape Then-clause text
        into a fabricated must_catch list, every descriptor below would gain
        a must_catch key; the per-entry key-set assertion (must_catch absent
        from every single descriptor, not just summarised as "not found
        anywhere") is written to catch that on any one of them, not only in
        aggregate."""
        ac = make_ac(assigned_agent="python-coder")
        ac["criteria"] = (
            "Given the retry gate has fired once already\n"
            "When neither the schedule window nor retry_due is true\n"
            "Then the gate must revert the fix and stay idle\n"
        )
        # No test_spec authored at all -> criteria-derived fallback route.
        gen = generate_written(ac, "ZZP-F1")
        assert gen.exit_code == 0, f"generator CLI failed: {gen.warnings}"
        entries = _parse_tests_from_ticket(gen.text)
        assert entries, "criteria-derived fallback must still emit at least one descriptor"

        offenders = [e.get("name") for e in entries if "must_catch" in e]
        assert offenders == [], (
            f"the criteria-derived fallback ticket must carry NO must_catch "
            f"key on any entry; offending entries: {offenders}\nfull "
            f"entries: {entries}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
