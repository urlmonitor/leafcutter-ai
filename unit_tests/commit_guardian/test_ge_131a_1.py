"""
MODULE: unit_tests/commit_guardian/test_ge_131a_1.py
COVERS: GE-131a-1 -- "Each staged function is held to the greater of the limit
    and its own highest previous score, and a file that cannot be judged is
    never passed as clean"

GOAL: Behavioural proof of the per-function complexity ratchet. Every test
    performs a REAL `git init`, REAL commits establishing the previous
    scores, a REAL `git add` of the staged change, then runs the REAL
    check_complexity.py (or run_hook.py) as a subprocess and reads the real
    exit code and output. Source text is produced by the generator below
    (never a checked-in literal); the git history is real.

SCORING: a generated function with N-1 independent `if` statements scores N
    under the shipped counting rule (base 1, +1 per `if`).

DECISION HISTORY
- 2026-10-09 [GE-131a-1/test-writer]: Initial RED authoring, one test per arm
    plus a reachability test through run_hook.py.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMIT_GUARDIAN_DIR = REPO_ROOT / "templates" / "scripts" / "commit_guardian"
CHECK_COMPLEXITY = COMMIT_GUARDIAN_DIR / "check_complexity.py"
RUN_HOOK = COMMIT_GUARDIAN_DIR / "run_hook.py"
PYTHON = sys.executable
TIMEOUT = 60
TARGET = "scripts/planner.py"


def git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Run a real git command in *cwd*."""
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=TIMEOUT, check=check)


def func(name: str, score: int, indent: str = "") -> str:
    """Source for a function whose complexity score is exactly *score*."""
    body = "".join(f"{indent}    if x == {i}:\n{indent}        pass\n" for i in range(score - 1))
    return f"{indent}def {name}(x):\n{body}{indent}    return x\n"


def module(**scores: int) -> str:
    """A module holding one top-level function per keyword, in order."""
    return "\n\n".join(func(name, score) for name, score in scores.items())


def nested_module(encode: int, decode: int) -> str:
    """A module whose encode() and decode() each hold a nested visit()."""
    parts = []
    for outer, score in (("encode", encode), ("decode", decode)):
        parts.append(f"def {outer}(x):\n" + func("visit", score, indent="    ") + "    return visit\n")
    return "\n\n".join(parts)


def run_check(cwd: Path, via_hook: bool = False) -> subprocess.CompletedProcess:
    """Invoke the real check_complexity.py (optionally through run_hook.py)."""
    argv = [PYTHON, str(RUN_HOOK), str(CHECK_COMPLEXITY)] if via_hook else [PYTHON, str(CHECK_COMPLEXITY)]
    return subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, timeout=TIMEOUT)


def output_of(result: subprocess.CompletedProcess) -> str:
    return result.stdout + result.stderr


def lines_naming(output: str, name: str) -> list[str]:
    """Output lines that mention *name* as a whole token (dots allowed in name)."""
    pattern = re.compile(r"(?<![\w.])" + re.escape(name) + r"(?![\w])")
    return [line for line in output.splitlines() if pattern.search(line)]


def has_number(text: str, number: int) -> bool:
    return re.search(rf"(?<!\d){number}(?!\d)", text) is not None


class RepoCase(unittest.TestCase):
    """A real git repo with the committed baseline written by commit_baseline()."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        git(["init", "-q", "-b", "main"], self.root)
        git(["config", "user.email", "test-writer@example.com"], self.root)
        git(["config", "user.name", "GE-131a-1 fixture"], self.root)

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit_baseline(self, text: str) -> None:
        self.write(TARGET, text)
        git(["add", "-A"], self.root)
        git(["commit", "-q", "-m", "baseline"], self.root)

    def stage(self, text: str) -> subprocess.CompletedProcess:
        self.write(TARGET, text)
        git(["add", TARGET], self.root)
        return run_check(self.root)


class TestGe131a1(RepoCase):
    def test_offender_kept_or_reduced_is_allowed(self):
        # covers: GE-131a-1
        # angle: criterion
        """Arm 1: committed plan_batches=30; staged at 30, and at 22, both exit 0.

        Must implement: ceiling = max(limit, function's own highest previous score).
        """
        self.commit_baseline(module(plan_batches=30, load_rules=12))
        # load_rules moves 12 -> 11 so the staged 30 case is a REAL staged change
        # (identical content would stage nothing and exit 0 vacuously).
        for staged_score in (30, 22):
            with self.subTest(staged_score=staged_score):
                result = self.stage(module(plan_batches=staged_score, load_rules=11))
                self.assertEqual(result.returncode, 0, output_of(result))

    def test_offender_raised_above_own_score_is_refused_naming_ceiling(self):
        # covers: GE-131a-1
        # angle: failure
        """Arm 2: staged 31 over committed 30 is refused naming plan_batches, 31 and ceiling 30."""
        self.commit_baseline(module(plan_batches=30, load_rules=12))
        result = self.stage(module(plan_batches=31, load_rules=12))
        out = output_of(result)
        self.assertNotEqual(result.returncode, 0, out)
        named = lines_naming(out, "plan_batches")
        self.assertTrue(named, out)
        text = "\n".join(named)
        self.assertTrue(has_number(text, 31), out)
        self.assertTrue(has_number(text, 30), f"ceiling 30 not stated: {out}")
        self.assertFalse(lines_naming(out, "load_rules"), f"unchanged load_rules wrongly named: {out}")

    def test_new_or_crossing_function_is_held_to_limit(self):
        # covers: GE-131a-1
        # angle: boundary
        """Arm 3: new parse_rules=16 ('new') and load_rules 12->16 ('crossed') refused vs 15; new 15 allowed."""
        self.commit_baseline(module(plan_batches=30, load_rules=12))

        new_over = self.stage(module(plan_batches=30, load_rules=12, parse_rules=16))
        out = output_of(new_over)
        self.assertNotEqual(new_over.returncode, 0, out)
        text = "\n".join(lines_naming(out, "parse_rules"))
        self.assertTrue(text, out)
        self.assertTrue(has_number(text, 16) and has_number(text, 15), out)
        self.assertIn("new", text.lower(), out)
        self.assertNotIn("crossed", text.lower(), out)
        self.assertFalse(lines_naming(out, "plan_batches"), f"plan_batches at its own ceiling wrongly named: {out}")

        crossed = self.stage(module(plan_batches=30, load_rules=16))
        out = output_of(crossed)
        self.assertNotEqual(crossed.returncode, 0, out)
        text = "\n".join(lines_naming(out, "load_rules"))
        self.assertTrue(text, out)
        self.assertTrue(has_number(text, 16) and has_number(text, 15), out)
        self.assertIn("crossed", text.lower(), out)
        self.assertNotIn("new", text.lower().replace("renew", ""), out)

        new_at_limit = self.stage(module(plan_batches=30, load_rules=12, parse_rules=15))
        self.assertEqual(new_at_limit.returncode, 0, output_of(new_at_limit))

    def test_staged_blob_is_judged_not_working_tree(self):
        # covers: GE-131a-1
        # angle: discrimination
        """Arm 4: staged 31, working tree put back to 30: refused naming score 31 and ceiling 30.

        Wrong version caught: reading the working-tree file instead of the staged blob.
        """
        self.commit_baseline(module(plan_batches=30, load_rules=12))
        self.write(TARGET, module(plan_batches=31, load_rules=12))
        git(["add", TARGET], self.root)
        self.write(TARGET, module(plan_batches=30, load_rules=12))
        result = run_check(self.root)
        out = output_of(result)
        self.assertNotEqual(result.returncode, 0, out)
        text = "\n".join(lines_naming(out, "plan_batches"))
        self.assertTrue(has_number(text, 31), f"staged score 31 not reported: {out}")
        self.assertTrue(has_number(text, 30), f"ceiling 30 not reported: {out}")

    def test_merge_ceiling_is_highest_parent_score(self):
        # covers: GE-131a-1
        # angle: criterion
        """Arm 5: merge with HEAD 30 / MERGE_HEAD 40: staged 40 allowed, 41 refused naming ceiling 40.

        Wrong version caught: ceiling taken from HEAD only.
        """
        self.commit_baseline(module(plan_batches=30, load_rules=12))
        git(["checkout", "-q", "-b", "side"], self.root)
        self.write(TARGET, module(plan_batches=40, load_rules=12))
        git(["commit", "-q", "-am", "side raises to 40"], self.root)
        git(["checkout", "-q", "main"], self.root)
        self.write("scripts/other.py", "VALUE = 1\n")
        git(["add", "-A"], self.root)
        git(["commit", "-q", "-m", "main diverges"], self.root)
        git(["merge", "--no-commit", "--no-ff", "side"], self.root, check=False)
        merge_head = git(["rev-parse", "--git-path", "MERGE_HEAD"], self.root).stdout.strip()
        self.assertTrue((self.root / merge_head).is_file(), "fixture failed to enter a merge")

        allowed = self.stage(module(plan_batches=40, load_rules=12))
        self.assertEqual(allowed.returncode, 0, output_of(allowed))

        refused = self.stage(module(plan_batches=41, load_rules=12))
        out = output_of(refused)
        self.assertNotEqual(refused.returncode, 0, out)
        text = "\n".join(lines_naming(out, "plan_batches"))
        self.assertTrue(has_number(text, 41) and has_number(text, 40), out)

    def test_same_named_nested_functions_keep_separate_ceilings(self):
        # covers: GE-131a-1
        # angle: discrimination
        """Arm 6: encode.visit=20 unchanged, decode.visit 9->18: decode.visit refused vs 15; encode.visit not named.

        Wrong version caught: bare-name identity lends encode.visit's 20 to decode.visit.
        """
        self.commit_baseline(nested_module(encode=20, decode=9))
        result = self.stage(nested_module(encode=20, decode=18))
        out = output_of(result)
        self.assertNotEqual(result.returncode, 0, out)
        text = "\n".join(lines_naming(out, "decode.visit"))
        self.assertTrue(text, f"decode.visit not named: {out}")
        self.assertTrue(has_number(text, 18) and has_number(text, 15), out)
        self.assertFalse(lines_naming(out, "encode.visit"), f"encode.visit wrongly refused: {out}")

    def test_unparseable_or_unreadable_file_is_never_passed_clean(self):
        # covers: GE-131a-1
        # angle: failure
        """Arm 7: a syntax-error .py and a non-UTF-8 .py are each refused or reported by name, never silently clean."""
        self.commit_baseline(module(plan_batches=30, load_rules=12))
        bad_bytes = {
            "broken_syntax.py": b"def (:\n    pass\n",
            "not_utf8.py": b"X = '\xff\xfe\xfa'\n",
        }
        for name, payload in bad_bytes.items():
            with self.subTest(file=name):
                (self.root / "scripts").mkdir(exist_ok=True)
                (self.root / "scripts" / name).write_bytes(payload)
                git(["add", f"scripts/{name}"], self.root)
                result = run_check(self.root)
                out = output_of(result)
                mentioned = name in out
                self.assertTrue(result.returncode != 0 or mentioned, f"silently passed: {out!r}")
                self.assertTrue(mentioned, f"file not named: {out!r}")
                if result.returncode == 0:
                    self.assertTrue("could not" in out.lower() or "could_not_check" in out.lower(), out)
                git(["reset", "-q", "--", f"scripts/{name}"], self.root)
                (self.root / "scripts" / name).unlink()

    def test_ge_131a_1_reachable_from_entry_point(self):
        # covers: GE-131a-1
        # angle: reachability
        """The registered hook runner (run_hook.py) reaches the ratchet: staged 31 over 30 is refused with the ceiling."""
        self.commit_baseline(module(plan_batches=30, load_rules=12))
        self.write(TARGET, module(plan_batches=31, load_rules=12))
        git(["add", TARGET], self.root)
        result = run_check(self.root, via_hook=True)
        out = output_of(result)
        self.assertNotEqual(result.returncode, 0, out)
        text = "\n".join(lines_naming(out, "plan_batches"))
        self.assertTrue(has_number(text, 31) and has_number(text, 30), out)

        self.write(TARGET, module(plan_batches=30, load_rules=11))
        git(["add", TARGET], self.root)
        allowed = run_check(self.root, via_hook=True)
        self.assertEqual(allowed.returncode, 0, output_of(allowed))


if __name__ == "__main__":
    unittest.main()
