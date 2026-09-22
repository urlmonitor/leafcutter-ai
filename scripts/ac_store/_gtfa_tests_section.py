#!/usr/bin/env python3
"""
MODULE: _gtfa_tests_section
GOAL: Turn an AC's authored ``test_spec`` — or, failing that, its criteria —
    into the generated ticket's ``## Test Requirements`` block.
BUSINESS CONTEXT: An authored ``test_spec`` is the it-po's explicit statement
    of what this work must assert, and it is the source of truth test-writer
    works from. Discarding it is not a missing feature but a silent data loss:
    conflating "does this change production code?" with "did somebody specify
    tests for it?" once threw away 308 authored descriptors across 85 records,
    including 13 assigned to test-writer itself. The block is therefore never a
    hardcoded ``tests: []`` stub — it is always derived from the AC, so the
    ticket-level Test Requirements guard passes by construction.
ARCHITECTURE: Source-of-truth order is spec first, criteria second, and the
    reachability floor is applied to whichever route ran. The YAML dump uses
    ``sort_keys=False`` and that is load-bearing, not cosmetic: ``name`` must
    stay the first key of each entry or
    ``check_ticket_test_requirements._TESTS_ENTRY_RE`` stops matching and the
    guard silently sees a block with no tests in it.
"""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING, Any

import yaml

# See the "Sibling wiring" note in generate_ticket_from_ac.py for why the
# sibling package prefix is derived from __name__ rather than hard-coded.
_PKG = __name__.rpartition(".")[0]
_gtfa_seams = importlib.import_module(f"{_PKG}._gtfa_seams" if _PKG else "_gtfa_seams")
_gtfa_constants = importlib.import_module(
    f"{_PKG}._gtfa_constants" if _PKG else "_gtfa_constants"
)
_gtfa_test_descriptors = importlib.import_module(
    f"{_PKG}._gtfa_test_descriptors" if _PKG else "_gtfa_test_descriptors"
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

_TEST_ANGLES = _gtfa_constants._TEST_ANGLES
_slugify_for_test = _gtfa_test_descriptors._slugify_for_test
_derive_tests_from_criteria = _gtfa_test_descriptors._derive_tests_from_criteria
_ensure_reachability_floor = _gtfa_test_descriptors._ensure_reachability_floor


def _test_descriptors_from_spec(ac: AcRecord, ac_id: str) -> list[dict[str, Any]]:
    """Build test descriptors from the AC's explicit ``test_spec`` field.

    ``test_spec`` is the source-of-truth test contract authored on the AC by
    it-po. Each entry is normalised into the ticket ``## Test Requirements``
    shape (name / file / covers / asserts, plus optional framework / type /
    requires_db). The ``file`` path is derived from ``target_dir`` and the AC id
    when the entry does not already point at a ``.py`` file.

    Args:
        ac: Parsed AC record.
        ac_id: The AC id.

    Returns:
        List of test descriptor dicts. Empty when ``test_spec`` is absent or
        contains no usable entries.
    """
    test_spec = ac.get("test_spec")
    if not isinstance(test_spec, list) or not test_spec:
        return []
    slug = _slugify_for_test(ac_id)
    descriptors: list[dict[str, Any]] = []
    for item in test_spec:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if not name:
            continue
        entry = _spec_entry(item, name, slug, ac_id)
        descriptors.append(entry)
    return descriptors


def _spec_entry(
    item: dict[str, Any], name: str, slug: str, ac_id: str
) -> dict[str, Any]:
    """Normalise one authored ``test_spec`` item into a ticket test descriptor.

    Args:
        item: One entry from the AC's ``test_spec`` list.
        name: The entry's ``name`` (already confirmed non-empty by the caller).
        slug: Slugified AC id, used to build a default test file path.
        ac_id: The AC id, named in the unrecognised-angle WARNING.

    Returns:
        The descriptor dict for this entry.
    """
    target_dir = str(item.get("target_dir") or "").rstrip("/")
    if target_dir.endswith(".py"):
        file_path = target_dir
    elif target_dir:
        file_path = f"{target_dir}/test_{slug}.py"
    else:
        file_path = f"unit_tests/test_{slug}.py"
    entry: dict[str, Any] = {
        "name": name,
        "file": file_path,
        "covers": item.get("covers") or [ac_id],
    }
    if item.get("description"):
        entry["asserts"] = item["description"]
    if item.get("framework"):
        entry["framework"] = item["framework"]
    if item.get("type"):
        entry["type"] = item["type"]
    if item.get("angle"):
        # Pass an authored angle straight through to the ticket entry, so an
        # it-po's angle classification survives into ## Test Requirements
        # instead of being silently dropped. Declared in the test_spec item
        # schema (config/ac_store_schema.json), vocabulary in
        # docs/testing/test-angles.md. There is no double-cover to guard
        # against here: _build_test_requirements_section returns these
        # descriptors and never falls through to the derived floor.
        #
        # The value is NOT rejected here — the schema is the gate, and
        # dropping authored data on a vocabulary miss is worse than emitting
        # it. But the schema hook does not run on every path an AC can reach
        # the store by, so an unrecognised value is logged rather than
        # passed through in silence.
        if item["angle"] not in _TEST_ANGLES:
            logger.warning(
                "AC %s test_spec entry %r declares an unrecognised test "
                "angle %r (known: %s); emitting it unchanged — see "
                "docs/testing/test-angles.md",
                ac_id,
                name,
                item["angle"],
                ", ".join(sorted(_TEST_ANGLES)),
            )
        entry["angle"] = item["angle"]
    if item.get("requires_db"):
        entry["requires_db"] = True
    return entry


def _has_authored_test_spec(ac: AcRecord) -> bool:
    """Return True when the it-po authored a non-empty test contract on this AC.

    An authored ``test_spec`` is an explicit statement that this work must be
    tested. It is deliberately independent of the assigned agent's ``produces``
    classification: the two questions "does this change production code?" and
    "did somebody specify tests for it?" are orthogonal, and conflating them is
    what caused 308 authored descriptors across 85 records to be discarded.

    Args:
        ac: Parsed AC record.

    Returns:
        True when test_spec is a non-empty list.
    """
    spec = ac.get("test_spec")
    return isinstance(spec, list) and len(spec) > 0


def _build_test_requirements_section(ac: AcRecord, ac_id: str) -> str:
    """Build the ## Test Requirements section, derived from the AC.

    Source-of-truth order:
      1. explicit ``test_spec`` on the AC (authored by it-po) — preferred;
      2. otherwise derive stubs from the Gherkin ``criteria`` Then-clauses.

    Either way the tests are derived from the AC — never a hardcoded ``tests: []``
    stub — so the ticket-level Test Requirements guard passes by construction and
    test-writer receives a real, AC-derived contract. Returns an empty string
    only when the AC explicitly sets ``test_required: false`` (genuinely
    test-free), in which case the caller omits the section.

    Args:
        ac: Parsed AC record.
        ac_id: The AC id.

    Returns:
        Formatted ``## Test Requirements`` markdown block, or ``""`` when the AC
        is explicitly marked test-free.
    """
    if ac.get("test_required") is False:
        return ""

    descriptors = _test_descriptors_from_spec(ac, ac_id)
    if not descriptors:
        descriptors = _derive_tests_from_criteria(ac, ac_id)

    # BO-2900g-1 / BO-2900g-1-i: the reachability floor is universal — every
    # route's finalised plan passes through this one check, which is a no-op
    # (dedupe) when a reachability entry already made it into `descriptors`
    # (e.g. via _derive_tests_from_criteria's own unconditional append) and
    # appends exactly one sentinel entry otherwise (the authored-test_spec
    # route, which previously received no generator-added entries at all).
    descriptors = _ensure_reachability_floor(ac_id, descriptors)

    try:
        # sort_keys=False is REQUIRED: 'name' must stay the first key in each test
        # item so check_ticket_test_requirements._TESTS_ENTRY_RE ("- name: \\S+")
        # and the --verify guard-equivalence regex both match. Do not enable sorting.
        block = yaml.dump(
            {"tests": descriptors},
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        ).rstrip()
    except yaml.YAMLError as exc:
        logger.warning("Could not serialise derived test descriptors to YAML: %s", exc)
        return ""

    return "\n".join([
        "## Test Requirements",
        "",
        "```yaml",
        block,
        "```",
        "",
    ])
