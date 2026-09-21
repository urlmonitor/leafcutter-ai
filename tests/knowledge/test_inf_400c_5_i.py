"""
MODULE: test_inf_400c_5_i
GOAL: RED test stubs for AC INF-400c-5-i -- separator and case variants of
    one entry_kind normalise to a single canonical (hyphenated, lower-case)
    value before it is compared against the declared vocabulary.
AC: INF-400c-5-i (source_ac)
DEPENDS ON: INF-400c-5 (the declared vocabulary + emission helper CLI this
    module assumes; see test_inf_400c_5.py's module docstring for the full
    assumed contract of ``config/entry_kind_vocabulary.json`` and
    ``scripts/knowledge/emit_knowledge.py``).

CONTRACT ASSUMED HERE, ADDITIONALLY: a shared, importable normalisation
function, ``normalize_entry_kind(value: str) -> str``, living in
``scripts/knowledge/entry_kind_vocabulary.py`` (a plain-data/helper module
alongside the CLI, not itself a CLI) so it can be applied identically at
both the emission helper and the harvester read path from one place, per
this AC's it_requirements. Lower-cases the value and treats ``_`` and ``-``
as the same separator; does not touch any other character.

WHAT IS EXPECTED TO BE RED AND WHY: neither
``scripts/knowledge/entry_kind_vocabulary.py`` nor
``scripts/knowledge/emit_knowledge.py`` exists yet in this worktree, so
every test below fails at import / subprocess-invocation time until
python-coder authors them.
"""
# @ac-tag: INF-400c-5-i

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_VOCAB_MODULE_PATH = _REPO_ROOT / "scripts" / "knowledge" / "entry_kind_vocabulary.py"
_EMIT_SCRIPT = _REPO_ROOT / "scripts" / "knowledge" / "emit_knowledge.py"
_VOCAB_CONFIG = _REPO_ROOT / "config" / "entry_kind_vocabulary.json"

_TIMEOUT_SECONDS = 30


def _load_normalize_fn() -> Any:
    """Import scripts/knowledge/entry_kind_vocabulary.py by file path (the
    same importlib.util.spec_from_file_location convention already used by
    test_harvest_learnings.py for the sibling harvest_learnings.py module,
    since this is a standalone script directory, not an importable package).

    Raises FileNotFoundError (RED) until the module exists.
    """
    spec = importlib.util.spec_from_file_location(
        "entry_kind_vocabulary", _VOCAB_MODULE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.normalize_entry_kind


def _run_emit(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_EMIT_SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=_TIMEOUT_SECONDS,
        check=False,
    )


def test_underscore_and_hyphen_variants_normalise_to_the_same_value() -> None:
    # covers: INF-400c-5-i
    # angle: criterion
    """Then the value is normalised ... by lower-casing it and treating an
    underscore and a hyphen as the same separator, and "component_convention",
    "component-convention", "Component-Convention" and "COMPONENT_CONVENTION"
    all resolve to one canonical member.

    Uses the AC's own Given-clause examples verbatim.
    """
    normalize_entry_kind = _load_normalize_fn()
    variants = [
        "component_convention",
        "component-convention",
        "Component-Convention",
        "COMPONENT_CONVENTION",
    ]
    normalised = {normalize_entry_kind(v) for v in variants}
    assert len(normalised) == 1, f"expected all variants to collapse to one value, got {normalised}"
    assert normalised == {"component-convention"}, (
        "the canonical spelling must be the hyphenated lower-case form"
    )


def test_normalisation_is_case_insensitive_on_a_second_example() -> None:
    # covers: INF-400c-5-i
    # angle: boundary
    """The AC also names "agent_memory"/"agent-memory" as an independent
    second example -- covering the boundary of a value with no upper-case
    variant at all supplied by the caller, only the separator swap.
    """
    normalize_entry_kind = _load_normalize_fn()
    assert normalize_entry_kind("agent_memory") == normalize_entry_kind("agent-memory")
    assert normalize_entry_kind("agent_memory") == "agent-memory"


def test_normalisation_never_invents_a_member_that_is_still_out_of_vocabulary(
    tmp_path: Path,
) -> None:
    # covers: INF-400c-5-i
    # angle: failure
    """And normalisation never invents a member: a normalised value that is
    still not in the vocabulary stays out of the vocabulary and is handled
    as an out-of-vocabulary value.

    Exercised through the REAL emission helper CLI (not just the pure
    normalize function) so the observed behaviour is the one an agent
    actually gets: normalising "Totally_Bogus-Kind" must not accidentally
    coerce it into any real member.
    """
    sink_path = tmp_path / "knowledge_emissions.jsonl"
    result = _run_emit(
        "--agent", "test-writer",
        "--component", "infrastructure",
        "--destination", str(tmp_path / "wherever.md"),
        "--entry-kind", "Totally_Bogus-Kind",
        "--text", "This normalised value is still not a vocabulary member.",
        "--sink", str(sink_path),
    )
    assert result.returncode == 0, "rejection must still be non-fatal (see INF-400c-5-iii)"
    assert not sink_path.exists() or sink_path.read_text(encoding="utf-8").strip() == "", (
        "a normalised-but-still-unknown entry_kind must never be written to the sink"
    )


def test_canonical_spelling_written_to_the_sink_is_hyphenated_lower_case(
    tmp_path: Path,
) -> None:
    # covers: INF-400c-5-i
    # angle: real_artifact
    """And the canonical spelling -- the one form written into the sink and
    used in every report -- is the hyphenated lower-case form.

    Picks a REAL vocabulary member from the declared config (not a guessed
    literal), mangles its case/separator, emits it via the real CLI, and
    reads the ACTUAL sink file back to assert the stored entry_kind is the
    canonical spelling, not the caller's variant spelling.
    """
    vocab = json.loads(_VOCAB_CONFIG.read_text(encoding="utf-8"))
    members = sorted(vocab["members"].keys())
    assert members, "sanity: need at least one real vocabulary member"
    canonical = members[0]
    mangled = canonical.upper().replace("-", "_")

    sink_path = tmp_path / "knowledge_emissions.jsonl"
    result = _run_emit(
        "--agent", "test-writer",
        "--component", "infrastructure",
        "--destination", str(tmp_path / "wherever.md"),
        "--entry-kind", mangled,
        "--text", "A real learning body for the canonical-spelling round trip.",
        "--sink", str(sink_path),
    )
    assert result.returncode == 0
    assert sink_path.exists(), f"expected {canonical!r} (mangled as {mangled!r}) to be accepted"
    lines = [ln for ln in sink_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["entry_kind"] == canonical, (
        f"sink must store the canonical spelling {canonical!r}, not the caller's "
        f"variant spelling; got {event['entry_kind']!r}"
    )
