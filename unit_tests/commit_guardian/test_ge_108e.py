"""
Tests for GE-108e — templates/hooks/check_exception_handling_hook.py must
find ruff the same way the rest of the project does.

`_run_ruff` asked the operating system for a `ruff` executable, while the
project's own lint step reaches ruff as a module. On a machine where ruff
is importable but exposes no console script on PATH, the hook took its
not-installed branch and blocked every Python write — while
`python -m ruff --version` answered perfectly well.

Split out of test_exception_hook.py: adding these three arms took that file
to 453 measured lines against a 400 limit and check-file-size refused the
commit. The subprocess plumbing both files need now lives in
_exception_hook_fixture.py so the hook's launch contract stays
single-sourced — which matters more than usual here, because the two files
deliberately differ ONLY in the environment they hand the child process.

The GE-108d-era arms (stderr routing, the not-installed branch) stay in
test_exception_hook.py.
"""
from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _exception_hook_fixture import _make_payload, _run_hook  # noqa: E402


class TestExceptionHookModuleOnlyRuffLookup(unittest.TestCase):
    """GE-108e — "is ruff installed" must get the same answer here as it
    gets everywhere else in the project: `python -m ruff` first, the bare
    `ruff` executable as a fallback.

    PRECONDITION verified manually before authoring these tests (2026-10-07,
    this environment): `python3 -c "import ruff"` succeeds (ruff resolves to
    ``~/.local/lib/python3.12/site-packages/ruff/__init__.py``, i.e. the
    interpreter's USER site-packages), while the bare `ruff` executable
    resolves via PATH (``~/.local/bin/ruff``) as a SEPARATE, independent
    resolution mechanism. Emptying PATH removes the executable without
    touching module importability, which is exactly the configuration this
    AC describes: "ruff is installed but exposes no console script on PATH."

    Also verified: setting ``PYTHONNOUSERSITE=1`` removes the module from
    that same interpreter (``ModuleNotFoundError: No module named 'ruff'``),
    and ``python -m ruff`` with the module genuinely absent EXITS 1 printing
    "No module named ruff" to stderr -- it does NOT raise. That is the
    environment test 3 below needs: neither module nor executable
    resolvable for the child process.
    """

    def test_importable_ruff_with_no_console_script_is_found_and_reports_the_violation(
        self,
    ) -> None:
        # covers: GE-108e
        # angle: criterion
        """PATH emptied so no `ruff` executable resolves on the child, but
        the child interpreter can still import ruff as a module (ruff lives
        in the interpreter's own user site-packages, which PATH does not
        gate). A file with a bare `except:` is checked.

        Asserts exit 2, "E722" present on stderr, AND the ruff-not-found
        install instruction ABSENT from stderr.

        RED before the fix: `_run_ruff` invoked the bare `ruff` executable
        only: with PATH emptied, `subprocess.run(["ruff", ...])` raises
        FileNotFoundError, main() takes the not-installed branch, and the
        hook reports ruff missing instead of finding the E722 violation --
        even though `python -m ruff` would have answered perfectly well.
        """
        bad_python = textwrap.dedent("""\
            def bad():
                try:
                    open("x")
                except:
                    pass
        """)
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write(bad_python)
            tmp_path = f.name

        with tempfile.TemporaryDirectory() as empty_dir:
            try:
                result = _run_hook(
                    _make_payload(tmp_path),
                    env={"PATH": empty_dir},
                )
                self.assertEqual(
                    result.returncode,
                    2,
                    msg=(
                        "Expected exit 2 (block) for bare except: even when "
                        "only the module form of ruff is available, got "
                        f"{result.returncode}.\n"
                        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                    ),
                )
                self.assertIn(
                    "E722",
                    result.stderr,
                    msg=(
                        "Expected 'E722' in stderr -- ruff was importable as "
                        f"a module the whole time. Got: {result.stderr!r}"
                    ),
                )
                self.assertNotIn(
                    "ruff not found on PATH",
                    result.stderr,
                    msg=(
                        "The not-installed install instruction must NOT "
                        "appear -- ruff genuinely was available via the "
                        f"module form. Got stderr: {result.stderr!r}"
                    ),
                )
            finally:
                Path(tmp_path).unlink(missing_ok=True)

    def test_clean_file_still_passes_when_ruff_is_module_only(self) -> None:
        # covers: GE-108e
        # angle: criterion
        """Same environment as above (PATH emptied, module still
        importable), but with a clean .py file.

        Asserts exit 0 and both streams empty -- finding ruff by the module
        route instead of the executable route must not change what a clean
        file does.

        RED before the fix for the same underlying reason as the sibling
        test above: the hook blocked even a clean file when the console
        script was missing, because it never tried the module form at all.
        """
        clean_python = textwrap.dedent("""\
            def greet(name: str) -> str:
                return f"Hello, {name}"
        """)
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write(clean_python)
            tmp_path = f.name

        with tempfile.TemporaryDirectory() as empty_dir:
            try:
                result = _run_hook(
                    _make_payload(tmp_path),
                    env={"PATH": empty_dir},
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    msg=(
                        "Expected exit 0 for a clean file when ruff is "
                        f"module-only, got {result.returncode}.\n"
                        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                    ),
                )
                self.assertEqual(
                    result.stdout.strip(),
                    "",
                    msg=f"Expected empty stdout. Got: {result.stdout!r}",
                )
                self.assertEqual(
                    result.stderr.strip(),
                    "",
                    msg=f"Expected empty stderr. Got: {result.stderr!r}",
                )
            finally:
                Path(tmp_path).unlink(missing_ok=True)

    def test_truly_absent_ruff_still_reports_the_install_instruction(self) -> None:
        # covers: GE-108e
        # angle: criterion
        """Regression guard, GREEN ON ARRIVAL -- protects GE-108d's stderr
        routing and the not-installed branch from being deleted by an
        over-eager fix to the two RED tests above.

        Neither the module nor the executable is available to the child:
        PATH is emptied (as above, removing the executable) AND
        `PYTHONNOUSERSITE=1` is set, which removes ruff's own package --
        installed under this interpreter's USER site-packages -- from the
        child's import path entirely (`ModuleNotFoundError: No module named
        'ruff'`), verified manually in this environment before writing this
        test. `python -m ruff` under that condition exits 1 and prints "No
        module named ruff" to stderr; it does not raise, which is exactly
        the "non-zero exit that is NOT a real E722 violation" case the AC's
        it_requirements warns must not be conflated with one -- the
        production fix must detect this specific case and fall through to
        the bare executable, which is then ALSO missing (empty PATH),
        raising FileNotFoundError and reaching main()'s pre-existing
        install-instruction branch.

        Asserts exit 2 and the install instruction present on stderr.
        """
        clean_python = textwrap.dedent("""\
            def greet(name: str) -> str:
                return f"Hello, {name}"
        """)
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", encoding="utf-8", delete=False
        ) as f:
            f.write(clean_python)
            tmp_path = f.name

        with tempfile.TemporaryDirectory() as empty_dir:
            try:
                result = _run_hook(
                    _make_payload(tmp_path),
                    env={"PATH": empty_dir, "PYTHONNOUSERSITE": "1"},
                )
                self.assertEqual(
                    result.returncode,
                    2,
                    msg=(
                        "Expected exit 2 when ruff is genuinely absent "
                        f"(neither module nor executable), got {result.returncode}.\n"
                        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
                    ),
                )
                install_keywords = ("ruff", "install")
                for kw in install_keywords:
                    self.assertIn(
                        kw,
                        result.stderr.lower(),
                        msg=(
                            f"Expected '{kw}' in install instruction on "
                            f"stderr. Got: {result.stderr!r}"
                        ),
                    )
            finally:
                Path(tmp_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-10-07 [GE-108e]: Split out of test_exception_hook.py, which
  reached 453 measured lines against a 400 limit when these three arms
  were added and was refused by check-file-size. The three arms are
  moved verbatim; only the helper imports changed, now coming from the
  new _exception_hook_fixture.py shared by both files.
====================================================================
"""
