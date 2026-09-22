#!/usr/bin/env python3
"""
MODULE: _gtfa_test_descriptors
GOAL: Derive test descriptors from an AC's Gherkin criteria when it authored no
    ``test_spec``, and guarantee that every finalised test plan carries exactly
    one reachability-floor entry.
BUSINESS CONTEXT: The criteria-derived fallback is, by construction, the
    AC-literal angle and nothing else — one test per ``Then`` clause, asserting
    the clause text. That is exactly the shape that lets code ship unit-tested
    but never wired into anything that runs it: the phantom-done failure this
    repo exists to prevent. The reachability floor is the single entry under
    that fallback that must invoke a production entry point, and it is
    deliberately an INSTRUCTION rather than a stub, because an AC with no
    ``test_spec`` never named an entry point for the generator to fill in.
ARCHITECTURE: The floor is attached at two places on purpose, and the two are
    idempotent together. ``_derive_tests_from_criteria`` appends it so a direct
    caller of that function still observes the floor;
    ``_ensure_reachability_floor`` is the universal finalisation point, and it
    de-duplicates by declared KIND (``angle == "reachability"``) rather than by
    name, path, or text similarity — so an authored entry of any shape is
    returned untouched instead of having a second, contradictory request
    stapled next to it.
"""

from __future__ import annotations

import importlib
import logging
import re
from typing import TYPE_CHECKING, Any

# See the "Sibling wiring" note in generate_ticket_from_ac.py for why the
# sibling package prefix is derived from __name__ rather than hard-coded.
_PKG = __name__.rpartition(".")[0]
_gtfa_seams = importlib.import_module(f"{_PKG}._gtfa_seams" if _PKG else "_gtfa_seams")
_gtfa_constants = importlib.import_module(
    f"{_PKG}._gtfa_constants" if _PKG else "_gtfa_constants"
)

logger = logging.getLogger(_gtfa_seams.logger_name())

# ``AcRecord`` is bound at RUNTIME by the ``else`` branch, off the sibling
# module object resolved above through importlib under a prefix COMPUTED from
# ``__name__`` -- see the "Sibling wiring" note in generate_ticket_from_ac.py
# for why a literal relative import there would break one of the two supported
# layouts. A computed name is opaque to a type checker, so that rebind reads as
# a VARIABLE and mypy rejects every annotation using it ("Variable ... is not
# valid as a type"). The TYPE_CHECKING branch declares the alias statically and
# is never executed, so the runtime binding is unchanged.
if TYPE_CHECKING:  # pragma: no cover - a static declaration, never executed
    from ._gtfa_constants import AcRecord
else:
    AcRecord = _gtfa_constants.AcRecord

TEST_ANGLE_CRITERION = _gtfa_constants.TEST_ANGLE_CRITERION
TEST_ANGLE_REACHABILITY = _gtfa_constants.TEST_ANGLE_REACHABILITY
_REACHABILITY_ASSERTS = _gtfa_constants._REACHABILITY_ASSERTS


def _slugify_for_test(text: str, max_words: int = 8) -> str:
    """Convert free text into a snake_case identifier fragment for a test name.

    Args:
        text: Source text (e.g. a Gherkin Then clause or an AC id).
        max_words: Cap on the number of words retained.

    Returns:
        A lowercase snake_case fragment safe for a Python test function name.
    """
    words = re.findall(r"[A-Za-z0-9]+", text.lower())
    if not words:
        return "criterion"
    return "_".join(words[:max_words])


def _unique_test_name(name: str, seen: set[str]) -> str:
    """Return *name*, numerically suffixed until it is absent from *seen*.

    A fixed suffix can still collide with an earlier clause's slug, which would
    silently drop a test, so the suffix is incremented until the candidate is
    genuinely unique. Does NOT mutate *seen* — the caller records the result.

    Args:
        name: Desired test function name.
        seen: Names already allocated for this descriptor set.

    Returns:
        A name not present in *seen*.
    """
    if name not in seen:
        return name
    suffix = 1
    candidate = f"{name}_{suffix}"
    while candidate in seen:
        suffix += 1
        candidate = f"{name}_{suffix}"
    return candidate


def _reachability_descriptor(
    ac_id: str, file_path: str, seen: set[str]
) -> dict[str, Any]:
    """Build the mandatory reachability-floor test descriptor for an AC.

    The derived-from-criteria fallback is, by construction, the AC-literal angle
    and nothing else: one test per Gherkin ``Then`` clause, asserting the clause
    text. That is exactly the shape that lets code ship unit-tested but never
    wired into anything that runs it (phantom-done — see CLAUDE.md "Gate /
    Workflow ACs — Verify Behaviorally, Not by Grep"). This descriptor is the
    floor under that fallback: one test that must invoke the production entry
    point.

    Args:
        ac_id: The AC id the test covers.
        file_path: Test file the derived descriptors live in.
        seen: Names already allocated, so a slug collision disambiguates rather
            than silently dropping the entry.

    Returns:
        A single test descriptor dict tagged ``angle: reachability``.
    """
    slug = _slugify_for_test(ac_id)
    return {
        "name": _unique_test_name(f"test_{slug}_reachable_from_entry_point", seen),
        "file": file_path,
        "covers": [ac_id],
        "angle": TEST_ANGLE_REACHABILITY,
        "asserts": _REACHABILITY_ASSERTS,
    }


def _derive_tests_from_criteria(ac: AcRecord, ac_id: str) -> list[dict[str, Any]]:
    """Derive best-effort test descriptors from an AC's Gherkin criteria.

    Fallback used only when the AC carries no explicit ``test_spec``. Each
    ``Then`` clause in the criteria becomes one ``angle: criterion`` test
    descriptor, so the derived ticket still tells test-writer what to assert
    straight from the criteria — the AC remains the source of truth. When no
    ``Then`` clause is present a single generic descriptor is emitted so the
    ticket is never left with an empty test contract.

    On top of those, one mandatory ``angle: reachability`` descriptor is always
    appended: the reachability floor. Without it this fallback emits only
    AC-literal unit tests, which pass happily on code no entry point ever calls.

    Args:
        ac: Parsed AC record.
        ac_id: The AC id.

    Returns:
        List of test descriptor dicts (name / file / covers / angle / asserts),
        always including exactly one reachability entry.
    """
    criteria = str(ac.get("criteria") or "")
    slug = _slugify_for_test(ac_id)
    then_clauses = [
        m.group(1).strip()
        for m in re.finditer(r"^\s*Then\b(.*)$", criteria, re.MULTILINE | re.IGNORECASE)
        if m.group(1).strip()
    ]
    file_path = f"unit_tests/test_{slug}.py"
    tests: list[dict[str, Any]] = []
    seen: set[str] = set()

    if not then_clauses:
        tests.append({
            "name": f"test_{slug}_satisfies_criteria",
            "file": file_path,
            "covers": [ac_id],
            "angle": TEST_ANGLE_CRITERION,
            "asserts": "Derived from AC criteria — replace with a concrete assertion.",
        })
        seen.add(tests[0]["name"])
    else:
        for clause in then_clauses:
            name = _unique_test_name(f"test_{slug}_{_slugify_for_test(clause)}", seen)
            seen.add(name)
            tests.append({
                "name": name,
                "file": file_path,
                "covers": [ac_id],
                "angle": TEST_ANGLE_CRITERION,
                "asserts": clause,
            })

    # Unconditional by design. Every descriptor built above is hard-coded
    # ``angle: criterion``, and an authored ``test_spec`` never reaches this
    # function — ``_build_test_requirements_section`` returns the spec-derived
    # descriptors before calling it. So there is nothing here that could already
    # be a reachability entry, and an "is one present?" guard would be dead code.
    # This append is kept (rather than moved wholesale to the universal floor
    # in ``_ensure_reachability_floor``) so direct callers of this function —
    # bypassing ``_build_test_requirements_section`` entirely — still observe
    # the floor; ``_ensure_reachability_floor``'s dedupe-by-kind check makes
    # the two call sites idempotent together (BO-2900g-1-i), never doubled up.
    tests.append(_reachability_descriptor(ac_id, file_path, seen))
    return tests


def _ensure_reachability_floor(
    ac_id: str, descriptors: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Guarantee exactly one ``angle: reachability`` descriptor, at the one
    finalisation point every produced test plan passes through.

    BO-2900g-1: the reachability request used to be attached ONLY inside
    ``_derive_tests_from_criteria`` (the criteria-derived fallback route). An
    AC that authored its own ``test_spec`` never reached that function, so it
    received a privileged, undecided exemption from the floor. This helper is
    called from ``_build_test_requirements_section`` — the single place a
    plan is finalised for a piece of work, regardless of which route produced
    the descriptor list — so a third route introduced later inherits the
    floor without being told about this rule.

    BO-2900g-1-i: de-duplication is by declared KIND (``angle ==
    "reachability"``), never by descriptor name, file path, or text
    similarity. A plan that already carries one such entry — in any authored
    shape, naming any entry point — is returned unaltered: its authored
    order and fields survive byte-for-byte, and no second, contradictory
    request is stapled on next to it.

    Args:
        ac_id: The AC id, used to build the appended descriptor's name/file
            when the floor is not already present.
        descriptors: The descriptor list produced by whichever route ran
            (spec-derived or criteria-derived), in authored/derived order.

    Returns:
        *descriptors* unchanged when a reachability entry is already present;
        otherwise a new list with *descriptors* followed by exactly one
        sentinel reachability descriptor.
    """
    if any(
        isinstance(item, dict) and item.get("angle") == TEST_ANGLE_REACHABILITY
        for item in descriptors
    ):
        return descriptors

    slug = _slugify_for_test(ac_id)
    first_file = descriptors[0].get("file") if descriptors else None
    file_path = first_file if isinstance(first_file, str) and first_file else (
        f"unit_tests/test_{slug}.py"
    )
    seen = {
        item["name"]
        for item in descriptors
        if isinstance(item, dict) and item.get("name")
    }
    return [*descriptors, _reachability_descriptor(ac_id, file_path, seen)]
