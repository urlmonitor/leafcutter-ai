"""
MODULE: check_lint_gate
GOAL: Refuse, at commit time, any change CI's required "Lint (ruff)" check
    would reject -- judged by the same rules over the same files -- and be the
    ONE runner every local mirror of that check goes through: `--mode staged`
    (the pre-commit hook), `--mode full` (CI and scripts/run_ci_local.py) and
    `--mode files --files <paths>` (BO-570-3's sign-off adapter), each with an
    optional `--json` payload.
BUSINESS CONTEXT: BP-1300e. CI's blocking lint check had no commit-time
    counterpart (PR #1058: two E741 sites reached CI). Parity needs three
    things at once: one declaration of scope and rule sets that CI and every
    local runner read (leafcutter-lint.json, via _lint_scope), a verdict
    judged on the bytes being committed (the INDEX blob, via _lint_ruff), and
    a refusal that is never reported as a pass when the check could not run
    (_ruff_locator, _lint_requirements, _lint_config). A linter version that
    differs from CI's is such a case: findings under a different linter are
    never presented as CI's verdict.
ARCHITECTURE: Pipeline, each stage able to stop the run with a could_not_check
    reason: (1) subject root from git in the hook's cwd, never from __file__;
    (2) declaration (index in staged mode, work tree otherwise); (3) the
    in-scope set from the declaration and git ALONE -- empty means
    nothing_to_inspect and ruff is never probed; (4) locate ruff; (5) compare
    its version with the project's declared pin; (6) verify the governing ruff
    configuration belongs to the project and is staged as on disk; (7) run
    every declared step -- ALL steps, ALL findings, then one verdict, with the
    same (path, line, code) reported by two steps counted once. Helpers:
    _lint_git, _lint_scope, _lint_requirements, _lint_config, _lint_ruff,
    _lint_report, _lint_probe (the `--probe known-bad|known-clean` negative
    control), _ruff_locator (all underscore-prefixed siblings, deployed by
    build_commit_guardian()'s directory copy with no deploy_map entry).

DECISION HISTORY
- 2026-10-12 [python-coder/BP-1300e-1]: Created. EVERY could_not_check cause
    BLOCKS (exit 1), including this check's own internal defects, CONTRARY to
    the component's usual fail-open convention: pre-commit prints "Passed"
    beside any hook that exits 0 whatever it writes, so an exit-0 fail-open on
    an internal defect is a printed false green (BP-1300e-1-iii, scenario 5).
    Do not "restore consistency" by returning 0 from the guards below. The
    outermost last-resort guard therefore also exits non-zero.
- 2026-10-12 [python-coder/BP-1300e-1-ii]: In staged mode a path is linted
    only if its suffix is one ruff includes by default (.py, .pyi, .ipynb):
    ruff applies `include` to discovered files only and lints any explicit
    path (and any stdin blob) as Python, so a staged scripts/README.md would
    otherwise be parsed as code. A project's `extend-include` is not consulted
    there. Files mode hands explicit paths to ruff as `ruff check <file>` does,
    and full mode lets ruff's own discovery apply `include`.
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True  # a hook must not leave __pycache__ in the tree it reads

import argparse
import json
import logging
import os
import shlex
import subprocess
from pathlib import Path
from typing import NoReturn

import _lint_config as lcfg
import _lint_git as lg
import _lint_probe as probe
import _lint_requirements as lreq
import _lint_ruff as lr
import _lint_scope as ls
import _resolve_root as rr
import _ruff_locator as loc
import check_outcome as co
from _lint_report import Finding, Report, exit_code, render_human, to_payload

logger = logging.getLogger(__name__)

PY_SUFFIXES = (".py", ".pyi", ".ipynb")


class CouldNotCheck(Exception):
    """A stage cannot give CI's verdict; ends the run as could_not_check."""

    def __init__(self, reason: str, detail: str, fix: str = "") -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail
        self.fix = fix


def _stop(reason: str, detail: str, fix: str = "") -> NoReturn:
    """Raise CouldNotCheck (the single raise site for stage failures)."""
    raise CouldNotCheck(reason, detail, fix)


# ── stage 1-2: root and declaration ──────────────────────────────────────────
def resolve_root() -> Path:
    """The git toplevel of the hook's cwd; nothing else may supply the project."""
    try:
        top = rr.find_git_toplevel_strict()
    except OSError as exc:
        _stop("internal_error", f"git could not be launched: {exc}")
    if top is rr.NO_REPO:
        _stop("no_repository", "the working directory is not inside a git repository "
              "(`git rev-parse --show-toplevel` failed); the gate never guesses a project root")
    return top


def load_declaration(root: Path, mode: str) -> ls.Declaration:
    """Read leafcutter-lint.json from the index (staged) or the work tree; never default a bad one."""
    try:
        return ls.load(root, "index" if mode == "staged" else "worktree")
    except ls.DeclarationError as exc:
        _stop("declaration_unreadable", str(exc), "Fix leafcutter-lint.json: an unreadable declaration is "
              "never replaced by the default scope, because that would be a different verdict presented as CI's.")


# ── stage 3: the in-scope set, from the declaration and git alone ────────────
def named_files(root: Path, raw: list[str]) -> list[str]:
    """Repo-relative POSIX paths for the --files arguments that exist inside the project."""
    rels = []
    for item in raw:
        absolute = Path(item) if os.path.isabs(item) else Path.cwd() / item
        rel = Path(os.path.relpath(absolute, root)).as_posix()
        if not rel.startswith("..") and absolute.is_file():
            rels.append(rel)
    return rels


def in_scope(decl: ls.Declaration, rels: list[str], *, python_only: bool) -> list[str]:
    """Paths a declared step covers; staged paths must also carry a suffix ruff includes."""
    return [
        r for r in rels
        if (not python_only or r.lower().endswith(PY_SUFFIXES)) and any(s.covers(r) for s in decl.steps)
    ]


def full_targets(root: Path, step: ls.Step) -> list[str]:
    """A step's declared paths that exist (an absent tree contributes nothing)."""
    return [p for p in step.paths if (root / p).exists()]


def step_targets(root: Path, step: ls.Step, mode: str, candidates: list[str]) -> list[str]:
    """What ruff is handed for one step in files or full mode."""
    if mode == "full":
        return full_targets(root, step)
    return [c for c in candidates if step.covers(c)]


def candidates_for(args, root: Path, decl: ls.Declaration) -> tuple[list[str], int]:
    """(in-scope candidate files, number of files considered) for this mode."""
    if args.mode == "full":
        found = [p for step in decl.steps for p in full_targets(root, step)]
        return found, len(found)
    staged = args.mode == "staged"
    allfiles = lg.staged_paths(root) if staged else named_files(root, args.files or [])
    return in_scope(decl, allfiles, python_only=staged), len(allfiles)


# ── stage 4-6: linter, version, configuration ────────────────────────────────
def locate_ruff(report: Report, root: Path, decl: ls.Declaration) -> loc.Located:
    """Find ruff or stop with the reason and the fix."""
    found = loc.locate()
    if isinstance(found, loc.Located):
        report.ruff_version = found.version
        return found
    if isinstance(found, loc.NotInstalled):
        install = f"pip install -r {decl.linter_version_source}" if (root / decl.linter_version_source).is_file() else "pip install ruff"
        _stop("ruff_not_installed", f"ruff is not installed (tried {' and '.join(found.tried)})",
              f"Install it with: {install}")
    _stop("ruff_failed_to_start", f"ruff is installed but cannot start: {found.stderr}",
          f"Run `{' '.join(found.prefix)} --version` to reproduce, then repair the ruff installation.")


def check_version(report: Report, root: Path, decl: ls.Declaration, ruff: loc.Located, mode: str) -> None:
    """Compare ruff's version with the project's declared pin (exact string equality)."""
    reader = lreq.index_reader(root) if mode == "staged" else lreq.worktree_reader(root)
    need = lreq.resolve(reader, decl.linter_version_source, declared=decl.version_source_declared)
    report.version_source = need.source
    if need.kind == lreq.UNREADABLE:
        _stop("linter_version_source_unreadable", f"the linter version source {need.source} cannot be read: {need.detail}")
    if need.kind == lreq.NOT_DECLARED:
        where = f"{need.source} declares no exact ruff version" if need.source else f"{decl.linter_version_source} does not exist"
        report.version_check = "not_declared"
        report.version_note = f"no exact linter version is declared for the project ({where}), so no version check was applied"
        return
    report.required_ruff_version = need.version
    if need.version == ruff.version:
        report.version_check = "matched"
        return
    report.version_check = "mismatched"
    _stop("linter_version_mismatch",
          f"the local ruff version {ruff.version} differs from the version {need.version} the project declares "
          f"(CI installs it from {need.source}); a verdict from a different linter is not CI's verdict",
          f"Install exactly that version: {shlex.quote(sys.executable)} -m pip install ruff=={need.version}")


def check_configuration(root: Path, mode: str, directories: list[Path]) -> None:
    """Stop unless every governing ruff configuration is the project's own (and staged as on disk)."""
    try:
        lcfg.check_governing(root, directories, staged=mode == "staged")
    except lcfg.ConfigProblem as exc:
        fix = "Stage or stash its unstaged edits, then commit again." if exc.reason.endswith("staged") else (
            "Give the project its own ruff configuration (CI cannot see a file outside the checkout)."
            if exc.reason.endswith("project") else "Fix the file; the gate never falls back to ruff's default rules.")
        _stop(exc.reason, exc.detail, fix)


def directories_of(root: Path, mode: str, decl: ls.Declaration, candidates: list[str]) -> list[Path]:
    """Directories whose governing ruff configuration must be checked."""
    if mode != "full":
        return [root / Path(c).parent for c in candidates]
    paths = [root / p for step in decl.steps for p in full_targets(root, step)]
    return [p if p.is_dir() else p.parent for p in paths]


# ── stage 7: run every declared step ─────────────────────────────────────────
def judge_staged_file(prefix: tuple[str, ...], root: Path, rel: str, steps: list[ls.Step]) -> tuple[bool, list[Finding]]:
    """Judge one staged blob under each covering step; (admitted by ruff, findings)."""
    data = lg.index_blob(root, rel)
    if data is None:
        _stop("internal_error", f"{rel} is staged but has no index entry")
    head: bytes | None = None
    head_loaded, admitted, out = False, False, []
    for step in steps:
        found = lr.check_blob(prefix, root, rel, data, step)
        admitted = admitted or bool(found) or lr.is_admitted(prefix, root, rel, step)
        if found and not head_loaded:
            head, head_loaded = lg.head_blob(root, rel), True
        if found:
            old = lr.check_blob(prefix, root, rel, head, step) if head is not None else []
            lr.label_predates(found, data, head, old)
        out += found
    return admitted, out


def run_staged(prefix: tuple[str, ...], root: Path, decl: ls.Declaration, candidates: list[str]) -> tuple[set[str], list[Finding]]:
    """Judge every in-scope staged file as it will be committed."""
    inspected: set[str] = set()
    findings: list[Finding] = []
    for rel in candidates:
        admitted, found = judge_staged_file(prefix, root, rel, [s for s in decl.steps if s.covers(rel)])
        if admitted:
            inspected.add(rel)
        findings += found
    return inspected, findings


def run_paths(prefix: tuple[str, ...], root: Path, decl: ls.Declaration, mode: str, candidates: list[str]) -> tuple[set[str], list[Finding]]:
    """Judge work-tree paths (files and full modes) one declared step at a time."""
    inspected: set[str] = set()
    findings: list[Finding] = []
    for step in decl.steps:
        targets = step_targets(root, step, mode, candidates)
        if targets:
            inspected.update(lr.show_files(prefix, root, targets))
            findings += lr.check_paths(prefix, root, targets, step)
    return inspected, findings


def finalize(report: Report, inspected: set[str], findings: list[Finding]) -> None:
    """One verdict from all findings, the same (path, line, code) counted once."""
    unique: dict[tuple, Finding] = {}
    for finding in findings:
        unique.setdefault(finding.key(), finding)
    report.findings = sorted(unique.values(), key=lambda f: (f.path, f.line, f.col, f.code))
    report.files_inspected = sorted(inspected)
    if report.findings:
        report.outcome = co.OUTCOME_REFUSED
    elif not inspected:
        report.outcome = co.OUTCOME_NOTHING_TO_INSPECT
    else:
        report.outcome = co.OUTCOME_OK


# ── driver ───────────────────────────────────────────────────────────────────
def execute(args, report: Report) -> None:
    """Run the whole pipeline, filling *report*; raises CouldNotCheck to stop."""
    root = resolve_root()
    decl = load_declaration(root, args.mode)
    candidates, report.considered = candidates_for(args, root, decl)
    if not candidates:
        report.outcome = co.OUTCOME_NOTHING_TO_INSPECT
        return
    ruff = locate_ruff(report, root, decl)
    check_version(report, root, decl, ruff, args.mode)
    check_configuration(root, args.mode, directories_of(root, args.mode, decl, candidates))
    if args.mode == "staged":
        inspected, findings = run_staged(ruff.prefix, root, decl, candidates)
    else:
        inspected, findings = run_paths(ruff.prefix, root, decl, args.mode, candidates)
    finalize(report, inspected, findings)


def could_not_check(report: Report, reason: str, detail: str, fix: str = "") -> Report:
    """Turn *report* into a could_not_check verdict (no findings are ever carried)."""
    report.outcome, report.reason, report.detail, report.fix = co.OUTCOME_COULD_NOT_CHECK, reason, detail, fix
    report.findings, report.files_inspected = [], []
    return report


def run(args) -> Report:
    """Produce the verdict for *args*; every expected failure becomes could_not_check."""
    report = Report(mode=args.mode)
    try:
        execute(args, report)
    except CouldNotCheck as exc:
        return could_not_check(report, exc.reason, exc.detail, exc.fix)
    except lr.RuffFailure as exc:
        return could_not_check(report, exc.reason, exc.detail)
    except (lg.GitError, OSError, subprocess.SubprocessError, ValueError, UnicodeDecodeError) as exc:
        logger.warning("the lint gate could not complete: %s", exc)
        return could_not_check(report, "internal_error", f"{type(exc).__name__}: {exc}")
    return report


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse the CLI: --mode staged|full|files, --files, --json."""
    parser = argparse.ArgumentParser(description="Commit-time mirror of CI's required lint check.")
    parser.add_argument("--mode", choices=("staged", "full", "files"), default="staged")
    parser.add_argument("--files", nargs="+", help="paths to judge (--mode files)")
    parser.add_argument("--json", action="store_true", help="print the machine-readable payload")
    parser.add_argument("--probe", choices=("known-bad", "known-clean"),
                        help="run this gate on a throwaway one-file project (negative-control input)")
    args = parser.parse_args(argv)
    if args.mode == "files" and not args.files:
        parser.error("--mode files requires --files <paths...>")
    return args


def main(argv: list[str] | None = None) -> int:
    """CLI entry: print the verdict (human lines + RESULT, or --json); exit 0 only for a clean one."""
    args = parse_args(argv)
    if args.probe:
        return probe.run_probe(args.probe, Path(__file__).resolve())
    report = run(args)
    if args.json:
        print(json.dumps(to_payload(report)))
    else:
        for line in render_human(report):
            print(line)
        co.emit_result(report.outcome)
    return exit_code(report)


def guarded_main() -> int:
    """Outermost guard: anything unforeseen is still a visible, BLOCKING could_not_check."""
    try:
        return main()
    except Exception as exc:  # noqa: BLE001 -- outermost last-resort guard (BP-1300e-1-iii)
        print(f"WARNING: check_lint_gate failed unexpectedly: {type(exc).__name__}: {exc}", file=sys.stderr)
        print(f"lint gate: could not check this commit: {type(exc).__name__}: {exc} (reason: internal_error)")
        co.emit_result(co.OUTCOME_COULD_NOT_CHECK)
        return 1


if __name__ == "__main__":
    sys.exit(guarded_main())
