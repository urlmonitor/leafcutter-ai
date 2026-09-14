"""
MODULE: unit_tests/commit_guardian/test_hook_registration_inventory.py
COVERS: KI-TQ-007 (pattern), KI-CG-021 (instance)

GOAL: Answer the question six rounds of adversarial review never asked about
    check_identifier_uniqueness.py — *what invokes this in production?* — as a
    standing, mechanical assertion over the whole commit-guardian hook
    directory, so the next unregistered gate fails on the day it is written
    rather than after it has been hardened five times.

BUSINESS CONTEXT: KI-TQ-007 records that rounds one through five each verified
    a gate by importing the module or running the script directly, and every
    one of those verifications was accurate. Round six asked what registered
    it and the answer was nothing. Nothing in 3,772 passing tests could
    distinguish that gate from one that had never been wired up, because
    nothing in the suite looked outside the source tree at a *registry*.

    This module is that missing look. It is deliberately an inventory over the
    whole directory rather than the per-AC registration test KI-TQ-007
    proposes: a per-AC test has to be remembered by the author of hook number
    nineteen, and the defect class is precisely that such things are not
    remembered.

ARCHITECTURE: Two assertions, both against SOURCE, never against build output.

    KI-TQ-007's stated remedy — "assert the hook's id appears in the deployed
    .pre-commit-config.yaml" — cannot be implemented as written. That file is
    gitignored build output emitted by build.py; asserting against it would
    verify the generator's last run rather than the committed registry, and it
    is absent entirely in a fresh clone. The source of truth for registration
    is hooks_manifest.hooks in templates/scripts/commit_guardian/
    commit_guardian.json, so that is what is read here.

    Scope is taken from the repository's own definition of a hook script —
    hook_parity.hook_script_patterns and hook_parity.excluded_scripts — rather
    than a second hardcoded list, so this test and check_hook_parity.py cannot
    drift apart about what counts as a hook.

    The project root is resolved from this file's location, never from
    Path.cwd() (the KI-CG-027 defect), so the test gives the same verdict from
    any working directory.

    RELATIONSHIP TO EXISTING GATES — this duplicates neither:
      - check_hook_trigger_reachability.py iterates the REGISTRY asking "can
        any tracked path fire this gate?". A script absent from the registry
        is invisible to it.
      - check_hook_parity.py compares script sets across DIRECTORIES and hook
        ids across MANIFESTS. It never asks whether a script on disk is named
        by any manifest entry.
    The unasked question is disk -> manifest, and it is asked below.
"""

from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GUARDIAN_DIR = PROJECT_ROOT / "templates" / "scripts" / "commit_guardian"
MANIFEST_PATH = GUARDIAN_DIR / "commit_guardian.json"

# ---------------------------------------------------------------------------
# Ratchet baseline — hook scripts that exist on disk with no hooks_manifest
# entry. 18 at 2524993b9 (2026-09-14); 16 after check_pytest_style.py and
# check_sql_dependencies.py were deleted as bybit-trader residue; 14 now that
# two non-hooks are listed in hook_parity.excluded_scripts.
#
# THIS LIST MAY ONLY SHRINK. Every entry is a script that pre-commit never
# runs. Adding to it would make this test the rubber stamp it exists to
# prevent; to clear an entry, either register the script in
# hooks_manifest.hooks or delete it, then remove the line here.
#
# The remaining fourteen are all KNOWN AND WANTED — none is a candidate for
# deletion. Five of them (check_folder_density, check_test_fixture_bloat,
# check_sql_complexity, check_debug_scripts, check_ac_done_on_merge) need no
# code work and are verified safe to register, but registering them adds
# package-registry entries, which check-package-surface-declaration refuses
# unless a cited acceptance criterion carries `package_surface: true`. That
# criterion does not exist yet, so the registration is queued behind it rather
# than forced through. The other nine each need real work first — a ratchet over
# existing violations, a crash fix, or an argv fix — scheduled after the
# file-length gate is fully integrated. The comments below record what each is
# waiting on, measured against the tree at this commit.
# ---------------------------------------------------------------------------
UNREGISTERED_BASELINE: frozenset[str] = frozenset(
    {
        # Superseded in practice by check-done-proof (registered + required in
        # CI). Also near-blind: _ID_REGEX is $-anchored, so a suffixed id like
        # TQ-100b-4-i never matches — it sees 275 of 4,032 records.
        "check_ac_coverage.py",
        # READY TO REGISTER — blocked only on a package_surface AC. Cannot block
        # a commit: main() returns 0 unconditionally and the __main__ guard
        # swallows OSError/ValueError into exit 0. Belongs on the post-merge
        # stage. Note the call direction: it INVOKES mark_ac_done.py, whose
        # docstring back-reference to this hook was misread as an invoker once.
        "check_ac_done_on_merge.py",
        # READY TO REGISTER — blocked only on a package_surface AC. Fully
        # config-driven, so portable; vacuous here because debugging/ is
        # untracked. Must be registered always_run with no files key: a
        # location-anchored `^debugging/scripts/` regex matching nothing is
        # classified UNREACHABLE, not NOTHING-TO-MATCH.
        "check_debug_scripts.py",
        # Wanted. Nothing enforces cyclomatic complexity today (ruff.toml
        # selects only E, F, E722 — no C901). Needs a shrink-only ratchet first:
        # 79 over-limit functions across 50 files at max_score 15.
        "check_complexity.py",
        # Runs again as of this commit (the _project_root NameError is fixed),
        # but its output is advisory and lands on the passing path, where a
        # hook's stdout is discarded (KI-CG-026). Needs verbose: true to be
        # worth registering.
        "check_doc_coverage.py",
        # Advisory, exits 0, only 13 findings. Needs verbose: true and a parser
        # fix — it reads DECISION HISTORY lines as DOC_LINKS paths (3 of the 13).
        "check_doc_links.py",
        # Wanted. ruff carries no D rules, so nothing enforces docstrings.
        # Needs an unhandled docstring_parser.ParseError caught and a ratchet
        # over 617 violations in 74 of 127 in-scope files.
        "check_docstrings.py",
        # Rules 2-3 (new-file header fields) are cheap; rule 1 is the blocker —
        # 35 of 50 directories holding tracked .py have no README.md. Has a live
        # caller: doc-enforcer SKILL.md runs it with --report-legacy.
        "check_documentation.py",
        # READY TO REGISTER — blocked only on a package_surface AC. Safe because
        # the ratchet is built in: _classify_folders raises a violation only when
        # a folder crosses the limit IN THIS COMMIT, so the 113 directories
        # already over 15 report as warnings. Verified against a real staged set.
        "check_folder_density.py",
        # Concept is general, allowlist is not: it still permits bybit-trader's
        # app_launcher.py while REJECTING ruff.toml, SETUP.md, VERSION,
        # LEAFCUTTER_VERSION, build-self.sh and requirements-dev.txt — and it
        # fires on modify, not just add. Needs its allowlist rewritten.
        # check_documentation.py imports its constants, so it cannot just go.
        "check_root_files.py",
        # READY TO REGISTER — blocked only on a package_surface AC. Portable and
        # config-driven (unlike the deleted check_sql_dependencies.py, it
        # hardcodes no schema); vacuous here with zero tracked .sql, and there
        # for the consumers README.md line 38 has been promising it to.
        "check_sql_complexity.py",
        # Substantially superseded by done_proof.py, which reimplements the same
        # three tag positions. Warn mode today; 5,725 untagged test functions in
        # 642 of 644 files, so registering it verbose would be pure noise.
        "check_test_ac_tags.py",
        # READY TO REGISTER — blocked only on a package_surface AC. Inert by
        # design once registered: the test_fixture_bloat config key does not
        # exist, so config resolves to {}, enabled defaults False, and every
        # violation path returns 0. Arming it is a separate deliberate step.
        "check_test_fixture_bloat.py",
        # Registering as-is would be theatre: main() ignores argv and reads
        # paths from stdin (:151-152), but pre-commit passes filenames as
        # arguments and leaves stdin empty, so it would check zero files and
        # always pass. Needs sys.argv[1:] preferred first.
        "check_ticket_test_requirements.py",
    }
)

_SCRIPT_IN_ENTRY = re.compile(r"([A-Za-z0-9_]+\.py)")
_ALWAYS_EXCLUDED = frozenset({"__init__.py", "README.md"})


def _load_manifest() -> dict:
    """Read the canonical commit_guardian.json from the template source tree."""
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _registered_script_names(manifest: dict) -> set[str]:
    """Every .py filename a hooks_manifest entry names, via `script` or `entry`.

    Both keys are read because an entry may invoke its script through
    run_hook.py in the `entry` command line while also declaring it in
    `script`; taking the union means a hook registered by either convention
    counts as registered.
    """
    names: set[str] = set()
    for hook in manifest.get("hooks_manifest", {}).get("hooks", []):
        script = hook.get("script")
        if script:
            names.add(script)
        names.update(_SCRIPT_IN_ENTRY.findall(hook.get("entry", "")))
    return names


def _hook_scripts_on_disk(manifest: dict) -> set[str]:
    """Hook scripts present in the guardian dir, per the repo's own patterns."""
    parity = manifest.get("hook_parity", {})
    patterns = parity.get("hook_script_patterns", ["check_*.py"])
    excluded = set(parity.get("excluded_scripts", [])) | _ALWAYS_EXCLUDED

    found: set[str] = set()
    for directory in (GUARDIAN_DIR, GUARDIAN_DIR / "hooks"):
        if not directory.is_dir():
            continue
        for path in directory.glob("*.py"):
            if path.name in excluded:
                continue
            if any(fnmatch.fnmatch(path.name, pat) for pat in patterns):
                found.add(path.name)
    return found


def test_no_unregistered_hook_scripts_beyond_baseline() -> None:
    """No hook script may exist on disk without a hooks_manifest entry.

    This is the KI-TQ-007 assertion: a gate that no registry names cannot
    fire, no matter how green its own unit tests are. Set equality is used
    rather than a subset check so the baseline is forced to shrink when an
    entry is registered or deleted, and can never quietly grow.
    """
    manifest = _load_manifest()
    orphans = _hook_scripts_on_disk(manifest) - _registered_script_names(manifest)

    newly_unregistered = sorted(orphans - UNREGISTERED_BASELINE)
    assert not newly_unregistered, (
        "Hook script(s) on disk that no hooks_manifest entry invokes: "
        f"{newly_unregistered}. Nothing will ever run these — see KI-TQ-007 / "
        "KI-CG-021. Register each in hooks_manifest.hooks of "
        "templates/scripts/commit_guardian/commit_guardian.json, or delete it. "
        "Do NOT add it to UNREGISTERED_BASELINE."
    )

    now_registered = sorted(UNREGISTERED_BASELINE - orphans)
    assert not now_registered, (
        f"UNREGISTERED_BASELINE is stale: {now_registered} no longer "
        "unregistered (registered or deleted). Remove these lines from the "
        "baseline in this file — the ratchet only holds while it is exact."
    )


def test_every_registered_script_resolves_on_disk() -> None:
    """Every script a hooks_manifest entry names must exist.

    The other half of KI-TQ-007's "and that its script resolves": a manifest
    entry pointing at a filename that is not there is a gate that fails at
    invocation rather than one that silently never runs, but it is the same
    unasked question about the link between registry and disk.
    """
    manifest = _load_manifest()

    missing: list[str] = []
    for hook in manifest.get("hooks_manifest", {}).get("hooks", []):
        script = hook.get("script")
        if not script:
            continue
        if (
            not (GUARDIAN_DIR / script).is_file()
            and not (GUARDIAN_DIR / "hooks" / script).is_file()
        ):
            missing.append(f"{hook.get('id')} -> {script}")

    assert not missing, f"hooks_manifest entries naming a script that does not exist: {missing}"
