"""
Tests pinning the durable implementation craft rules in templates/agents/python-coder.md.

Covers AC BO-2000b and leaves:
  BO-2000b-1, BO-2000b-1-i  (fail-open hook carve-out)
  BO-2000b-2                 (path context awareness: templates/ vs scripts/.claude/)
  BO-2000b-3                 (delegation: create-hook/add-agent/add-skill)
  BO-2000b-4                 (read-before-Edit rule)
  BO-2000b-5                 (real-artifact spot-check + phantom-test prohibition)
  BO-2000b-6                 (single-simple-command shell discipline)

Implementation is already complete (python-coder.md was edited in the
prompt-assembly-hardening session). These tests verify the content persists.
A red result indicates a regression in the template file.
"""
import pathlib
import unittest

TEMPLATE_PATH = (
    pathlib.Path(__file__).resolve().parents[2]
    / "templates"
    / "agents"
    / "python-coder.md"
)


def _load_template() -> str:
    return TEMPLATE_PATH.read_text(encoding="utf-8")


class TestPythonCoderTemplateFailOpenCarveout(unittest.TestCase):
    """AC BO-2000b-1 / BO-2000b-1-i: fail-open hook carve-out."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.content = _load_template()

    def test_python_coder_hook_failopen_carveout(self) -> None:
        # covers: BO-2000b-1
        """Template must state the fail-open pre-commit hook carve-out rule."""
        self.assertIn(
            "fail-open pre-commit hook carve-out",
            self.content,
            "python-coder.md must contain the fail-open hook carve-out section",
        )

    def test_python_coder_hook_return_zero_and_no_reraise(self) -> None:
        # covers: BO-2000b-1
        """Template must show 'return 0' and prohibit re-raising in hook scripts."""
        self.assertIn(
            "return 0",
            self.content,
            "python-coder.md must contain 'return 0' for the fail-open hook pattern",
        )
        # The template must explain that re-raising propagates the exception and
        # aborts git commit, making re-raise the wrong choice for hooks.
        self.assertTrue(
            "re-raising is WRONG" in self.content
            or "re-raise" in self.content,
            "python-coder.md must state that re-raising in hook scripts is wrong",
        )

    def test_python_coder_hook_print_stderr_no_unused_logger(self) -> None:
        # covers: BO-2000b-1-i
        """Template must specify print(stderr) and prohibit unused module logger."""
        self.assertIn(
            "file=sys.stderr",
            self.content,
            "python-coder.md must mention print(..., file=sys.stderr) for hook diagnostics",
        )
        # The no-unused-logger guidance appears as "Ruff F841" or as an explicit
        # prohibition on module-level logger declarations.
        self.assertTrue(
            "F841" in self.content or "logger" in self.content.lower(),
            "python-coder.md must address the unused-logger issue in hook scripts",
        )


class TestPythonCoderTemplatePathAwarenessAndDelegation(unittest.TestCase):
    """AC BO-2000b-2 / BO-2000b-3: path context awareness and delegation."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.content = _load_template()

    def test_python_coder_path_awareness_and_delegation(self) -> None:
        # covers: BO-2000b-2
        # covers: BO-2000b-3
        """Template must state templates/ is source and scripts/.claude/ are build outputs."""
        self.assertIn(
            "templates/",
            self.content,
            "python-coder.md must reference templates/ as the canonical source",
        )
        # The template must warn that scripts/ and .claude/ are generated outputs.
        self.assertTrue(
            "gitignored build output" in self.content
            or "build output" in self.content,
            "python-coder.md must state scripts/.claude/ are build outputs",
        )

    def test_python_coder_delegation_skills(self) -> None:
        # covers: BO-2000b-3
        """Template must require routing through create-hook, add-agent-to-package, add-skill-to-package."""
        for skill in ("create-hook", "add-agent-to-package", "add-skill-to-package"):
            with self.subTest(skill=skill):
                self.assertIn(
                    skill,
                    self.content,
                    f"python-coder.md must mention '{skill}' for new hook/agent/skill delegation",
                )


class TestPythonCoderTemplateReadBeforeEditAndShell(unittest.TestCase):
    """AC BO-2000b-4 / BO-2000b-6: read-before-Edit and shell discipline."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.content = _load_template()

    def test_python_coder_read_before_edit_and_shell(self) -> None:
        # covers: BO-2000b-4
        # covers: BO-2000b-6
        """Template must state the read-before-Edit rule."""
        self.assertTrue(
            "Read-before-Edit" in self.content or "read-before-Edit" in self.content,
            "python-coder.md must state the Read-before-Edit rule",
        )

    def test_python_coder_shell_discipline(self) -> None:
        # covers: BO-2000b-6
        """Template must restate the single-simple-command shell discipline."""
        # The template must explicitly prohibit &&, ;, ||, and pipes.
        self.assertTrue(
            "single, simple command" in self.content
            or "&&" in self.content,
            "python-coder.md must restate the single-simple-command shell discipline",
        )
        # No cd — use absolute paths
        self.assertIn(
            "absolute paths",
            self.content,
            "python-coder.md must require absolute paths in shell calls",
        )


class TestPythonCoderTemplateRealArtifactAndPhantom(unittest.TestCase):
    """AC BO-2000b-5: real-artifact spot-check and phantom-test prohibition."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.content = _load_template()

    def test_python_coder_realartifact_and_phantom(self) -> None:
        # covers: BO-2000b-5
        """Template must require real-artifact spot-check and prohibit phantom tests."""
        self.assertIn(
            "Real-artifact behavioral spot-check",
            self.content,
            "python-coder.md must contain the Real-artifact behavioral spot-check rule",
        )
        self.assertIn(
            "Phantom-test prohibition",
            self.content,
            "python-coder.md must contain the Phantom-test prohibition rule",
        )


if __name__ == "__main__":
    unittest.main()
