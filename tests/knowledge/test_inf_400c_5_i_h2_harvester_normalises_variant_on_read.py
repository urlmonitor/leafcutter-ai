"""
MODULE: test_inf_400c_5_i_h2_harvester_normalises_variant_on_read
GOAL: Regression test for the H-2 fast-lane pr-review finding on AC
    INF-400c-5-i: the harvester's routing check compared a raw on-disk
    ``entry_kind`` directly against ``_KNOWN_ENTRY_KINDS`` with no
    normalisation, so a legacy or hand-written record already on disk under
    a separator/case variant of a routable kind (this AC's own Given
    clause: "component_convention" vs "component-convention") was
    misreported unroutable even though its normalised form IS a known kind.
AC: INF-400c-5-i (source_ac), H-2 fix

WHY THIS TEST EXISTS: every pre-existing normalisation test in this suite
(``test_inf_400c_5_i.py``) drives ``emit_knowledge.py``'s CLI -- the WRITE
path. Nothing exercised the harvester's READ path with a variant spelling
already sitting in the sink, which is exactly how a legacy or hand-written
record would arrive (bypassing the emission CLI entirely). This test writes
a variant-spelled ``entry_kind`` DIRECTLY into a sink file -- never through
``emit_knowledge.py`` -- and calls the REAL ``harvest()`` function (loaded
from source, unmocked capture_fn) to assert it is routed, proving
``harvest_learnings.py`` normalises on read through the SAME shared
function ``emit_knowledge.py`` uses on write
(``entry_kind_vocabulary.resolve_canonical``).

CONFIRMED RED against the pre-fix harvester: before the H-2 fix, the
routing check at the bottom of ``harvest()`` was
``if entry_kind not in _KNOWN_ENTRY_KINDS:`` -- a raw, unnormalised
membership test. A mangled-case/underscore variant of a real vocabulary
member (e.g. ``AGENT-FRONTMATTER`` mangled to ``AGENT_FRONTMATTER``) is
never itself a literal member of ``_KNOWN_ENTRY_KINDS`` (every member is
declared lower-case/hyphenated), so this test's core assertion
(``result.skipped_unknown == 0``) would fail with
``result.skipped_unknown == 1`` and ``result.routed == 0`` against that
prior implementation -- independently verified by reverting the fix locally
and re-running this exact test file, which failed exactly that way.
"""
# @ac-tag: INF-400c-5-i

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HARVEST_PATH = _REPO_ROOT / "scripts" / "knowledge" / "harvest_learnings.py"
_VOCAB_CONFIG = _REPO_ROOT / "config" / "entry_kind_vocabulary.json"

# Loaded by file path (the same importlib.util.spec_from_file_location
# convention already used by tests/knowledge/test_harvest_learnings.py and
# siblings, since scripts/knowledge/ is a standalone-script directory, not
# an importable package) under a name distinct from every other test
# module's registration, so this file can run alongside the rest of the
# suite in one pytest process without sys.modules collisions.
_spec = importlib.util.spec_from_file_location(
    "harvest_learnings_inf400c5i_h2", _HARVEST_PATH
)
assert _spec is not None and _spec.loader is not None, f"could not load spec for {_HARVEST_PATH}"
_mod: Any = importlib.util.module_from_spec(_spec)
# Must be registered in sys.modules BEFORE exec_module: harvest_learnings.py
# uses @dataclasses.dataclass, and dataclasses._is_type() looks up
# sys.modules[cls.__module__] while processing the class body -- an
# unregistered module name makes that lookup return None and crash with
# AttributeError. Mirrors tests/knowledge/test_harvest_learnings.py's own
# ``sys.modules["harvest_learnings"] = _mod`` line, under a distinct name so
# the two test files' independent loads never collide in one pytest session.
sys.modules["harvest_learnings_inf400c5i_h2"] = _mod
_spec.loader.exec_module(_mod)

harvest = _mod.harvest


def _write_sink(path: Path, events: list[dict]) -> None:
    """Write a JSONL sink file from a list of event dicts (mirrors
    ``tests/knowledge/test_harvest_learnings.py``'s helper of the same
    name)."""
    with open(path, "w", encoding="utf-8") as fh:
        for ev in events:
            fh.write(json.dumps(ev) + "\n")


def test_harvester_routes_a_variant_spelled_legacy_entry_kind_written_directly_to_the_sink(
    tmp_path: Path,
) -> None:
    # covers: INF-400c-5-i
    # angle: real_artifact (H-2 fast-lane pr-review fix)
    """A variant-spelled ``entry_kind`` (separator/case variant of a REAL
    vocabulary member, read from the actual declared config -- never a
    hand-typed guess) written DIRECTLY into the sink -- as a legacy or
    hand-written record would be, bypassing ``emit_knowledge.py`` entirely
    -- must be routed by the real harvester and counted under its
    canonical spelling, not reported as unroutable.
    """
    vocab = json.loads(_VOCAB_CONFIG.read_text(encoding="utf-8"))
    members = sorted(vocab["members"].keys())
    canonical = next(m for m in members if "-" in m)
    variant = canonical.upper().replace("-", "_")
    assert variant != canonical, "sanity: the mangled variant must actually differ"

    sink_path = tmp_path / "knowledge_emissions.jsonl"
    dest_path = tmp_path / "captured_learning.md"
    real_text = "A legacy record already on disk under a separator/case variant."
    event = {
        "event": "knowledge_captured",
        "timestamp": "2026-09-14T00:00:00Z",
        "agent": "test-writer",
        "component": "infrastructure",
        "destination": str(dest_path),
        "entry_kind": variant,
        "text": real_text,
    }
    _write_sink(sink_path, [event])

    result = harvest(sink_path=sink_path, state_path=tmp_path / "state.json")

    assert result.skipped_unknown == 0, (
        f"the variant-spelled entry_kind {variant!r} (of canonical "
        f"{canonical!r}) was misreported unroutable; "
        f"unroutable_by_kind={result.unroutable_by_kind!r}"
    )
    assert result.routed == 1, f"expected the variant to be routed exactly once; result={result!r}"
    assert dest_path.exists(), "the harvester must have written the routed destination file"
    assert real_text in dest_path.read_text(encoding="utf-8")
    assert result.by_kind.get(canonical) == 1, (
        "the routed record must be counted under its CANONICAL spelling "
        f"({canonical!r}), not the on-disk variant {variant!r}; "
        f"by_kind={result.by_kind!r}"
    )
