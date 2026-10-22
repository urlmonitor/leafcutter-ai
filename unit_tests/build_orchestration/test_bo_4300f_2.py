"""
MODULE: unit_tests/build_orchestration/test_bo_4300f_2.py
AC: BO-4300f-2 -- "The former ways of making a workspace are gone from what an install delivers" (L2).
TICKET: tickets/00_inbox/epics/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/
    14_TICKET-20260928-BO-4300-retire-former-ways.md

Two halves. (1) DEPLOYED proofs: in the shared deployed layout (the ONE build of
_workspace_maker_fixtures.ensure_deployed_layout) each former way is absent or relays the maker's
answer; a surviving shim creates exactly what the maker creates. (2) The REPO-WIDE CENSUS: no tracked
file spells the old way of adding/removing a git workspace outside the one declared exemption list
(``_bo_4300f_2_fixtures.EXEMPTIONS``: two sites with reasons + seven record folders); each hit is
reported ``file:line``. A second census covers the ``-C <path> commit`` spelling.

This module spells none of the censused commands as literal text -- the scanner patterns and every
fixture line are built from pieces -- so it never trips the census it implements. Fixture trees are
written with newline="\\n". Entry point: ``python -m unit_tests.build_orchestration.test_bo_4300f_2
--census`` prints the real tree's hits and exits non-zero when there are any.

SHIM CONTRACT ASSUMED (python-coder: delete the script, or satisfy this; raise a mismatch before
changing a test): a surviving setup_ticket_worktree.py maps ``<sub-command> <slug> --repo-root P``
to the maker's ``ensure --kind <kind> --slug <slug> --repo-root P`` and relays its one JSON answer
and exit code unchanged (setup-ticket->ticket, create-only->feature, create-ac-worktree->ac,
create-fastlane-worktree->fastlane). A surviving worktree_repo_facts.py names the maker and runs no
subprocess of its own. git_recovery.py spells no old-way add/remove.

DEPENDS ON (not yet built -- expected RED): the removal/shimming of the former scripts, the
rewritten instruction sites and fixture tests (census), and the scripts/build.py refusal (Q6).
Census-mechanics tests (fixture trees, exemption list) are self-contained and are green from the
start; they pin the census so the real-tree test cannot be satisfied by weakening it.

DECISION HISTORY
====================================================================
- 2026-10-13 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/14,
  BO-4300f-2]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/14)
====================================================================
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration import _bo_4300f_2_fixtures as fx
from unit_tests.build_orchestration._workspace_maker_fixtures import deployed_maker_path, make_project, run_maker

REPO_ROOT = fx.REPO_ROOT
_G = "g" + "it"
_WT = "work" + "tree"


def _old_way_line(verb: str, form: str = "shell") -> str:
    """One line spelling the old way in the requested *form* (assembled, never literal)."""
    if form == "shell":
        return f"    {_G} {_WT} {verb} ../w1 -b x"
    if form == "dash_c":
        return f"    {_G} -C /repo {_WT} {verb} ../w1"
    if form == "argv":
        return f'    subprocess.run(["{_G}", "{_WT}", "{verb}", path])'
    if form == "argv_dash_c":
        return f'    cmd = ["{_G}", "-C", repo, "{_WT}", "{verb}", path]'
    if form == "js":
        return f"    const cmd = `{_G} -C ${{root}} {_WT} {verb} ${{p}}`;"
    raise ValueError(form)


def _write(root: Path, rel: str, lines: list[str]) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


class _TmpCase(unittest.TestCase):
    def tmp(self) -> Path:
        holder = tempfile.TemporaryDirectory(prefix="bo4300f2-", ignore_cleanup_errors=True)
        self.addCleanup(holder.cleanup)
        return Path(holder.name)


class TestFormerWaysAreGone(_TmpCase):
    """Deployed-layout proofs."""

    def test_each_former_way_is_absent_or_relays_the_makers_answer_unchanged(self):
        # covers: BO-4300f-2
        # angle: deployed
        """Every former script/sub-command, the facts helper's base lookup and the recovery re-add is
        absent from the install, or answers exactly as the maker does (timestamps normalised)."""
        scripts = fx.deployed_scripts_dir()
        failures: list[str] = []

        former = scripts / fx.FORMER_SCRIPT
        if former.is_file():
            deployed_maker_path()
            for sub, kind in fx.SHIM_KIND_BY_SUBCOMMAND.items():
                ta, tb = self.tmp(), self.tmp()
                pa, pb = make_project(ta)["project"], make_project(tb)["project"]
                try:
                    shim = fx.run_script(former, [sub, "slug1", "--repo-root", str(pa)], pa)
                except subprocess.TimeoutExpired:
                    failures.append(f"{sub}: timed out")
                    continue
                ref = run_maker(["ensure", "--kind", kind, "--slug", "slug1", "--repo-root", str(pb)], pb)
                got = fx.one_json(shim.stdout)
                if got is None:
                    failures.append(f"{sub}: no single JSON answer (exit {shim.returncode}): {shim.stdout[:120]!r}")
                elif fx.normalise(got, ta) != fx.normalise(ref["answer"], tb) or shim.returncode != ref["exit_code"]:
                    failures.append(f"{sub}: answer differs from the maker's for the equivalent request")

        facts = scripts / fx.FORMER_FACTS
        if facts.is_file():
            src = facts.read_text(encoding="utf-8")
            if "subprocess" in src or "worktree.py" not in src:
                failures.append(f"{fx.FORMER_FACTS}: survives with its own git lookups instead of the maker")

        recovery = scripts / fx.FORMER_RECOVERY
        if recovery.is_file():
            hits = fx.scan_text(recovery.read_text(encoding="utf-8"))
            if hits:
                failures.append(f"{fx.FORMER_RECOVERY}: re-adds a workspace the old way (lines {hits})")

        self.assertEqual([], failures, "former ways survive in the deployed install: " + "; ".join(failures))

    def test_no_former_way_makes_finds_or_clears_by_its_own_means(self):
        # covers: BO-4300f-2
        # angle: failure
        """A surviving shim creates exactly what the maker creates (one marker-bearing clone) and no
        linked-workspace registration in the main project. Control row: the maker itself passes the
        same checks, so the test cannot pass by checking nothing."""
        scripts = fx.deployed_scripts_dir()

        def check(project: Path, landing: Path, kind: str, slug: str) -> list[str]:
            problems = []
            marker = landing / kind / slug / ".leafcutter" / "workspace.json"
            if not marker.is_file():
                problems.append("no marker-bearing clone at <landing>/<kind>/<slug>")
            made = sorted(p.relative_to(landing).as_posix() for p in landing.glob("*/*")) if landing.is_dir() else []
            if made != [f"{kind}/{slug}"]:
                problems.append(f"workspaces made: {made}, expected only {kind}/{slug}")
            if fx.has_registration(project):
                problems.append("a linked-workspace registration was made in the main project")
            if (project.parent / "worktrees").exists():
                problems.append("a sibling old-style landing folder was created")
            return problems

        # control row: the maker's own request
        t0 = self.tmp()
        made0 = make_project(t0)
        ref = run_maker(["ensure", "--kind", "feature", "--slug", "ctl", "--repo-root", str(made0["project"])], made0["project"])
        self.assertEqual(0, ref["exit_code"], ref["stderr"])
        self.assertEqual([], check(made0["project"], made0["landing_place"], "feature", "ctl"))

        former = scripts / fx.FORMER_SCRIPT
        if not former.is_file():
            return
        failures = []
        for sub, kind in fx.SHIM_KIND_BY_SUBCOMMAND.items():
            t = self.tmp()
            made = make_project(t)
            try:
                fx.run_script(former, [sub, "slug1", "--repo-root", str(made["project"])], made["project"])
            except subprocess.TimeoutExpired:
                failures.append(f"{sub}: timed out")
                continue
            failures.extend(f"{sub}: {p}" for p in check(made["project"], made["landing_place"], kind, "slug1"))
        self.assertEqual([], failures)


class TestCensusOfTheRealTree(unittest.TestCase):
    def test_no_git_worktree_add_or_remove_outside_the_declared_exemptions(self):
        # covers: BO-4300f-2
        # angle: seam
        """Seam: the real tracked tree (producer: every file's text) through the census scanner
        (consumer) against the one declared exemption list; each hit is reported file:line."""
        files = fx.tracked_files()
        hits = fx.census(REPO_ROOT, files)
        self.assertEqual([], hits, f"{len(hits)} old-way spelling(s) outside the exemptions:\n" + "\n".join(hits))

    def test_no_git_dash_c_commit_in_component_files_or_instruction_surfaces(self):
        # covers: BO-4300f-2
        # angle: criterion
        """No ``-C <path> commit`` (shell or argv) in the component's files or any instruction surface;
        a fixture file containing it is reported, a ``-C`` with another verb is not."""
        tmp = Path(tempfile.mkdtemp(prefix="bo4300f2-c-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        _write(tmp, "templates/skills/x/SKILL.md", [f"run {_G} -C /w commit -m x", f'cmd = ["{_G}", "-C", wt, "commit", "-m", m]', f"{_G} -C /w status"])
        reported = fx.census(tmp, fx.commit_census_files(fx.walk_files(tmp)), fx.DASH_C_COMMIT_RES)
        self.assertEqual(["templates/skills/x/SKILL.md:1", "templates/skills/x/SKILL.md:2"], reported)

        files = fx.tracked_files()
        hits = fx.census(REPO_ROOT, fx.commit_census_files(files), fx.DASH_C_COMMIT_RES, apply_exemptions=False)
        self.assertEqual([], hits, "commit spelled with -C (the delegation hook misses it):\n" + "\n".join(hits))


class TestCensusMechanics(_TmpCase):
    def test_census_reports_a_how_to_hit_but_not_the_same_text_in_an_analysis(self):
        # covers: BO-4300f-2
        # angle: boundary
        """Same instruction in docs/how-to and docs/analysis: only the how-to hit is reported (file and
        line). A second helper beside the exempt legacy helper is reported; the exempt one is not."""
        tmp = self.tmp()
        line = _old_way_line("add")
        _write(tmp, "docs/how-to/x.md", ["# x", "", line])
        _write(tmp, "docs/analysis/x.md", ["# x", "", line])
        _write(tmp, "unit_tests/build_orchestration/_workspace_maker_builders.py", ["a", line])
        _write(tmp, "unit_tests/build_orchestration/_workspace_maker_other_helper.py", ["a", "b", line])
        hits = fx.census(tmp, fx.walk_files(tmp))
        self.assertEqual(
            ["docs/how-to/x.md:3", "unit_tests/build_orchestration/_workspace_maker_other_helper.py:3"], sorted(hits)
        )

    def test_census_excludes_adrs_but_reports_component_docs(self):
        # covers: BO-4300f-2
        # angle: boundary
        """An ADR is a record of the past (excluded by folder); a component doc is not."""
        tmp = self.tmp()
        line = _old_way_line("remove")
        _write(tmp, "docs/architecture/adrs/ADR-1.md", ["x", line])
        _write(tmp, "docs/architecture/components/c.md", ["x", "y", line])
        _write(tmp, "docs/architecture/diagrams/d.md", ["x", line])
        self.assertEqual(
            ["docs/architecture/components/c.md:3", "docs/architecture/diagrams/d.md:2"],
            sorted(fx.census(tmp, fx.walk_files(tmp))),
        )

    def test_census_detects_every_spelling_of_the_commands(self):
        # covers: BO-4300f-2
        # angle: failure
        """Shell, -C (folder first), Python argv list and JS template literal are each reported; the
        exempt cut-over verb's file is not, though it holds the same text."""
        tmp = self.tmp()
        _write(tmp, "scripts/shell_form.sh", [_old_way_line("add", "shell")])
        _write(tmp, "scripts/c_form.sh", [_old_way_line("remove", "dash_c")])
        _write(tmp, "scripts/argv_form.py", [_old_way_line("add", "argv")])
        _write(tmp, "scripts/argv_c_form.py", [_old_way_line("remove", "argv_dash_c")])
        _write(tmp, "templates/workflows-js/js_form.js", [_old_way_line("add", "js")])
        verb = fx.EXEMPT_FILES[0]
        _write(tmp, verb, [_old_way_line("add"), _old_way_line("remove", "argv")])
        reported = sorted(fx.census(tmp, fx.walk_files(tmp)))
        self.assertEqual(
            [
                "scripts/argv_c_form.py:1",
                "scripts/argv_form.py:1",
                "scripts/c_form.sh:1",
                "scripts/shell_form.sh:1",
                "templates/workflows-js/js_form.js:1",
            ],
            reported,
        )
        self.assertEqual([], fx.census(tmp, [verb]), "the exempt cut-over verb's file must report nothing")

    def test_census_exemption_list_is_one_declared_list_with_reasons_and_folder_entries(self):
        # covers: BO-4300f-2
        # angle: criterion
        """One list; every entry has a reason; exactly the seven record folders as folder entries; the
        only file entries are the cut-over verb and the one legacy workspace test helper."""
        entries = fx.EXEMPTIONS
        self.assertTrue(entries and all(e.get("reason", "").strip() for e in entries), "every entry needs a reason")
        folders = sorted(e["path"] for e in entries if e["kind"] == "folder")
        self.assertEqual(
            sorted(
                [
                    "docs/analysis/",
                    "docs/known-issues/",
                    "docs/retrospectives/",
                    "changelogs/",
                    "docs/architecture/adrs/",
                    "tickets/",
                    "docs/acceptance-criteria/",
                ]
            ),
            folders,
        )
        self.assertTrue(all(f.endswith("/") for f in folders))
        files = sorted(e["path"] for e in entries if e["kind"] == "file")
        self.assertEqual(
            ["templates/scripts/worktree_migrate.py", "unit_tests/build_orchestration/_workspace_maker_builders.py"], files
        )
        self.assertEqual({"file", "folder"}, {e["kind"] for e in entries})
        for f in files:
            self.assertTrue((REPO_ROOT / f).is_file(), f"exempt file {f} must exist in the repository")
        for d in folders:
            self.assertTrue((REPO_ROOT / d).is_dir(), f"record folder {d} must exist in the repository")


class TestBuildRefusesAnImplicitBuildIntoThePackage(_TmpCase):
    def _disposable_package(self) -> Path:
        copy = self.tmp() / "pkg"
        ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
        for top in ("scripts", "templates", "config"):
            shutil.copytree(REPO_ROOT / top, copy / top, ignore=ignore)
        skip = {".git", ".build_manifest.json", ".leafcutter.lock", ".pre-commit-config.yaml"}
        for f in REPO_ROOT.iterdir():
            if f.is_file() and f.name not in skip:
                shutil.copy2(f, copy / f.name)
        # Explicit GIT_DIR/GIT_WORK_TREE: the copy must never resolve to THIS repository's own
        # git directory (the checkout this test runs in is itself a linked workspace).
        env = self._git_env(copy)
        (copy / ".git").mkdir()
        for args in (
            ["init", "-q", "-b", "main"],
            ["add", "-A"],
            ["-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "--no-verify", "-m", "copy"],
        ):
            subprocess.run([_G, *args], cwd=str(copy), env=env, capture_output=True, check=True)
        return copy

    @staticmethod
    def _git_env(copy: Path) -> dict[str, str]:
        return {
            **os.environ,
            "GIT_DIR": str(copy / ".git"),
            "GIT_WORK_TREE": str(copy),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
        }

    def _status(self, copy: Path) -> str:
        return subprocess.run(
            [_G, "status", "--porcelain", "--ignored"], cwd=str(copy), env=self._git_env(copy),
            capture_output=True, text=True, check=True,
        ).stdout

    def test_build_refuses_an_implicit_build_into_the_package_repository(self):
        # covers: BO-4300f-2
        # angle: failure
        """No --target-dir, run from the package root of a disposable copy: exit non-zero naming the
        rule and --target-dir, before any phase wrote anything (no .leafcutter/, status unchanged).
        Control row: --validate-only with an explicit --target-dir is not refused (exit 0)."""
        copy = self._disposable_package()
        before = self._status(copy)
        try:
            proc = subprocess.run(
                [sys.executable, "scripts/build.py"], cwd=str(copy), capture_output=True, text=True, timeout=90
            )
        except subprocess.TimeoutExpired:
            self.fail("an implicit build into the package repository ran instead of being refused")
        output = proc.stdout + proc.stderr
        self.assertNotEqual(0, proc.returncode, "an implicit build into the package must exit non-zero")
        self.assertIn("--target-dir", output)
        self.assertRegex(output.lower(), r"package|repository", "the message must name the rule")
        self.assertFalse((copy / ".leafcutter").exists(), "no install folder may be created")
        self.assertEqual(before, self._status(copy), "the copy's working tree must be unchanged")

        control = subprocess.run(
            [sys.executable, "scripts/build.py", "--validate-only", "--target-dir", "."],
            cwd=str(copy), capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(0, control.returncode, control.stdout + control.stderr)


def main(argv: list[str] | None = None) -> int:
    """``--census``: print the real tree's hits as file:line; exit 1 when there are any."""
    args = sys.argv[1:] if argv is None else argv
    if "--census" not in args:
        print("usage: test_bo_4300f_2 --census", file=sys.stderr)
        return 2
    hits = fx.census(REPO_ROOT, fx.tracked_files())
    for h in hits:
        print(h)
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
