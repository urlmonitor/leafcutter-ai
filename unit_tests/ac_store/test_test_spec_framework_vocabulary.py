"""The AC store's test vocabulary can name every framework this repo runs.

KI-ACS-010. `test_spec[].framework` was an enum of ``["unittest", "pytest"]``,
authored when the repo was Python-only. It now also ships `leafcutter-web/`, a
TypeScript app whose tests run under vitest — installed, wired, and executed by
CI so the required done-proof gate can read its results. Twenty-eight records
across two components declared `vitest` or `playwright` and were rejected by the
schema for saying something true.

WHY BOTH SCHEMAS. `config/ac_store_schema.json` governs the AC record;
`config/test_requirements.schema.json` governs the ticket generated from it, and
`generate_ticket_from_ac.py` copies `framework` straight across that boundary.
Widening only the first moves the break downstream AND makes it silent, because
nothing enforces the ticket schema — the AC would validate while the generated
ticket quietly violated the contract test-writer is handed. The two enums are
hand-duplicated with nothing holding them in step, which is how they drift
apart again; `test_framework_enums_agree_across_both_schemas` is that guard.

WHAT THIS DELIBERATELY DOES NOT ASSERT. That a named framework is installed.
`playwright` is NOT currently a dependency of this repo — the two BP-1400
records naming it describe a CI gate that has not been built. A vocabulary that
can express a not-yet-installed tool is the point of a specification store, but
it means a validating record is not evidence the toolchain exists, and nothing
here should be read as saying otherwise. See KI-ACS-20260901-1520 for the
adjacent defect this widening makes less visible.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_AC_SCHEMA = _REPO_ROOT / "config" / "ac_store_schema.json"
_TICKET_SCHEMA = _REPO_ROOT / "config" / "test_requirements.schema.json"

#: Every runner this repository actually executes, plus the one its build-gate
#: criteria specify. unittest/pytest run the Python suites; vitest runs
#: leafcutter-web's; playwright is specified by BP-1400 and not yet installed.
_EXPECTED_FRAMEWORKS = {"unittest", "pytest", "vitest", "playwright"}


def _load(path: Path) -> dict:
    """Read and parse one JSON schema file.

    Args:
        path: Absolute path to the schema.

    Returns:
        The parsed schema document.

    Raises:
        OSError: When the schema cannot be read.
        json.JSONDecodeError: When it is not valid JSON.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssertionError(f"cannot read schema {path}: {exc}") from exc


def _ac_test_spec_properties() -> dict:
    """Return the per-entry property map of the AC schema's ``test_spec``.

    `test_spec` is a ``oneOf`` — an array-of-descriptors branch, or null for
    "no contract authored yet". Navigating straight to ``items`` misses that
    and raises KeyError, so the array branch is selected explicitly rather than
    by position, which would break silently if the branches were reordered.

    Returns:
        The ``properties`` map of one test-spec descriptor.
    """
    schema = _load(_AC_SCHEMA)
    branches = schema["properties"]["test_spec"]["oneOf"]
    array_branches = [b for b in branches if b.get("type") == "array"]
    assert len(array_branches) == 1, (
        "expected exactly one array branch in test_spec's oneOf; found "
        f"{len(array_branches)}. The schema's shape changed — re-point this "
        "accessor rather than loosening the assertion."
    )
    return array_branches[0]["items"]["properties"]


def _ac_framework_enum() -> list:
    """Return the ``framework`` enum from the AC-record schema."""
    return _ac_test_spec_properties()["framework"]["enum"]


def _ticket_framework_enum() -> list:
    """Return the ``framework`` enum from the generated-ticket schema."""
    schema = _load(_TICKET_SCHEMA)
    return schema["$defs"]["test_entry"]["properties"]["framework"]["enum"]


class TestFrameworkVocabulary(unittest.TestCase):
    def test_ac_schema_names_every_framework_this_repo_runs(self):
        # angle: criterion
        """The AC record may declare vitest and playwright, not only Python."""
        actual = set(_ac_framework_enum())
        missing = sorted(_EXPECTED_FRAMEWORKS - actual)
        self.assertEqual(
            missing,
            [],
            "config/ac_store_schema.json's test_spec framework enum cannot name "
            f"{missing}. leafcutter-web's suite genuinely runs under vitest, and "
            "BP-1400's criteria specify playwright, so records saying so are "
            f"rejected for being accurate. Enum is currently {sorted(actual)}.",
        )

    def test_ticket_schema_names_them_too(self):
        # angle: seam
        """The generated ticket must accept what the AC is allowed to say.

        `generate_ticket_from_ac.py` copies `framework` verbatim onto the
        ticket. If this schema is narrower than the AC schema, the AC validates
        and the ticket it produces does not — and nothing enforces the ticket
        schema, so that failure would be silent rather than loud.
        """
        actual = set(_ticket_framework_enum())
        missing = sorted(_EXPECTED_FRAMEWORKS - actual)
        self.assertEqual(
            missing,
            [],
            "config/test_requirements.schema.json cannot name "
            f"{missing}, so a generated ticket would violate its own schema for "
            "a value the AC schema permits. Widening one without the other moves "
            f"the break downstream and hides it. Enum is currently {sorted(actual)}.",
        )

    def test_framework_enums_agree_across_both_schemas(self):
        # angle: seam
        """The two hand-duplicated enums must stay identical.

        Nothing but this test holds them in step. They were byte-identical when
        authored and would have drifted the moment either was widened alone —
        which is precisely the change this suite accompanies.
        """
        ac_enum = sorted(_ac_framework_enum())
        ticket_enum = sorted(_ticket_framework_enum())
        self.assertEqual(
            ac_enum,
            ticket_enum,
            "the framework enums in config/ac_store_schema.json and "
            "config/test_requirements.schema.json have diverged. They are copied "
            "across by generate_ticket_from_ac.py, so a value legal in one and "
            "not the other produces a ticket that violates its own schema. "
            f"AC: {ac_enum}. Ticket: {ticket_enum}.",
        )


class TestTypeVocabulary(unittest.TestCase):
    def test_both_schemas_accept_component_tests(self):
        # angle: criterion
        """`type: component` is a real shape and both schemas must permit it.

        Nine ux-prototyping records declare it. A component test is neither a
        unit test nor an end-to-end one, and forcing it to claim either would
        make the record misdescribe what it is.
        """
        ac_types = set(_ac_test_spec_properties()["type"]["enum"])
        ticket_types = set(
            _load(_TICKET_SCHEMA)["$defs"]["test_entry"]["properties"]["type"]["enum"]
        )
        self.assertIn(
            "component",
            ac_types,
            f"AC schema type enum omits 'component'; it is {sorted(ac_types)}.",
        )
        self.assertIn(
            "component",
            ticket_types,
            f"ticket schema type enum omits 'component'; it is {sorted(ticket_types)}.",
        )


if __name__ == "__main__":
    unittest.main()
