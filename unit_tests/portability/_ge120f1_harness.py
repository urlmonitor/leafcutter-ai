"""
MODULE: _ge120f1_harness
GOAL: Shared fixture vocabulary, deployed-manifest helpers, and the SHARED
    deployed-copy provisioning for the GE-120f-1 test family
    (test_ge_120f_1_*.py in this directory).
BUSINESS CONTEXT: Split out of the former monolithic test_ge_120f_1.py (673
    counted lines, over the check-file-size 400-line budget) so each split
    test file only carries the tests it drives — mirrors
    unit_tests/workflows/_quick_fix_harness.py's precedent (a leading
    underscore, `test_` absent, so pytest does not collect this as a test
    module).

    Every test in this family stands up a REAL deployed working copy via
    `scripts/build.py` (tens of seconds each) and mutates its REAL
    `commit_guardian.json`. Splitting one file into several must not
    multiply that cost by the split count. `pairing_copy()`/`gate_copy()`
    below are a PROCESS-WIDE cache — module-level state, built at most once
    per process no matter how many of this family's TestCase classes (in
    however many files) request a copy — so the whole family shares exactly
    TWO real deployed copies for an entire pytest run, down from the four
    the monolithic file's single `setUpClass` built.
ARCHITECTURE: `pairing_copy()` / `gate_copy()` / `shared_harness()` are the
    ONLY sanctioned way a split test file obtains a working copy or a
    `DeployedCheckHarness` — never call `DeployedCheckHarness.
    create_second_copy()` directly from a test file, or the sharing this
    module exists to provide is defeated.

    CONSOLIDATION RATIONALE (pr-reviewer's settled decision on this ticket,
    re-derived at 9 tests, not inherited from the original 7-test finding):
    the monolithic file's `copy_alter` + `copy_pairing` + `copy_clean`
    consolidate into ONE shared copy here (kept under the name `pairing`,
    matching pr-reviewer's own wording), because every test that used to run
    on those three copies calls only `upsert_hooks()` — additive,
    replace-by-id, never destructive — against disjoint hook ids and
    disjoint fixture script filenames. `copy_gate` stays exclusive: its one
    test calls `replace_hooks()` twice, WIPING `hooks_manifest.hooks` down
    to a single fixture entry, specifically to decouple its exit-code
    assertion from the ~72 real production hooks a shared copy also
    deploys. Sharing `copy_gate` would make that assertion depend on no
    real hook's own negative control currently reading `failing`, and the
    wipe would destroy any fixture hooks a differently-ordered sibling test
    had already written to the same copy.

AC: GE-120f-1 — see test_ge_120f_1_alter_and_pairing.py's module docstring
    for the full AC text / governing-ADR citation (not repeated in every
    split file that imports this module).
"""

from __future__ import annotations

import atexit
import json
import sys
import tempfile
import threading
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parent.parent  # unit_tests/portability/ -> worktree root

if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import _deployed_check_harness as dch  # type: ignore[import]  # noqa: E402

# ---------------------------------------------------------------------------
# Fixture vocabulary
# ---------------------------------------------------------------------------
NEGATIVE_CONTROL_INPUT = "GE120F1_BAD_INPUT"
REJECTED_MARKER = "GE120F1_REJECTED"
CLEAN_MARKER = "GE120F1_CHECK_RAN_CLEAN"
NEVER_REJECTS_MARKER = "GE120F1_CHECK_RAN_BUT_NEVER_REJECTS"

RUNNER_ENTRY = (
    "python {{config.output_root}}/scripts/commit_guardian/run_hook.py "
    "{{config.output_root}}/scripts/commit_guardian/check_negative_controls.py"
)

_ENTRY_TEMPLATE = (
    "python {{config.output_root}}/scripts/commit_guardian/run_hook.py "
    "{{config.output_root}}/scripts/commit_guardian/%s"
)


def wrapped_entry(script_name: str, extra_arg: str = "") -> str:
    """Build a run_hook.py-wrapped entry string for `script_name`, mirroring
    the exact shape every real `hooks_manifest` entry in this repo uses."""
    base = _ENTRY_TEMPLATE % script_name
    return f"{base} {extra_arg}" if extra_arg else base


def make_argv_check_script(rejects: bool) -> str:
    """A real fixture negative-control check script. When `rejects` is True
    it rejects (non-zero exit + the rejected marker) exactly when invoked
    with `NEGATIVE_CONTROL_INPUT` as its first argv token — the SAME entry
    point, fed the declared bad input, per ADR-045 §1. When False, it is the
    ALTERED version: it never rejects anything, simulating a protection
    that has silently broken while its declaration is untouched."""
    if rejects:
        return (
            '"""GE-120f-1 fixture negative-control check: rejects its '
            'declared known-bad input, fed via argv (the entry point this '
            'fixture uses)."""\n'
            "import sys\n"
            f"if len(sys.argv) > 1 and sys.argv[1] == {NEGATIVE_CONTROL_INPUT!r}:\n"
            f"    print({REJECTED_MARKER!r})\n"
            "    sys.exit(1)\n"
            f"print({CLEAN_MARKER!r})\n"
            "sys.exit(0)\n"
        )
    return (
        '"""GE-120f-1 fixture negative-control check, ALTERED: never '
        "rejects anything regardless of input -- simulates a protection "
        'breaking while its DECLARATION stays byte-identical."""\n'
        "import sys\n"
        f"print({NEVER_REJECTS_MARKER!r})\n"
        "sys.exit(0)\n"
    )


def make_argparse_check_script() -> str:
    """A real fixture negative-control check using Python's own ``argparse``,
    with no positional argument declared. Fed the declared bad input as an
    unrecognised positional token, argparse's OWN ``ArgumentParser.error()``
    rejects it with a ``usage: ...`` line and Python's hard-coded
    parser-error exit code (2) -- BEFORE this script's own examination
    logic (the print below) ever runs. Used to prove the runner does not
    misread argparse's own structural rejection as a genuine 'passing'
    observation of the check's declared rejection (pr-reviewer H-1b)."""
    return (
        '"""GE-120f-1 fixture negative-control check: a real argparse-based '
        "script with no positional argument declared, so an appended "
        "known-bad input is rejected by argparse ITSELF as an unrecognised "
        'argument, never reaching this script\'s own logic."""\n'
        "import argparse\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--flag', default=None)\n"
        "parser.parse_args()\n"
        f"print({CLEAN_MARKER!r})\n"
    )


def hook_entry(hook_id: str, script_name: str, enabled: bool = True) -> dict:
    """Build a real hooks_manifest.hooks[] entry for a fixture check, with a
    `negative_control` shaped exactly per
    config/verification_flow.schema.json $defs/negative_control (reused
    verbatim, per ADR-045 §3) and a sibling `entry_point` field (ADR-045
    §3's "entry_point ... NOT an internal helper import")."""
    return {
        "id": hook_id,
        "tier": "judging",
        "entry": wrapped_entry(script_name),
        "language": "system",
        "stages": ["pre-commit"],
        "pass_filenames": False,
        "enabled": enabled,
        "entry_point": wrapped_entry(script_name).replace(
            "{{config.output_root}}", ".leafcutter",
        ),
        "negative_control": {
            "input": NEGATIVE_CONTROL_INPUT,
            "command": wrapped_entry(script_name, NEGATIVE_CONTROL_INPUT),
            "expected_result": f"non-zero exit; output contains {REJECTED_MARKER}",
            "currently": {
                "state": "unverified",
                "observed": "2020-01-01",
                "evidence": [{"command": "n/a - not yet run", "output": ""}],
            },
        },
    }


def declaration_only_state(hook: dict) -> str:
    """NAMED MUTATION reference implementation (ticket test descriptor 2):
    the exact anti-pattern ADR-045 §1 and its Alternatives section forbid --
    "Deriving the record from the declaration when the declaration is
    well-formed." Treats a complete `negative_control` (non-empty `input`
    and `expected_result`) as sufficient evidence the rejection was
    observed, WITHOUT regard to whether the check was ever actually
    invoked. Used only to demonstrate mechanically that this suite's
    assertions are sharp enough to catch a runner shaped this way -- never
    called by, or a stand-in for, the real runner."""
    nc = hook.get("negative_control", {})
    if nc.get("input") and nc.get("expected_result"):
        return "passing"
    return "unverified"


# ---------------------------------------------------------------------------
# Deployed-manifest helpers (read/write the REAL on-disk commit_guardian.json
# in a REAL deployed copy -- never a simulated in-memory stand-in).
# ---------------------------------------------------------------------------
def read_manifest(copy_dir: Path) -> dict:
    manifest_path = copy_dir / dch._DEPLOYED_MANIFEST_REL  # noqa: SLF001
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def write_manifest(copy_dir: Path, data: dict) -> None:
    manifest_path = copy_dir / dch._DEPLOYED_MANIFEST_REL  # noqa: SLF001
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def upsert_hooks(copy_dir: Path, hooks_to_add: list[dict]) -> None:
    """Add or replace-by-id the given hook entries in the REAL deployed
    manifest, leaving every other entry untouched."""
    data = read_manifest(copy_dir)
    hooks = data.setdefault("hooks_manifest", {}).setdefault("hooks", [])
    by_id = {h.get("id"): i for i, h in enumerate(hooks)}
    for hook in hooks_to_add:
        if hook["id"] in by_id:
            hooks[by_id[hook["id"]]] = hook
        else:
            hooks.append(hook)
    write_manifest(copy_dir, data)


def replace_hooks(copy_dir: Path, hooks: list[dict]) -> None:
    """Overwrite hooks_manifest.hooks ENTIRELY with `hooks` -- used only when
    a test needs exclusive control over the whole examined population
    (ticket test descriptor 5's fixture-population wording). Only ever
    called against `gate_copy()`, which no other test shares."""
    data = read_manifest(copy_dir)
    data.setdefault("hooks_manifest", {})["hooks"] = list(hooks)
    write_manifest(copy_dir, data)


def hook_from_manifest(copy_dir: Path, hook_id: str) -> dict | None:
    data = read_manifest(copy_dir)
    for hook in data.get("hooks_manifest", {}).get("hooks", []):
        if hook.get("id") == hook_id:
            return hook
    return None


def write_check_script(copy_dir: Path, filename: str, content: str) -> Path:
    dest = copy_dir / dch._DEPLOYED_CG_REL / filename  # noqa: SLF001
    dest.write_text(content, encoding="utf-8")
    return dest


def declaration_fingerprint(hook: dict) -> str:
    """The DECLARATION (never the observed record): input/command/
    expected_result only. This is what ADR-045 §1's alter-and-revert
    discriminator requires to stay byte-identical while behaviour moves."""
    nc = hook.get("negative_control", {})
    declared = {k: nc.get(k) for k in ("input", "command", "expected_result")}
    return json.dumps(declared, sort_keys=True)


def run_negative_control_runner(
    harness: dch.DeployedCheckHarness, copy_dir: Path,
) -> dch.CopyCheckOutcome:
    """Invoke the runner EXACTLY the way its own hooks_manifest entry line
    would -- the real run_hook.py-wrapped subprocess shape, via the real
    harness, against the real deployed copy. This is the production entry
    point (ticket test descriptor 5)."""
    return harness.invoke_check(copy_dir, RUNNER_ENTRY, [])


# ---------------------------------------------------------------------------
# Shared deployed-copy provisioning -- built at most ONCE per process.
# ---------------------------------------------------------------------------
class _SharedState:
    """Plain namespace holding the process-wide cache; see module ARCHITECTURE."""

    tmp: tempfile.TemporaryDirectory | None = None
    harness: dch.DeployedCheckHarness | None = None
    pairing_dir: Path | None = None
    gate_dir: Path | None = None


_state = _SharedState()
_state_lock = threading.Lock()


def _ensure_shared_copies_built() -> None:
    """Build the two shared deployed copies exactly once per process.

    Guarded by a lock so concurrent `setUpClass` calls from different
    TestCase classes (should a future test runner ever parallelize within
    one process) cannot race into building twice. Registers the temporary
    directory's cleanup with `atexit` rather than relying solely on
    `TemporaryDirectory`'s own garbage-collection finalizer, since this
    cache is intentionally never torn down mid-run.
    """
    with _state_lock:
        if _state.tmp is not None:
            return
        tmp = tempfile.TemporaryDirectory()
        tmp_root = Path(tmp.name)
        harness = dch.DeployedCheckHarness(repo_root=_REPO_ROOT)
        pairing_dir = tmp_root / "copy_pairing"
        gate_dir = tmp_root / "copy_gate"
        harness.create_second_copy(pairing_dir)
        harness.create_second_copy(gate_dir)
        atexit.register(tmp.cleanup)
        _state.tmp = tmp
        _state.harness = harness
        _state.pairing_dir = pairing_dir
        _state.gate_dir = gate_dir


def shared_harness() -> dch.DeployedCheckHarness:
    """The single `DeployedCheckHarness` shared by every split test file."""
    _ensure_shared_copies_built()
    return _state.harness  # type: ignore[return-value]


def pairing_copy() -> Path:
    """The ONE shared deployed copy for every non-destructive test (the
    former copy_alter / copy_pairing / copy_clean) -- additive, id-scoped
    mutation only. Built once per process; every caller after the first
    reuses the same on-disk directory."""
    _ensure_shared_copies_built()
    return _state.pairing_dir  # type: ignore[return-value]


def gate_copy() -> Path:
    """The exclusive deployed copy for the one test that calls
    `replace_hooks()` (destructive: wipes the whole hooks list). Still
    built only once per process -- exclusivity is about which TEST touches
    it, never about how many times it is built."""
    _ensure_shared_copies_built()
    return _state.gate_dir  # type: ignore[return-value]
