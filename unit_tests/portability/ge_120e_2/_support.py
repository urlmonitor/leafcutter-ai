"""
MODULE: unit_tests/portability/ge_120e_2/_support.py
GOAL: Shared path constants and fixture writers for the TDD red-baseline
    tests of AC GE-120e-2 — "Which checks work out their own change set is
    read from the manifest, not from the two that were caught." The tests
    live in ``test_ge_120e_2_determination.py`` (tests 1-6) and
    ``test_ge_120e_2_consumers_and_reachability.py`` (tests 7-8) in this
    package. The AC turns "does this check work out its own change set?"
    from a hand-written list of two observed offenders into a DECLARED,
    per-entry value on ``hooks_manifest.hooks[]`` (``change_set_source``),
    determined by a single callable that reads the manifest at run time.

BUSINESS CONTEXT: Ticket 30 of EPIC-TrustThatAGreenCheckActuallyChecked.
    Source AC: GE-120e-2. The AC's own ``test_spec`` supplies the eight test
    names used by this suite (seven behavioral/unit/integration + the
    mandatory reachability test) — authoritative over the ticket body's
    derived Gherkin per Source-of-Truth Discipline.

    architect-review's 2026-08-31 sign-off on this ticket resolved a
    conflict between the ticket's own ``## Test Requirements`` table (which
    names ``unit_tests/commit_guardian/test_ge_120e_2.py``) and this
    ticket's ``files_touched`` / the epic's out-of-process-harness
    convention (which name ``unit_tests/portability/test_ge_120e_2.py``) —
    in favour of ``unit_tests/portability/``, which is where this suite
    lives (split into ``unit_tests/portability/ge_120e_2/`` on 2026-11-16).
    architect-review also named GE-120e-2-i's ALREADY-COMMITTED test
    contract as binding prior art for this ticket's implementer: module
    ``scripts.commit_guardian.change_set_source``, callable
    ``determine_change_set_sources``, field name ``change_set_source``,
    values ``handed_by_commit_path`` / ``self_derived``. This suite honours
    that contract verbatim rather than re-deriving names from this ticket's
    prose alone.

CONTRACT ASSUMED (documented here so a reader — and GE-120e-2's implementer
    — does not have to reverse it out of assertions; NOT already fixed by a
    committed sibling test beyond the names above, so recorded explicitly):
    - Module: templates/scripts/commit_guardian/change_set_source.py
      (deployed by build_commit_guardian(), which copies every ``*.py`` in
      templates/scripts/commit_guardian/ verbatim to
      <target>/scripts/commit_guardian/ — confirmed by reading
      scripts/build_phases.py's ``build_commit_guardian()`` at
      authoring time; no separate deploy-manifest entry is required for a
      new ``*.py`` file in that directory).
    - ``determine_change_set_sources(manifest_path: Path) -> DeterminationResult``.
      Reads ``hooks_manifest.hooks[]`` from the JSON at ``manifest_path`` —
      the path given, NEVER a fallback to the installed manifest. A
      nonexistent or unreadable ``manifest_path`` raises an exception (an
      in-band, reported failure — not a silent empty result and not a
      silent fallback to some other manifest).
    - ``DeterminationResult`` exposes (plain data, per GE-120e-2-i's
      already-committed usage of exactly these three names):
        - ``.handed_its_files: list[str]`` — ids recorded
          ``change_set_source: "handed_by_commit_path"``.
        - ``.self_deriving: list[str]`` — ids recorded
          ``change_set_source: "self_derived"`` AND whose ``entry`` script's
          own source text references the shared derivation
          (``get_authored_change`` / ``_authored_change`` — see next
          bullet) — i.e. membership requires BOTH the declared value and a
          real check that the check actually uses the shared source, per
          this AC's own last Gherkin clause ("a check recorded as taking
          its own change set that obtains it by any other means is
          named ... reports a failure").
        - ``.failures: list[str]`` — ids that are missing the
          ``change_set_source`` key, carry a value outside the two-item
          vocabulary, OR are recorded ``self_derived`` but do not reference
          the shared source in their own script text.
      Every id in the manifest appears in EXACTLY ONE of these three lists
      (the candidate set is complete and partitioned, never a subset).
    - Compliance check for a ``self_derived`` entry is a STATIC text scan of
      the script file named by the entry's LAST whitespace-delimited token
      (``Path(entry.split()[-1])`` — the same token-extraction idiom already
      used by ``build_precommit.py``'s ``_check_hook_script_integrity``,
      reused here rather than invented fresh) for the substrings
      ``get_authored_change`` or ``_authored_change`` — NOT a subprocess
      execution of the check. This is required by the Implementation Notes'
      latency budget ("under 200ms ... must not spawn a subprocess per
      entry") and is exercised directly by this suite via planted fixture
      scripts that do/do not contain those substrings.
    - CLI entry point (resolves the required reachability angle, which the
      AC's own test_spec left undeclared): running
      ``python3 <path-to-change_set_source.py> <manifest_path>`` prints each
      failing id and exits 1 when ``result.failures`` is non-empty, exits 0
      otherwise. This mirrors every other ``check_*.py`` script in this
      directory (subprocess entry point via a bare positional path argument,
      not an import), so a future manifest entry could register this
      determination as an ordinary commit-guardian check without a shape
      change.

WHY THE FIXTURE MANIFEST, NEVER TODAY'S: per the AC's own coverage note, a
    test asserting today's ~59 manifest entries are all correctly recorded
    passes forever and cannot fail on the day the next self-deriving check
    is added without recording its source — the day this AC exists for.
    Every case in this suite drives the determination with an explicit,
    disposable fixture manifest. The one test that DOES read the real,
    installed manifest (test 7, in
    ``test_ge_120e_2_consumers_and_reachability.py``) only asserts a
    field-shape invariant and a zero-behavioural-diff regression guard —
    never that today's roster of checks is itself correctly classified.

WHY NO SUBPROCESS PER ENTRY / NO HARD-CODED COUNT: this repo's Implementation
    Notes for this AC are explicit that this determination runs at commit
    time under a 200ms budget and must not spawn a subprocess per manifest
    entry, and that no entry count may be hard-coded anywhere (it was 59 in
    this manifest at test-authoring time and moves with every addition).
    Every fixture manifest in this suite is sized arbitrarily and no
    assertion depends on the real manifest's current entry count.

====================================================================
DECISION HISTORY
====================================================================
- 2026-11-16 [split-oversized-tests]: Split from the single
  unit_tests/portability/test_ge_120e_2.py, which stood over the 400-line
  file-size limit and so could not take the class-level attribute
  declarations mypy needed. This module keeps the path setup, the shared
  constants and the fixture writers; the ten tests moved unchanged into two
  test modules, each holding the guarded imports only it uses. The guarded
  imports lost their `# type: ignore` comments (see the comment at the
  determination import for the one that also lost its None fallback).
- 2026-08-31 [EPIC-TrustThatAGreenCheckActuallyChecked/30, GE-120e-2,
  test-writer]: Initial TDD red-baseline. scripts.commit_guardian.
  change_set_source does not exist yet (neither the template nor the
  deployed copy), so every test that imports determine_change_set_sources
  fails via self.fail() naming the missing dependency — the intended red
  state. Test 7 (added-field regression guard) additionally asserts, on the
  REAL installed manifest, that every entry already carries a valid
  change_set_source value — false today, and independently red until
  python-coder lands the per-entry field.
====================================================================
"""
# @ac-tag: GE-120e-2

from __future__ import annotations

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — make scripts/ and templates/scripts/commit_guardian/
# importable regardless of cwd, matching the sibling GE-120e-2-i /
# GE-120e-1 test files' established convention exactly.
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent.parent  # unit_tests/portability/ge_120e_2/ -> worktree root
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_COMMIT_GUARDIAN_TEMPLATES = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_REAL_MANIFEST_PATH = _COMMIT_GUARDIAN_TEMPLATES / "commit_guardian.json"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

_ALLOWED_SOURCE_VALUES = {"handed_by_commit_path", "self_derived"}

_DETERMINATION_MISSING_MSG = (
    "scripts.commit_guardian.change_set_source.determine_change_set_sources "
    "does not exist yet (checked only the scripts/commit_guardian/ deployed "
    "copy, via the dotted import scripts.commit_guardian.change_set_source — "
    "this import resolves against the deployed tree only and never consults "
    "templates/scripts/commit_guardian/ source). GE-120e-2 has not landed. "
    "See this test file's module docstring 'CONTRACT ASSUMED' for the exact "
    "shape required: determine_change_set_sources(manifest_path) -> a result "
    "exposing .handed_its_files / .self_deriving / .failures."
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------
def _write_fixture_manifest(tmp_dir: Path, hooks: list[dict], name: str = "fixture_commit_guardian.json") -> Path:
    """Write a standalone fixture manifest carrying the given hook entries.

    Per this AC's own coverage note, a fixture manifest — never today's — is
    what proves the determination reads the manifest at run time rather
    than a hand-written list of the two originally-observed offenders.
    """
    manifest_path = tmp_dir / name
    manifest_path.write_text(
        json.dumps({"hooks_manifest": {"hooks": hooks}}, indent=2),
        encoding="utf-8",
    )
    return manifest_path


def _write_handed_its_files_script(tmp_dir: Path, name: str = "check_handed.py") -> Path:
    """A fixture check that only ever inspects argv — never derives a diff."""
    path = tmp_dir / name
    path.write_text(
        '''"""Fixture handed-its-files check: inspects only argv-handed files."""
import sys


def main(argv: list[str]) -> int:
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
''',
        encoding="utf-8",
    )
    return path


def _write_compliant_self_deriving_script(tmp_dir: Path, name: str = "check_compliant_self_derived.py") -> Path:
    """A fixture check that genuinely takes its change set from the shared
    authored-change source (GE-120e-1's get_authored_change()) — the
    positive case for AC-4's "every check recorded as taking its own change
    set takes it from the shared source"."""
    path = tmp_dir / name
    path.write_text(
        f'''"""Fixture COMPLIANT self-deriving check: uses the shared source."""
import sys

sys.path.insert(0, {str(_COMMIT_GUARDIAN_TEMPLATES)!r})
from _authored_change import get_authored_change  # noqa: E402


def main() -> int:
    change = get_authored_change()
    return 1 if change.could_not_check else 0


if __name__ == "__main__":
    sys.exit(main())
''',
        encoding="utf-8",
    )
    return path


def _write_noncompliant_self_deriving_script(tmp_dir: Path, name: str = "check_noncompliant_self_derived.py") -> Path:
    """A fixture check RECORDED as self-deriving but that actually computes
    its own diff directly (never touches the shared source) — the exact
    misattribution AC-5's last clause exists to catch."""
    path = tmp_dir / name
    path.write_text(
        '''"""Fixture NON-COMPLIANT self-deriving check: derives its own diff."""
import subprocess
import sys


def main() -> int:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=False,
    )
    return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
''',
        encoding="utf-8",
    )
    return path
