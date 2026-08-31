"""
MODULE: _deployed_check_harness
AC: GE-120c-1 — "A harness executes the deployed checks out of process from a
    real separate working copy"
GOAL: Test-only verification apparatus. Stands up a REAL second working copy
    of this repository (an independent, freshly `git init`-ed directory that
    is then built via the real `scripts/build.py`, so it ends up with ONLY
    the deployed `.leafcutter/scripts/commit_guardian/` layout — never a
    copy of the source `scripts/`/`templates/` tree), invokes deployed
    commit_guardian checks against it as REAL SEPARATE PROCESSES in the two
    shapes the real commit path uses (the `run_hook.py`-wrapped form
    `.pre-commit-config.yaml` declares, and the direct-script form
    `precommit-canary` uses), and reports each check's observable result
    (exit status + the text it wrote) from each of the two working copies
    side by side.

BUSINESS CONTEXT: Every existing unit test for these checks imports the check
    module from the source tree, which is precisely the layout in which the
    "resolves prerequisites only via the source tree" defect class does not
    reproduce. This module exists to give the defect class somewhere to be
    caught: it deliberately keeps the source tree off the import path of the
    subprocess under test (PYTHONPATH scrubbed, `-I` isolated interpreter,
    cwd never the source tree) so a check that can only find its
    prerequisites via the source tree fails here rather than passing.

ARCHITECTURE — mechanism chosen and why (per this AC's own it_requirements,
    "OPEN QUESTION ANSWERED"): a `git worktree add` was considered (it
    matches how people actually work) but was NOT used, because a worktree
    checks out the WHOLE repository at the same commit — the second copy
    would then contain its own on-disk `scripts/`, `templates/`, etc., so a
    check resolving its repo root via `.git` discovery would find a REAL
    (if differently-located) source tree inside the "isolated" copy too,
    defeating the property this harness exists to test. Per the AC's own
    it_requirements ("A copied tree is acceptable if staging can still be
    exercised"), this module instead creates a genuinely fresh, independent
    directory: `git init` (for a real index staged files can be added to)
    plus a real `scripts/build.py --target-dir` run (for the real deployed
    layout) — nothing else. That directory never receives a copy of the
    source `scripts/`/`templates/` package, so a check that can only resolve
    its prerequisites via the source tree genuinely cannot find them there.
    This also sidesteps the worktree's shared-object-store hazard entirely
    (no concurrency caveat to manage).

    THE HARNESS ASSERTS ONLY ON THE SUBPROCESS'S OBSERVABLE OUTPUT (exit
    code, stdout, stderr) for every check invocation. It never imports a
    check module, a commit_guardian helper, or `_resolve_root.py`.

DECISION HISTORY
====================================================================
- 2026-08-31 [EPIC-TrustThatAGreenCheckActuallyChecked/12, GE-120c-1]:
  Initial implementation. assigned_agent for this AC is test-writer (not
  python-coder) per the AC's own notes — this ticket carries no coder agent
  in its dispatch chain, so test-writer both authors this module and its
  test file, per the AC author's explicit reasoning: "the deliverable is
  verification apparatus, and the failure mode being guarded against is an
  implementer building a harness shaped to pass against their own fix."
====================================================================
"""

from __future__ import annotations

import ast
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_DEPLOYED_CG_REL = Path(".leafcutter") / "scripts" / "commit_guardian"
_DEPLOYED_MANIFEST_REL = _DEPLOYED_CG_REL / "commit_guardian.json"
_TEMPLATE_MANIFEST_REL = Path("templates") / "scripts" / "commit_guardian" / "commit_guardian.json"
_OUTPUT_ROOT_TOKEN = "{{config.output_root}}"
_DEFAULT_OUTPUT_ROOT = ".leafcutter"
_COULD_NOT_CHECK_MARKERS = (
    "modulenotfounderror",
    "importerror",
    "traceback (most recent call last)",
)


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------
@dataclass
class CopyCheckOutcome:
    """Observable result of invoking ONE check against ONE working copy."""

    status: str  # "clean" | "violation" | "could_not_check"
    exit_code: int
    output: str  # combined stdout + stderr, the text the check wrote


@dataclass
class CheckSweepEntry:
    """Per-check report pairing both copies' outcomes side by side, so a
    disagreement can be read directly rather than inferred from a failed
    assertion."""

    check_id: str
    first: CopyCheckOutcome | None = None
    second: CopyCheckOutcome | None = None

    @property
    def agrees(self) -> bool:
        if self.first is None or self.second is None:
            return False
        return self.first.status == self.second.status


@dataclass
class HarnessResult:
    """Overall result of one DeployedCheckHarness.run_sweep() call."""

    success: bool
    checks_exercised: int
    manifest_check_count: int
    message: str
    failed_setup_step: str | None = None
    checks: dict[str, CheckSweepEntry] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# The harness
# ---------------------------------------------------------------------------
class DeployedCheckHarness:
    """Stands up real deployed-only working copies and runs commit_guardian
    checks against them out of process."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)

    # ---- setup ----------------------------------------------------------
    def create_second_copy(self, target_dir: Path) -> None:
        """Stand up a real second working copy: `git init` (real index) plus
        a real `scripts/build.py --target-dir` run (real deployed layout).
        Deliberately never copies the source `scripts/`/`templates/` tree —
        see module docstring "ARCHITECTURE" for why."""
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            subprocess.run(
                ["git", "init", "-q"],
                cwd=str(target_dir),
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.CalledProcessError, OSError) as exc:
            logger.warning("git init failed for second copy at %s: %s", target_dir, exc)
            raise

        build_script = self.repo_root / "scripts" / "build.py"
        try:
            subprocess.run(
                [sys.executable, str(build_script), "--target-dir", str(target_dir)],
                check=True,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except (subprocess.CalledProcessError, OSError) as exc:
            logger.warning("build.py failed to deploy into second copy %s: %s", target_dir, exc)
            raise

    def stage_files(self, working_copy_dir: Path, files: dict[str, str]) -> list[str]:
        """Write `files` (relpath -> content) into working_copy_dir and
        `git add` them, giving REAL staged files via a REAL git index rather
        than a simulated one. Returns the list of relative paths staged."""
        working_copy_dir = Path(working_copy_dir)
        staged: list[str] = []
        for rel_path, content in files.items():
            dest = working_copy_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
            staged.append(rel_path)

        try:
            subprocess.run(
                ["git", "-C", str(working_copy_dir), "add", *staged],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.CalledProcessError, OSError) as exc:
            logger.warning("git add failed while staging files in %s: %s", working_copy_dir, exc)
            raise
        return staged

    # ---- introspection ----------------------------------------------------
    def deployed_layout_present(self, working_copy_dir: Path) -> bool:
        """True when `<working_copy_dir>/.leafcutter/scripts/commit_guardian/`
        exists — the deployed layout the real commit path's checks see."""
        return (Path(working_copy_dir) / _DEPLOYED_CG_REL).is_dir()

    def _manifest_hooks(self, working_copy_dir: Path) -> list[dict]:
        """Read the REAL deployed manifest's hooks_manifest.hooks[] from
        `working_copy_dir` — never a hard-coded set."""
        manifest_path = Path(working_copy_dir) / _DEPLOYED_MANIFEST_REL
        raw = manifest_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data.get("hooks_manifest", {}).get("hooks", [])

    def _template_manifest_check_count(self) -> int:
        """Read the expected check count from the real TEMPLATE manifest
        (this repo's own source of truth, GE-120c-3), never a constant."""
        manifest_path = self.repo_root / _TEMPLATE_MANIFEST_REL
        try:
            raw = manifest_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not read template manifest at %s: %s", manifest_path, exc)
            raise
        data = json.loads(raw)
        return len(data.get("hooks_manifest", {}).get("hooks", []))

    # ---- invocation ----------------------------------------------------
    def build_argv(self, entry_template: str, args: list[str]) -> list[str]:
        """Turn a manifest `entry` string (e.g.
        "python {{config.output_root}}/scripts/commit_guardian/x.py") into a
        real argv, substituting the real deployed output root and forcing
        the interpreter to run in isolated mode (`-I`) regardless of which
        shape (run_hook.py-wrapped or direct-script) the entry uses."""
        substituted = entry_template.replace(_OUTPUT_ROOT_TOKEN, _DEFAULT_OUTPUT_ROOT)
        parts = substituted.split()
        if parts and parts[0] == "python":
            parts = [sys.executable, "-I", *parts[1:]]
        return [*parts, *args]

    def invoke_check(
        self, working_copy_dir: Path, entry_template: str, args: list[str] | None = None,
    ) -> CopyCheckOutcome:
        """Invoke one check as a SEPARATE PROCESS in the way the commit path
        invokes it (per `entry_template`, taken verbatim from a real
        manifest). BINDING CONSTRAINTS enforced here: PYTHONPATH is scrubbed
        from the child's environment, the interpreter runs isolated (`-I`,
        via build_argv), and cwd is `working_copy_dir` — never this
        harness's own source tree."""
        working_copy_dir = Path(working_copy_dir)
        args = list(args) if args else []
        argv = self.build_argv(entry_template, args)

        env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}

        try:
            proc = subprocess.run(
                argv,
                cwd=str(working_copy_dir),
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            logger.warning(
                "Check invocation failed for entry %r in %s: %s",
                entry_template, working_copy_dir, exc,
            )
            return CopyCheckOutcome(status="could_not_check", exit_code=-1, output=str(exc))

        output = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode == 0:
            status = "clean"
        elif _looks_like_could_not_check(output):
            status = "could_not_check"
        else:
            status = "violation"
        return CopyCheckOutcome(status=status, exit_code=proc.returncode, output=output)

    # ---- the sweep ----------------------------------------------------
    def run_sweep(
        self,
        second_copy_dir: Path,
        first_copy_dir: Path | None = None,
        check_ids: list[str] | None = None,
        staged_files: list[str] | None = None,
        extra_hooks: list[dict] | None = None,
    ) -> HarnessResult:
        """Exercise checks against `second_copy_dir`, comparing each against
        `first_copy_dir` (defaults to `self.repo_root`). Per
        GE-120c-1-i: if EITHER copy's deployed layout is missing, this
        returns immediately with success=False, checks_exercised=0, and a
        failed_setup_step naming the specific missing artifact — it never
        proceeds to the per-check execution loop on incomplete setup."""
        second_copy_dir = Path(second_copy_dir)
        first_copy_dir = Path(first_copy_dir) if first_copy_dir is not None else self.repo_root
        manifest_count = self._template_manifest_check_count()

        if not self.deployed_layout_present(second_copy_dir):
            missing = second_copy_dir / _DEPLOYED_CG_REL
            failed_step = f"build.py did not produce {missing} in {second_copy_dir}"
            return HarnessResult(
                success=False,
                checks_exercised=0,
                manifest_check_count=manifest_count,
                message=(
                    f"Setup incomplete: {failed_step} — "
                    f"0 of {manifest_count} checks exercised."
                ),
                failed_setup_step=failed_step,
            )

        if not self.deployed_layout_present(first_copy_dir):
            missing = first_copy_dir / _DEPLOYED_CG_REL
            failed_step = f"reference copy {first_copy_dir} has no deployed layout at {missing}"
            return HarnessResult(
                success=False,
                checks_exercised=0,
                manifest_check_count=manifest_count,
                message=(
                    f"Setup incomplete: {failed_step} — 0 of {manifest_count} checks exercised."
                ),
                failed_setup_step=failed_step,
            )

        hooks = list(self._manifest_hooks(second_copy_dir))
        if extra_hooks:
            hooks = hooks + list(extra_hooks)
        if check_ids is not None:
            hooks = [h for h in hooks if h.get("id") in check_ids]

        args = list(staged_files) if staged_files else []
        entries: dict[str, CheckSweepEntry] = {}
        lines: list[str] = []
        any_disagreement = False

        for hook in hooks:
            check_id = hook.get("id")
            entry_template = hook.get("entry", "")
            hook_args = args if hook.get("pass_filenames", False) else []

            first_outcome = self.invoke_check(first_copy_dir, entry_template, hook_args)
            second_outcome = self.invoke_check(second_copy_dir, entry_template, hook_args)

            entry = CheckSweepEntry(check_id=check_id, first=first_outcome, second=second_outcome)
            entries[check_id] = entry
            if not entry.agrees:
                any_disagreement = True
            lines.append(
                f"{check_id}: first_copy={first_outcome.status} "
                f"({first_outcome.output.strip()[:160]!r}) "
                f"second_copy={second_outcome.status} "
                f"({second_outcome.output.strip()[:160]!r})"
            )

        message = f"{len(entries)} of {manifest_count} checks exercised.\n" + "\n".join(lines)
        return HarnessResult(
            success=not any_disagreement,
            checks_exercised=len(entries),
            manifest_check_count=manifest_count,
            message=message,
            failed_setup_step=None,
            checks=entries,
        )


def _looks_like_could_not_check(output: str) -> bool:
    lowered = output.lower()
    return any(marker in lowered for marker in _COULD_NOT_CHECK_MARKERS)


# ---------------------------------------------------------------------------
# Self-enforced coverage rule (AC-5 / coverage note): "a harness case that
# only searches a check's source text for a string is not accepted as
# coverage for any criterion in this tree." Encoded here as a rule the
# harness enforces on its OWN case definitions, per this AC's own
# it_requirements — a review convention will not survive the fourth author.
# ---------------------------------------------------------------------------
def enforce_no_grep_only_test_cases(test_file_path: Path) -> list[str]:
    """AST-scan `test_file_path` for grep-only coverage: a `test_*` function
    that reads a file's source text (`.read_text(`) and performs a
    containment check on it (an ` in ` expression), WITHOUT ever invoking a
    subprocess or this harness's own invocation surface
    (`invoke_check`/`run_sweep`) anywhere in the same function body, is not
    acceptable coverage for any criterion in the GE-120 tree. Returns the
    list of offending test function names — an empty list means none were
    found."""
    source = Path(test_file_path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    offenders: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        body_src = ast.get_source_segment(source, node) or ""
        reads_source_text = ".read_text(" in body_src
        has_containment_check = " in " in body_src
        invokes_process = (
            "subprocess" in body_src
            or "invoke_check" in body_src
            or "run_sweep" in body_src
        )
        if reads_source_text and has_containment_check and not invokes_process:
            offenders.append(node.name)

    return offenders
