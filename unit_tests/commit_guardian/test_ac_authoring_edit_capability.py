"""An agent template that instructs its agent to use a tool must grant that tool.

Covers AR-200b-1.

This is the AR-200 rule ("capability matches obligation") applied to a second,
distinct obligation source. AR-200a-1 derives the obligation from the sign-off
protocol: an agent required to record a verdict must hold a write-capable tool.
The obligation here is narrower and more literal -- an agent template whose BODY
names a specific tool as the way to perform a mandatory step must list that tool
in its ``tools:`` frontmatter.

The live instance this was written against: ``product-owner``,
``business-analyst`` and ``it-po`` each carry an S6b "parent covered_by update"
section marked mandatory, each of which says in so many words to use an ``Edit``
call that modifies only the ``covered_by`` field. None of the three listed
``Edit``. Four authoring agents run consecutively on 2026-08-26 hit this, and all
four fell back to rewriting the whole parent file with ``Write``.

Why that fallback is not an acceptable substitute, and why this is a real defect
rather than a cosmetic one:

* ``Write`` replaces a file wholesale. ``Edit`` cannot -- it requires an exact
  match on the text being replaced, so it fails closed where ``Write`` silently
  truncates.
* AC YAML files are untracked until committed. A truncating ``Write`` on a file
  that has never been committed is unrecoverable; there is no ``git checkout``
  to fall back to.
* It happened. One of the four agents leaked stray markup into a file tail on
  its first ``Write`` and caught it only on a manual tail inspection it was not
  obliged to perform.
* The usual proof that a rewrite was surgical -- ``git diff --stat`` -- is
  VACUOUS for an untracked file. It reports nothing whether the file survived
  intact or was emptied.

DERIVE BOTH SIDES, DO NOT HARDCODE THE THREE NAMES. The point of the rule is to
catch the fourth instance, which nobody has noticed yet. Scanning every template
is what makes this a rule rather than a patch. AR-200a-1's evidence is the
precedent: a derived rule found five violators where the incident report named
three.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEMPLATES = _REPO_ROOT / "templates" / "agents"

#: Tools whose absence is a real capability gap when the body mandates them.
#: Deliberately narrow: only tools that mutate state. A body mentioning "Read"
#: without granting it is a bug too, but a harmless one -- the agent simply
#: cannot proceed, loudly. The gap this rule exists for is the one where the
#: agent CAN proceed, by a riskier route, and does.
_MUTATING_TOOLS = ("Edit", "Write", "NotebookEdit")

#: Phrasings that constitute an instruction to USE a tool, as opposed to
#: incidental prose about it. Matched case-sensitively against the tool name so
#: that "edit the file" (generic English) does not match "Edit" (the tool).
_MANDATE_PATTERNS = (
    r"an?\s+`{tool}`\s+call",
    r"[Uu]se\s+an?\s+`{tool}`",
    r"`{tool}`\s+tool\s+to\b",
    r"[Uu]sing\s+the\s+`{tool}`\s+tool",
)


def _iter_templates() -> list[Path]:
    """Every agent template shipped by the package."""
    return sorted(p for p in _TEMPLATES.glob("*.md") if p.is_file())


def _frontmatter_tools(text: str) -> set[str] | None:
    """Return the declared tool set, or None when the template declares none.

    A template with no ``tools:`` line inherits the default allowlist, which is
    outside this rule's scope -- it is not a mismatch between a declaration and
    a body, because there is no declaration.
    """
    match = re.search(r"^tools:\s*(.+)$", text, re.MULTILINE)
    if match is None:
        return None
    declared = match.group(1).split("#", 1)[0]
    return {tool.strip() for tool in declared.split(",") if tool.strip()}


def _mandated_tools(text: str) -> set[str]:
    """Return mutating tools the template's own body tells the agent to use."""
    body = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.DOTALL)
    mandated: set[str] = set()
    for tool in _MUTATING_TOOLS:
        for pattern in _MANDATE_PATTERNS:
            if re.search(pattern.format(tool=re.escape(tool)), body):
                mandated.add(tool)
                break
    return mandated


class TestMandatedToolsAreGranted(unittest.TestCase):
    """The rule, derived over the whole registry."""

    def test_ar200b1_every_mandated_tool_is_in_the_allowlist(self) -> None:
        # covers: AR-200b-1
        violations: list[str] = []
        for template in _iter_templates():
            text = template.read_text(encoding="utf-8")
            granted = _frontmatter_tools(text)
            if granted is None:
                continue
            missing = _mandated_tools(text) - granted
            for tool in sorted(missing):
                violations.append(
                    f"{template.name}: body instructs the agent to use `{tool}`, "
                    f"but `tools:` grants only {sorted(granted)}"
                )

        self.assertEqual(
            [],
            violations,
            "An agent template must grant every mutating tool its own body "
            "instructs the agent to use. Granting the capability is the fix; "
            "deleting the instruction is NOT, because the instruction encodes "
            "the safe way to perform the step -- a surgical Edit rather than a "
            "whole-file Write on an untracked, unrecoverable file.\n  "
            + "\n  ".join(violations),
        )

    def test_ar200b1_detector_fires_on_a_synthetic_violator(self) -> None:
        # covers: AR-200b-1
        """The load-bearing test.

        Once the three real instances are fixed, the test above can never fail
        again on today's tree -- so on its own it would decay into a test that
        proves only that the loop runs. This one keeps the DETECTOR honest by
        feeding it a template that definitely violates the rule.
        """
        synthetic = (
            "---\n"
            "name: pretend-agent\n"
            "tools: Read, Bash\n"
            "requires_verification: false\n"
            "---\n"
            "\n"
            "## Mandatory step\n"
            "\n"
            "Update the parent using an `Edit` call that modifies ONLY the\n"
            "`covered_by` field.\n"
        )
        granted = _frontmatter_tools(synthetic)
        self.assertEqual({"Read", "Bash"}, granted)
        self.assertEqual(
            {"Edit"},
            _mandated_tools(synthetic) - (granted or set()),
            "The detector must flag a template that mandates `Edit` without "
            "granting it. If this fails, the rule above is vacuous.",
        )

    def test_ar200b1_detector_does_not_fire_on_generic_english(self) -> None:
        # covers: AR-200b-1
        """Control: prose about editing is not an instruction to use `Edit`.

        Without this, the cheapest way to pass the rule is a detector that
        matches the bare word and flags every template in the repository.
        """
        benign = (
            "---\n"
            "name: pretend-reader\n"
            "tools: Read, Bash\n"
            "---\n"
            "\n"
            "Do not edit the file. Report what you found and let the operator\n"
            "edit it. Writing to the store is out of scope.\n"
        )
        self.assertEqual(
            set(),
            _mandated_tools(benign),
            "Generic English about editing must not be read as a tool mandate.",
        )

    def test_ar200b1_rule_scans_the_whole_registry(self) -> None:
        # covers: AR-200b-1
        """A guard on the guard: the scan must actually reach the templates.

        A rule that silently resolves to zero files passes forever. This repo
        has shipped that exact defect before -- ``validate_ac_schema.py``'s
        bare-directory argument matched nothing, printed a success line and
        exited 0 for eight days (KI-ACS-001).
        """
        templates = _iter_templates()
        self.assertGreater(
            len(templates),
            20,
            f"Expected the full agent registry under {_TEMPLATES}; "
            f"found {len(templates)}. A near-empty scan makes the rule vacuous.",
        )
        with_declared_tools = [
            t for t in templates if _frontmatter_tools(t.read_text(encoding="utf-8"))
        ]
        self.assertGreater(
            len(with_declared_tools),
            20,
            "Expected most templates to declare a tools: allowlist.",
        )


if __name__ == "__main__":
    unittest.main()
