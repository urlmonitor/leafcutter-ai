#!/usr/bin/env python3
"""
MODULE: check_sink_parity
GOAL: Verify that all four shipped knowledge-capture emit surfaces (the
    signoff skill and the product-owner, business-analyst, it-po agent
    templates) resolve, in a given DEPLOYED install, to that same install's
    own declared knowledge-emission sink -- and that none of them carries a
    destination of its own.
BUSINESS CONTEXT: AC INF-400c-4-i closes a corpus-split defect: four shipped
    surfaces independently instruct an agent to append a knowledge_captured
    record, and if even one of them names a literal path rather than
    resolving the install's own build-time declaration, that install ends up
    with agents writing to two different files depending on which surface
    they followed. This check is the mechanical, behavioural proof required
    by the AC's own test_rationale -- it does not grep the surfaces' text for
    a string; it determines, by REAL EXECUTION, where an agent following
    each surface literally would append, and compares that against the
    install's own declared sink (AC INF-400c-4 /
    docs/architecture/adrs/ADR-034-knowledge-write-ownership.md).
ARCHITECTURE: A single CLI entry point (``main``) that composes three steps:
    (1) verify the deployed tree named by ``--target-dir`` is complete enough
    to inspect at all (the four canonical surface files, the deployed
    ``harvest_learnings.py``, and ``config/knowledge_sink.json`` all exist);
    (2) for each of the four surfaces, locate its append-INSTRUCTION
    paragraph (distinct from any paragraph that only discusses the telemetry
    stream historically) and resolve the destination it names, by invoking
    the deployed ``harvest_learnings.py --print-sink`` for real when the
    instruction names that invocation, or by treating a literal
    ``debugging/logs/*.jsonl`` path as itself the failure when the
    instruction still carries one; (3) compare every resolved destination
    against the install's own declared sink and report pass/fail per
    surface. This script is never itself deployed to a consumer's
    ``.leafcutter`` tree -- like its sibling ``check_consumer_install.py``
    and ``check_declaring_files.py`` (see the CI workflow, which invokes both
    from the package source clone), it inspects a DEPLOYED tree from outside
    it, so it ships with the package source only.

Usage::

    python scripts/ci/check_sink_parity.py --target-dir <deployed-project-root>

``--target-dir`` is the project root a real ``build.py`` run was pointed at
(the same argument ``check_consumer_install.py --target-dir`` takes), NOT the
deployed output root itself. The deployed root is derived as
``<target-dir>/.leafcutter`` (this package's own ``output_root_name``
default).

Surfaces inspected -- exactly these four canonical Claude-format deployed
files, never the mirrored ``.leafcutter/gemini/`` copies (a distinct concern
this check does not own):

    1. ``<deployed-root>/skills/signoff/SKILL.md``        id: "signoff"
    2. ``<deployed-root>/agents/product-owner.md``        id: "product-owner"
    3. ``<deployed-root>/agents/business-analyst.md``     id: "business-analyst"
    4. ``<deployed-root>/agents/it-po.md``                id: "it-po"

For each surface, the check splits its text into blank-line-delimited
paragraphs and locates the append-INSTRUCTION paragraph -- the first
paragraph mentioning both an imperative "emit" and the literal string
``knowledge_captured`` -- as distinct from any paragraph that only discusses
the telemetry stream historically (e.g. the signoff settlement/scope note,
which never uses an imperative "emit"). Within that one paragraph:

  (A code-fenced block that directly follows the paragraph, after a blank
  line, is read as part of it.) Before any mechanism is tried, EVERY
  ``emit_knowledge.py`` mention in the paragraph (each read up to the next
  backtick, newlines included) is scanned, and the surface FAILS if any carries
  ``--sink`` or ``--sink=`` -- so no other mechanism can mask a self-carried
  sink. The helper itself refuses flag abbreviations (``allow_abbrev=False``).
  Mechanisms, in precedence order:

- If it names a resolution invocation (a code span containing both
  ``harvest_learnings.py`` and ``--print-sink``), the check runs that
  invocation for real against the DEPLOYED copy at
  ``<deployed-root>/scripts/knowledge/harvest_learnings.py``, with its
  ``cwd`` set to ``--target-dir``, and takes stdout (stripped) as the
  surface's resolved destination.
- Otherwise, if it names an ``emit_knowledge.py`` invocation (AC INF-700b-1):
  without ``--sink`` the helper resolves the declared sink itself, so the
  check runs the DEPLOYED ``<deployed-root>/scripts/knowledge/emit_knowledge.py
  --print-sink`` for real (same ``cwd``, same comparison). An invocation that
  carries ``--sink <literal>`` is a self-carried destination and FAILS with a
  message containing "destination of its own" and that literal.
- Otherwise, if it names a literal path in backticks matching
  ``debugging/logs/*.jsonl``, that literal IS the surface's self-carried
  destination (the pre-AC / defective shape) -- this is never compared
  against the declared sink; carrying a destination of its own is itself the
  failure.
- Otherwise (neither found in the instruction paragraph, or no instruction
  paragraph could be located at all), the surface is reported as
  unparseable.

Every surface resolved via invocation is compared against the SAME install's
own build-time declaration (``<deployed-root>/config/knowledge_sink.json`` ->
key ``"knowledge_emission_sink"``). All four must resolve to exactly that
value for the check to pass.

Before any per-surface inspection, the declaration itself is checked against
two further, independently-exercisable failure branches (AC INF-400c-4) that
fire regardless of whether every surface agrees with it:

- Branch 2 -- the declared sink IS the install's own
  ``"operational_telemetry_stream"`` (the same declaration's other key).
  This is the settlement discriminator: an implementation that "ends" the
  emitter/reader disagreement by repointing everything at the shared
  operational file is rejected outright, even with unanimous surface
  agreement.
- Branch 3 -- the declared sink is not an ABSOLUTE path. A relative declared
  value lets each process finish the resolution against its own current
  working directory, reproducing the per-working-directory split this AC
  exists to end, even with unanimous, verbatim surface agreement.

A fourth declaration check (AC INF-500d-4-iii, ADR-069) follows those two and
runs on the same terms: ``operational_log_root`` and ``feedback_sink`` must be
present and absolute, every file-valued key must sit directly under
``operational_log_root``, and ``feedback_sink`` must not equal another stream.
A violation prints ``FAIL declared-log-root: <key>=<value> ...`` and exits 1.

Exit codes::

    0   Exactly four surfaces were inspected and every one resolves -- via a
        real invocation, never a literal -- to the project's declared sink,
        and the declared sink itself violates neither branch 2 nor branch 3.
    1   Either the declared sink itself violates branch 2 or branch 3 (in
        which case per-surface inspection is skipped entirely and stdout
        names the violation as ``FAIL declared-sink: ...``), or at least one
        surface fails: it carries a literal destination of its own, its
        resolved value does not match the declared sink, or its instruction
        paragraph could not be parsed. stdout names every failing surface by
        id.
    2   Usage/environment error: --target-dir does not exist, or the
        deployed tree is missing one or more of the four canonical surface
        files, the deployed harvest_learnings.py, or
        config/knowledge_sink.json (a target that was never actually built,
        or was built before the ``operational_telemetry_stream`` key
        existed).

Stdout contract: a line of the exact form ``Inspected N surfaces:
<comma-separated ids>`` where N MUST equal 4 whenever all four canonical
files were found AND the declared sink itself passes branches 2 and 3 -- a
check that silently found none must never report success. This line is
skipped entirely when the declaration itself is rejected (branch 2 or 3),
since no surface is inspected in that case; the ``FAIL declared-sink: ...``
line is printed instead. On a per-surface failure, one line per failing
surface: ``FAIL <surface-id>: <reason>``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Sibling import: scripts/ci is sys.path[0] when this runs as a script. The
# emit-mechanism half lives in _sink_parity_emit.py (file-size limit).
from _sink_parity_emit import (
    SurfaceResult,
    _compare_resolved,
    _emit_invocations,
    _self_carried_sink_failure,
)

_OUTPUT_ROOT_NAME = ".leafcutter"

# Matches a resolution invocation naming both the harvester script and its
# side-effect-free query flag, wherever it appears in the instruction
# paragraph.
_INVOCATION_PATTERN = re.compile(r"harvest_learnings\.py[^`\n]*--print-sink")

# Matches a literal backtick-quoted JSONL path under debugging/logs/ -- the
# pre-AC self-carried destination shape.
_LITERAL_PATTERN = re.compile(r"`(debugging/logs/[\w./-]+\.jsonl)`")

# An append-instruction paragraph uses an imperative "emit" directed at the
# agent performing the append; a paragraph that only discusses the telemetry
# stream historically (e.g. "producers append to X while Y reads Z") never
# does. This is what lets the check skip the signoff settlement/scope note
# without knowing its exact future wording.
_IMPERATIVE_EMIT_PATTERN = re.compile(r"\bemit\b", re.IGNORECASE)

_SURFACES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("signoff", ("skills", "signoff", "SKILL.md")),
    ("product-owner", ("agents", "product-owner.md")),
    ("business-analyst", ("agents", "business-analyst.md")),
    ("it-po", ("agents", "it-po.md")),
)


def _deployed_root(target_dir: Path) -> Path:
    return target_dir / _OUTPUT_ROOT_NAME


def _surface_path(target_dir: Path, relative_parts: tuple[str, ...]) -> Path:
    return _deployed_root(target_dir).joinpath(*relative_parts)


def _find_instruction_paragraph(text: str) -> str | None:
    """Return the append-instruction paragraph, or ``None`` if none is found.

    Splits *text* on blank lines (the same convention every surface already
    uses to separate its numbered emission step from surrounding prose --
    see this module's docstring) and returns the first paragraph that reads
    as an instruction to emit: it uses the imperative "emit" AND names the
    ``knowledge_captured`` event. A paragraph that only discusses the
    telemetry stream historically (past or present tense, third person)
    never pairs those two, so it is never mistaken for the instruction.

    Pure function: no I/O, no shared-state mutation.
    """
    paragraphs = re.split(r"\n\s*\n+", text)
    for index, paragraph in enumerate(paragraphs):
        if _IMPERATIVE_EMIT_PATTERN.search(paragraph) and "knowledge_captured" in paragraph:
            return _with_fenced_command(paragraph, paragraphs[index + 1 :])
    return None


def _with_fenced_command(paragraph: str, following: list[str]) -> str:
    """Append the code-fenced command that directly follows *paragraph*, if any.

    A surface may put the ``emit_knowledge.py`` command in a fenced block
    separated from its introducing sentence by a blank line; that block is part
    of the same instruction. Only a paragraph that STARTS with a code fence is
    joined, so unrelated prose after the instruction is never pulled in.

    Pure function: no I/O, no shared-state mutation.
    """
    if following and following[0].lstrip().startswith("```"):
        return paragraph + "\n\n" + following[0]
    return paragraph


def _inspect_surface(
    surface_id: str,
    surface_path: Path,
    harvester_path: Path,
    target_dir: Path,
    declared_sink: str,
) -> SurfaceResult:
    """Inspect one surface and return whether it resolves to *declared_sink*.

    See this module's docstring for the exact three-mechanism precedence this
    mirrors.
    """
    try:
        text = surface_path.read_text(encoding="utf-8")
    except OSError as exc:
        return SurfaceResult(surface_id, False, f"could not read {surface_path}: {exc}")

    paragraph = _find_instruction_paragraph(text)
    if paragraph is None:
        return SurfaceResult(
            surface_id,
            False,
            "could not locate an append-instruction paragraph (unparseable)",
        )

    carried = _self_carried_sink_failure(surface_id, paragraph, declared_sink)
    if carried is not None:
        return carried

    if _INVOCATION_PATTERN.search(paragraph) is not None:
        return _compare_resolved(surface_id, harvester_path, target_dir, declared_sink)

    if _emit_invocations(paragraph):
        emit_path = harvester_path.parent / "emit_knowledge.py"
        return _compare_resolved(surface_id, emit_path, target_dir, declared_sink)

    literal_match = _LITERAL_PATTERN.search(paragraph)
    if literal_match is not None:
        return SurfaceResult(
            surface_id,
            False,
            f"carries a destination of its own ({literal_match.group(1)!r}) "
            "instead of resolving the declared sink at emit time -- the "
            f"surface resolves to {literal_match.group(1)!r} while the "
            f"install's declared sink is {declared_sink!r}",
        )

    return SurfaceResult(
        surface_id,
        False,
        "append-instruction paragraph names no harvest_learnings.py "
        "--print-sink invocation, no emit_knowledge.py invocation and no "
        "literal debugging/logs/*.jsonl path (unparseable)",
    )


def _any_surface_names_emit_helper(target_dir: Path) -> bool:
    """Return whether any readable surface file mentions ``emit_knowledge.py``."""
    for _surface_id, relative_parts in _SURFACES:
        try:
            text = _surface_path(target_dir, relative_parts).read_text(encoding="utf-8")
        except OSError:
            continue  # a missing/unreadable surface is reported by the caller
        if "emit_knowledge.py" in text:
            return True
    return False


def _verify_deployed_tree_complete(
    target_dir: Path,
) -> tuple[Path, str, str, list[str]]:
    """Verify the deployed tree has everything this check needs to inspect.

    Returns ``(harvester_path, declared_sink, operational_stream, missing)``.
    ``missing`` is a list of human-readable descriptions of anything absent;
    when it is non-empty the caller must exit 2 without attempting any
    inspection. ``declared_sink`` and ``operational_stream`` are ``""`` when
    the declaration itself is missing, unreadable, or does not name that key.
    """
    deployed_root = _deployed_root(target_dir)
    harvester_path = deployed_root / "scripts" / "knowledge" / "harvest_learnings.py"
    config_path = deployed_root / "config" / "knowledge_sink.json"

    missing: list[str] = []
    for surface_id, relative_parts in _SURFACES:
        path = _surface_path(target_dir, relative_parts)
        if not path.is_file():
            missing.append(f"{surface_id} surface ({path})")
    if not harvester_path.is_file():
        missing.append(f"deployed harvest_learnings.py ({harvester_path})")
    emit_path = harvester_path.parent / "emit_knowledge.py"
    if not emit_path.is_file() and _any_surface_names_emit_helper(target_dir):
        missing.append(f"deployed emit_knowledge.py ({emit_path})")
    if not config_path.is_file():
        missing.append(f"knowledge_sink.json ({config_path})")

    if missing:
        return harvester_path, "", "", missing

    try:
        config_data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return harvester_path, "", "", [f"{config_path} could not be read: {exc}"]

    declared_sink = config_data.get("knowledge_emission_sink")
    if not isinstance(declared_sink, str) or not declared_sink:
        return harvester_path, "", "", [
            f"{config_path} does not declare a 'knowledge_emission_sink'"
        ]

    operational_stream = config_data.get("operational_telemetry_stream")
    if not isinstance(operational_stream, str) or not operational_stream:
        return harvester_path, "", "", [
            f"{config_path} does not declare an 'operational_telemetry_stream'"
        ]

    return harvester_path, declared_sink, operational_stream, []


def _settlement_violation(declared_sink: str, operational_stream: str) -> str | None:
    """Return a failure reason if *declared_sink* itself violates the settlement.

    Two independent, mechanically-checkable branches, both required by AC
    INF-400c-4 regardless of whether every emit surface agrees with the
    declared value:

    Branch 2 -- the declared value IS the operational telemetry stream. The
    AC's required settlement is that the EMITTERS move onto a knowledge-only
    stream and the reader stays; repointing everything at the shared
    operational file "ends the disagreement" while producing the outcome the
    AC rejects, so it must fail even when every surface agrees with it.

    Branch 3 -- the declared value is not an ABSOLUTE path. A relative
    declared value lets each process finish the resolution against its own
    current directory, reproducing the original per-working-directory split
    the AC exists to end, even when every surface agrees with it verbatim.

    Returns ``None`` when neither branch fires. Pure function: no I/O, no
    shared-state mutation.
    """
    if Path(declared_sink) == Path(operational_stream):
        return (
            f"declared knowledge-emission sink {declared_sink!r} IS the "
            f"operational telemetry stream {operational_stream!r} -- the "
            "required settlement moves the EMITTERS onto a knowledge-only "
            "stream; repointing everything at the shared operational file "
            "is the settlement this AC rejects, even though every surface "
            "agrees with it"
        )
    if not Path(declared_sink).is_absolute():
        return (
            f"declared knowledge-emission sink {declared_sink!r} is not an "
            "absolute path -- a relative declared value lets each process "
            "finish the resolution against its own current directory, "
            "reproducing the per-working-directory split this AC exists to "
            "end, even though every surface agrees with it verbatim"
        )
    return None


_FILE_KEYS = ("feedback_sink", "knowledge_emission_sink", "operational_telemetry_stream")


def _log_root_violation(config_data: dict) -> str | None:
    """Return a failure reason if the declaration splits or mis-anchors the log root.

    AC INF-500d-4-iii (ADR-069): ``operational_log_root`` and ``feedback_sink``
    must be present and absolute, every file-valued key must sit directly under
    the root, and ``feedback_sink`` must not equal another stream. The reason
    names the offending key and value. Pure function: no I/O.
    """
    for key in ("operational_log_root", *_FILE_KEYS):
        value = config_data.get(key)
        if not isinstance(value, str) or not Path(value).is_absolute():
            return f"{key}={value!r} is missing or not an absolute path"
    root = Path(config_data["operational_log_root"])
    for key in _FILE_KEYS:
        if Path(config_data[key]).parent != root:
            return f"{key}={config_data[key]!r} does not sit directly under operational_log_root={str(root)!r}"
    feedback = config_data["feedback_sink"]
    for key in _FILE_KEYS[1:]:
        if Path(config_data[key]) == Path(feedback):
            return f"feedback_sink={feedback!r} equals {key}"
    return None


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="check_sink_parity",
        description=(
            "Verify all four shipped knowledge-capture emit surfaces resolve "
            "to a deployed install's own declared knowledge-emission sink."
        ),
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        required=True,
        help="Project root a real build.py run was pointed at (not the deployed output root itself).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns 0 (pass), 1 (surface failure), or 2 (usage/environment error)."""
    args = _parse_args(argv)
    target_dir: Path = args.target_dir.resolve()

    if not target_dir.is_dir():
        print(f"ERROR: --target-dir {target_dir} does not exist", file=sys.stderr)
        return 2

    harvester_path, declared_sink, operational_stream, missing = _verify_deployed_tree_complete(
        target_dir
    )
    if missing:
        print(
            "ERROR: deployed tree is incomplete -- this target was never "
            f"actually built. Missing: {'; '.join(missing)}",
            file=sys.stderr,
        )
        return 2

    settlement_failure = _settlement_violation(declared_sink, operational_stream)
    if settlement_failure is not None:
        print(f"FAIL declared-sink: {settlement_failure}")
        return 1

    config_path = _deployed_root(target_dir) / "config" / "knowledge_sink.json"
    try:
        log_root_failure = _log_root_violation(json.loads(config_path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {config_path} could not be re-read: {exc}", file=sys.stderr)
        return 2
    if log_root_failure is not None:
        print(f"FAIL declared-log-root: {log_root_failure}")
        return 1

    results = [
        _inspect_surface(surface_id, _surface_path(target_dir, relative_parts), harvester_path, target_dir, declared_sink)
        for surface_id, relative_parts in _SURFACES
    ]

    print(f"Inspected {len(results)} surfaces: {', '.join(r.surface_id for r in results)}")

    failures = [result for result in results if not result.ok]
    if not failures:
        return 0

    for failure in failures:
        print(f"FAIL {failure.surface_id}: {failure.reason}")
    return 1


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-14 [python-coder/INF-400c-4-i]: Created check_sink_parity.py.
#   Distinguishes the append-INSTRUCTION paragraph from any historical/
#   scope-note paragraph via the imperative-"emit" + "knowledge_captured"
#   pairing (blank-line-delimited paragraph split), rather than any
#   surface-specific string match, so it survives whatever exact wording
#   llm-expert lands for the settlement note (this AC's it_requirements
#   forbid deleting that note). A literal debugging/logs/*.jsonl match is
#   never compared against the declared sink -- carrying a destination of
#   its own is itself the failure, per the AC's hardened "no destination of
#   its own" wording. Not deployed to consumer installs: it inspects a
#   deployed tree from outside it, same pattern as check_consumer_install.py
#   and check_declaring_files.py (see .github/workflows/ci.yml, which
#   invokes both directly from the package source clone) -- confirmed no
#   scripts/ci/*.py file appears in any build_phases*.py deploy_map before
#   adding this one. (#TICKETLESS reason=ac-scoped-fastlane-build-INF-400c-4-i)
# - 2026-09-14 [python-coder/INF-400c-4]: Added the two remaining parity
#   failure branches this AC's own test_spec requires and INF-400c-4-i's
#   narrower scope did not cover: branch 2 (the declared sink IS the
#   operational telemetry stream -- the settlement discriminator that
#   rejects repointing everything at the shared operational file even when
#   every surface agrees) and branch 3 (the declared sink is not an absolute
#   path, which lets each process finish resolution against its own current
#   directory). Both are checked once against the declaration itself
#   (`_settlement_violation`), before any per-surface inspection, so they
#   fire regardless of surface agreement. Also hardened branch 1's failure
#   message for a self-carried literal to additionally name the declared
#   sink it disagrees with, so the reported failure names both resolved
#   values and which side produced each, per the AC's own wording.
#   (#TICKETLESS reason=ac-scoped-fastlane-build-INF-400c-4)
# - 2026-10-09 [python-coder/INF-500d-4-iii]: Added _log_root_violation, run
#   after branches 2 and 3 (which are untouched): operational_log_root and
#   feedback_sink present and absolute, every file key directly under the
#   root, feedback_sink distinct from the other streams. (#INF-500d-4-iii)
# - 2026-10-20 [python-coder/INF-700b-1]: Added a third resolution
#   mechanism. The four surfaces now run the deployed emit_knowledge.py with
#   no --sink, so an emit invocation is resolved by running the deployed
#   `emit_knowledge.py --print-sink` for real; one carrying `--sink <literal>`
#   fails as a destination of its own. _find_instruction_paragraph now joins a
#   code-fenced block that directly follows the instruction paragraph (signoff
#   section 7 puts the command in its own block). INF-400c-4-i's criteria are
#   unchanged: following any surface still reaches the declared sink.
#   (#INF-700b-1)
# - 2026-10-20 [python-coder/INF-700b-1]: Closed pr-reviewer M-1. Every
#   emit_knowledge.py mention in the paragraph is scanned (to the next
#   backtick, newlines allowed) and any --sink / --sink= refuses the surface
#   BEFORE the mechanism precedence, so a prose mention, an unbackslashed wrap
#   or a named harvester command cannot mask it. A deployed tree whose surfaces
#   use the emit helper but lack emit_knowledge.py now exits 2. (#INF-700b-1)
# ====================================================================
