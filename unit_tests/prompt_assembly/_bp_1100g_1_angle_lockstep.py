"""
MODULE: unit_tests/prompt_assembly/_bp_1100g_1_angle_lockstep.py
GOAL: Hold the three-way (R/G/T) angle-lockstep comparator and its fresh-
    subprocess twin, shared by test_bp_1100g_1.py and (by re-export)
    test_tq_500f_1_i_three_way_lockstep.py.
BUSINESS CONTEXT: TQ-500f-1-i widened BP-1100g-1's original two-way (R vs T)
    comparator to full three-way set equality across R (config/ac_store_schema.json
    test_spec[].angle), G (config/test_requirements.schema.json tests[].angle)
    and T (the taught set in templates/agents/test-writer.md), per that AC's
    own it_requirement: replace the one check in place rather than adding a
    second one beside it, so two lockstep checks can never disagree.
ARCHITECTURE: Split out of test_bp_1100g_1.py itself (GE-127b-1's file-size
    ratchet: that module was already over its 400-line limit at HEAD, so
    growing it further would be refused at commit time). test_bp_1100g_1.py
    re-exports ``_compare_three_way_angle_sets`` and ``_load_generated_angles``
    at its own module scope (a plain import, not a re-implementation), which
    is what lets test_tq_500f_1_i_three_way_lockstep.py's
    ``from test_bp_1100g_1 import (_compare_three_way_angle_sets, ...)``
    (THE TARGET CONTRACT that AC's own test file names) keep working.
COVERS: (support module — no test functions live here)
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

_R_LABEL = "config/ac_store_schema.json (test_spec[].angle)"
_G_LABEL = "config/test_requirements.schema.json (tests[].angle)"
_T_LABEL = "templates/agents/test-writer.md (taught set)"


def _load_generated_angles(schema_path: Path) -> set[str]:
    """Read the generated-work-side (G) angle set from disk.

    TQ-500f-1-i: G is ``config/test_requirements.schema.json``'s
    ``$defs.test_entry.properties.angle.enum`` — the vocabulary a generated
    ticket's ``## Test Requirements`` entries may declare. Raises (does not
    swallow) if the file is missing, matching the R-side loader's fail-loud
    convention — a missing source must fail the test, never fall back to a
    hand-typed literal.

    Args:
        schema_path: Path to ``config/test_requirements.schema.json``.

    Returns:
        The set of permitted angle-kind strings declared on the generated
        side.
    """
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    enum = schema["$defs"]["test_entry"]["properties"]["angle"].get("enum") or []
    return set(enum)


def _compare_three_way_angle_sets(
    emittable: set, generated: set, taught: dict
) -> list[str]:
    """Full set-equality across R (emittable), G (generated), T (taught).

    TQ-500f-1-i: today's R-vs-T comparison misses a kind dropped from G
    alone. This compares the full sets pairwise-by-name across all three
    lists and, for every angle where the three lists disagree, reports one
    message naming the angle, which list(s) LACK it and which list(s) CARRY
    it — by file path, never merely "the sets differ".

    Args:
        emittable: R — the requirement-side angle set (config/ac_store_schema.json).
        generated: G — the generated-work-side angle set
            (config/test_requirements.schema.json).
        taught: T — the taught-set mapping (name -> distinguishing rule) from
            templates/agents/test-writer.md.

    Returns:
        One mismatch message per angle name where R, G and T do not all
        agree; empty when the three sets are identical.
    """
    taught_names = set(taught.keys())
    all_names = emittable | generated | taught_names
    mismatches: list[str] = []
    for name in sorted(all_names):
        sides = {
            _R_LABEL: name in emittable,
            _G_LABEL: name in generated,
            _T_LABEL: name in taught_names,
        }
        if len(set(sides.values())) == 1:
            continue  # all three agree (all present or all absent) — no mismatch
        carrying = sorted(label for label, present in sides.items() if present)
        lacking = sorted(label for label, present in sides.items() if not present)
        mismatches.append(
            f"angle '{name}': lacking from {lacking}; carried by {carrying}"
        )
    return mismatches


# ---------------------------------------------------------------------------
# Standalone comparator script, run as a genuinely fresh subprocess for the
# real_artifact angle. Inlined rather than imported so the process boundary
# is real — a fresh `python -c` invocation, not importlib.reload(). Fails
# loudly (non-zero exit + MISSING_SOURCE marker) when any source path is
# missing, rather than silently falling back to a literal.
# ---------------------------------------------------------------------------
_COMPARE_SCRIPT = textwrap.dedent(
    r"""
    import json, re, sys
    from pathlib import Path
    import yaml

    schema_path = Path(sys.argv[1])
    test_req_schema_path = Path(sys.argv[2])
    template_path = Path(sys.argv[3])

    for source_path in (schema_path, test_req_schema_path, template_path):
        if not source_path.is_file():
            print(f"MISSING_SOURCE: {source_path}", file=sys.stderr)
            sys.exit(2)

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    test_spec = schema["properties"]["test_spec"]
    array_branches = [b for b in test_spec["oneOf"] if b.get("type") == "array"]
    item_schema = array_branches[0]["items"]
    emittable = set(item_schema.get("properties", {}).get("angle", {}).get("enum") or [])

    test_req_schema = json.loads(test_req_schema_path.read_text(encoding="utf-8"))
    generated = set(
        test_req_schema["$defs"]["test_entry"]["properties"]["angle"].get("enum") or []
    )

    text = template_path.read_text(encoding="utf-8")
    start, end = "<!-- TAUGHT-TEST-ANGLES:START -->", "<!-- TAUGHT-TEST-ANGLES:END -->"
    taught = {}
    if start in text and end in text:
        block = text.split(start, 1)[1].split(end, 1)[0]
        m = re.search(r"```ya?ml\s*\n(.*?)```", block, re.DOTALL)
        if m:
            parsed = yaml.safe_load(m.group(1))
            taught = parsed if isinstance(parsed, dict) else {}
    taught_names = set(taught.keys())

    # Full three-way set equality (TQ-500f-1-i) — the same rule
    # _compare_three_way_angle_sets applies in-process, re-implemented here
    # because this script runs as a genuinely fresh subprocess (the
    # real_artifact angle), never imported.
    all_names = emittable | generated | taught_names
    mismatches = [
        name
        for name in sorted(all_names)
        if len({name in emittable, name in generated, name in taught_names}) != 1
    ]
    print(json.dumps({
        "emittable": sorted(emittable),
        "generated": sorted(generated),
        "taught": sorted(taught_names),
        "mismatches": mismatches,
    }))
    sys.exit(0 if not mismatches else 1)
    """
)


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-25 [python-coder/TQ-500f-1-i]: Created. Widened BP-1100g-1's
  original two-way (R vs T) `_compare_angle_sets` in place to full three-way
  R/G/T set equality, then split out of test_bp_1100g_1.py (already over its
  400-line ratchet limit at HEAD) so the widening could land without growing
  that file past its GE-127b-1 previous length.
====================================================================
"""
