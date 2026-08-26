"""
MODULE: test_agent_signoff_capability
GOAL: Registry-wide consistency test for AC AR-200a-1 — every agent template
    that carries a sign-off obligation must also declare a tool capable of
    performing the write that obligation requires.
BUSINESS CONTEXT: The sign-off protocol (templates/skills/signoff/SKILL.md)
    defines sign-off as an ATOMIC MUTATION of the ticket .md: the frontmatter
    `agents` map, the Sign-offs checklist and the Comments section, all in one
    pass. An agent template that declares that obligation while declaring only
    read tools has been handed a mandatory task its own definition forbids.
    Workflow run wf_394d2b76-014 halted on exactly this: `test-runner` ran all
    4 target tests green and the full 3984-test suite green, then returned
    `status: blocker / result_status: tests_pass_signoff_blocked_no_edit_tool`
    because it had no tool with which to record any of it. The only shell
    workarounds (`sed -i`, `python -c`, heredocs) are hard-forbidden by the
    global CLAUDE.md, and the tool allowlist is fixed at dispatch, so the
    mechanical-retry ladder re-dispatched an agent that could never succeed.
    This is a likely root cause of KI-BO-007 (phase counted complete while the
    agent halted without doing it): a read-only agent facing a mandatory write
    has two exits and only one of them is loud.

ARCHITECTURE: The rule is one reusable helper — `find_signoff_capability_violations`
    — and all three tests call it, so the synthetic and control cases exercise
    the same logic as the real-registry case rather than a lookalike. Both
    sides of the comparison are DERIVED from templates/agents/*.md on disk;
    nothing is hardcoded, so a phase agent added tomorrow with the same
    mismatch is reported without editing this file.

OBLIGATION SIGNAL (chosen deliberately — see AR-200a-1 constraint 3):
    A template is sign-off-obligated when EITHER structural signal is present:

      (1) frontmatter `signoff: true`     — the machine-readable declaration the
                                            build reads to dispatch the agent as
                                            a ticket phase; and
      (2) a body ATX heading matching     — the `## Sign-off (when ticket_path is
          `^#{1,6} Sign-off...`             provided)` section injected from
                                            templates/agents/_signoff_block.md,
                                            i.e. the instruction text that binds
                                            the running agent.

    Either declaration binds the agent, so the signal is their disjunction.

    EXPLICITLY REJECTED: a bare substring grep for "sign-off"/"signoff" anywhere
    in the file. Measured against this tree that signal is crude and wrong — it
    matches all 13 read-only, non-obligated templates (brainstorm-worker,
    brainstorm-lead, ac-triage, pt-classifier, glossary-triage, build-ac,
    knowledge-harvester, onboard-config-section, test-failure-triage,
    feedback-analyst, find-design-smells, find-structural-smells,
    code-review-architect), every one of which merely MENTIONS another agent's
    sign-off in prose or in a description. A substring rule would report 13
    false violators and be switched off within a week.

    SEPARATION CHECK (both signals, measured on this tree): each of the two
    signals independently selects all three known violators (test-runner,
    live-surface-tester, user-surface-smoker) AND all five correct
    counter-examples (ac-validator, ac-fulfillment-gate, pr-reviewer,
    documentation-verifier, change-scope-reviewer), and neither selects any of
    the 13 read-only non-obligated templates. The two signals agree on the
    violator set, which is the corroboration that the choice is not arbitrary.

CAPABILITY SIGNAL: a declared tool in {Edit, Write, NotebookEdit} (or the `*`
    wildcard). Bash is deliberately NOT write-capable for this rule: mutating a
    file from Bash is precisely what the global CLAUDE.md hard-forbids, and
    treating it as capable would make the rule vacuous — every agent has Bash.
    Agent is likewise not capable: it delegates, and the delegate is a different
    dispatch with its own allowlist (user-surface-smoker declares Agent and is
    still one of the three confirmed instances).

FAIL-CLOSED: a template whose frontmatter cannot be parsed is reported as a
    violation rather than skipped. Silence is not a pass.
"""

from __future__ import annotations

import re
import tempfile
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

import yaml

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_TEMPLATE_DIR = REPO_ROOT / "templates" / "agents"

# ---------------------------------------------------------------------------
# Rule constants
# ---------------------------------------------------------------------------

#: Tools that can perform the atomic ticket write the sign-off protocol requires.
WRITE_CAPABLE_TOOLS = frozenset({"Edit", "Write", "NotebookEdit"})

#: Wildcard allowlist (grants every tool, including the write-capable ones).
WILDCARD_TOOL = "*"

#: Body heading that marks the injected sign-off instruction block.
SIGNOFF_HEADING_RE = re.compile(
    r"^[ ]{0,3}#{1,6}[ \t]+sign[-\s]?off\b",
    re.IGNORECASE | re.MULTILINE,
)

#: Files in templates/agents/ that are not agent templates.
NON_TEMPLATE_FILENAMES = frozenset({"README.md"})

#: Human-readable description of the obligation, used in failure messages.
OBLIGATION_DESCRIPTION = (
    "sign-off: atomic write of the ticket .md "
    "(frontmatter agents map + Sign-offs checklist + Comments append)"
)


# ---------------------------------------------------------------------------
# Derived facts about a single template
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TemplateFacts:
    """Both sides of the comparison, derived from one template file."""

    name: str
    path: str
    tools: tuple[str, ...] = ()
    obligation_signals: tuple[str, ...] = ()
    parse_error: str | None = None

    @property
    def is_signoff_obligated(self) -> bool:
        return bool(self.obligation_signals)

    @property
    def has_write_capable_tool(self) -> bool:
        if WILDCARD_TOOL in self.tools:
            return True
        return any(tool in WRITE_CAPABLE_TOOLS for tool in self.tools)


@dataclass(frozen=True)
class Violation:
    """A template that carries the obligation without the capability."""

    name: str
    path: str
    obligation: str
    obligation_signals: tuple[str, ...] = ()
    declared_tools: tuple[str, ...] = ()
    missing_capability: tuple[str, ...] = field(
        default_factory=lambda: tuple(sorted(WRITE_CAPABLE_TOOLS))
    )
    reason: str = "no declared tool can perform the write"

    def describe(self) -> str:
        return (
            f"  - {self.name}  ({self.path})\n"
            f"      obligation : {self.obligation}\n"
            f"      signalled by: {', '.join(self.obligation_signals) or '(n/a)'}\n"
            f"      declares   : {', '.join(self.declared_tools) or '(none)'}\n"
            f"      missing    : at least one of "
            f"{', '.join(self.missing_capability)}\n"
            f"      why        : {self.reason}"
        )


# ---------------------------------------------------------------------------
# Parsing — derive both sides from the template text itself
# ---------------------------------------------------------------------------


def _split_frontmatter(text: str) -> tuple[str | None, str]:
    """Return ``(frontmatter_text, body_text)``; frontmatter is None if absent."""
    if not text.startswith("---"):
        return None, text
    parts = text.split("\n")
    if not parts or parts[0].strip() != "---":
        return None, text
    for index in range(1, len(parts)):
        if parts[index].strip() == "---":
            return "\n".join(parts[1:index]), "\n".join(parts[index + 1 :])
    return None, text


def _normalise_tools(raw: object) -> tuple[str, ...]:
    """Accept the string form (``Bash, Read, Edit``) or the YAML list form."""
    if raw is None:
        return ()
    if isinstance(raw, str):
        return tuple(part.strip() for part in raw.split(",") if part.strip())
    if isinstance(raw, (list, tuple)):
        return tuple(str(part).strip() for part in raw if str(part).strip())
    return (str(raw).strip(),)


def parse_agent_template(name: str, text: str) -> TemplateFacts:
    """Derive obligation signals and declared tools from one template's text.

    Pure function over the file text so the same code path serves the real
    registry, synthetic fixtures and any future caller (e.g. a pre-commit hook).
    """
    path = f"templates/agents/{name}.md"
    frontmatter_text, body = _split_frontmatter(text)

    if frontmatter_text is None:
        return TemplateFacts(
            name=name,
            path=path,
            parse_error="no YAML frontmatter block found",
        )

    try:
        frontmatter = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as exc:  # fail-closed: unparseable is not a pass
        return TemplateFacts(
            name=name, path=path, parse_error=f"unparseable frontmatter: {exc}"
        )

    if not isinstance(frontmatter, dict):
        return TemplateFacts(
            name=name,
            path=path,
            parse_error="frontmatter did not parse to a mapping",
        )

    signals: list[str] = []
    if frontmatter.get("signoff") is True:
        signals.append("frontmatter `signoff: true`")
    if SIGNOFF_HEADING_RE.search(body):
        signals.append("body `## Sign-off` instruction section")

    return TemplateFacts(
        name=str(frontmatter.get("name") or name),
        path=path,
        tools=_normalise_tools(frontmatter.get("tools")),
        obligation_signals=tuple(signals),
    )


def load_agent_templates(directory: Path) -> list[TemplateFacts]:
    """Derive facts for every agent template in ``directory``.

    Skips shared partials (leading underscore) and the directory README, which
    are include-fragments and documentation rather than dispatchable agents.
    """
    facts: list[TemplateFacts] = []
    for md_path in sorted(directory.glob("*.md")):
        if md_path.name.startswith("_") or md_path.name in NON_TEMPLATE_FILENAMES:
            continue
        text = md_path.read_text(encoding="utf-8")
        parsed = parse_agent_template(md_path.stem, text)
        if parsed.parse_error and "no YAML frontmatter" in parsed.parse_error:
            # A .md with no frontmatter in this directory is a fragment, not an
            # agent the build can dispatch.
            continue
        facts.append(parsed)
    return facts


# ---------------------------------------------------------------------------
# THE RULE — one helper, called by all three tests
# ---------------------------------------------------------------------------


def find_signoff_capability_violations(
    templates: Iterable[TemplateFacts],
) -> list[Violation]:
    """Report every template carrying a sign-off obligation it cannot discharge.

    A violation is a template that is sign-off-obligated (see the module
    docstring for the signal) while declaring no tool in
    :data:`WRITE_CAPABLE_TOOLS`. Templates whose frontmatter could not be parsed
    are also reported — fail-closed, since an unreadable template cannot be
    shown to be safe.
    """
    violations: list[Violation] = []
    for facts in templates:
        if facts.parse_error is not None:
            violations.append(
                Violation(
                    name=facts.name,
                    path=facts.path,
                    obligation=OBLIGATION_DESCRIPTION,
                    obligation_signals=("(undetermined — template unreadable)",),
                    declared_tools=facts.tools,
                    reason=(
                        f"fail-closed: could not determine capability "
                        f"({facts.parse_error})"
                    ),
                )
            )
            continue
        if facts.is_signoff_obligated and not facts.has_write_capable_tool:
            violations.append(
                Violation(
                    name=facts.name,
                    path=facts.path,
                    obligation=OBLIGATION_DESCRIPTION,
                    obligation_signals=facts.obligation_signals,
                    declared_tools=facts.tools,
                )
            )
    return sorted(violations, key=lambda v: v.name)


def format_violation_report(violations: Sequence[Violation]) -> str:
    """Operator-readable failure text: template, obligation, missing capability."""
    header = (
        f"{len(violations)} agent template(s) declare a sign-off obligation "
        f"they have no tool to discharge.\n"
        f"The sign-off protocol (templates/skills/signoff/SKILL.md) requires an "
        f"ATOMIC WRITE to the ticket .md.\n"
        f"FIX: grant the capability (add Edit to `tools:`, plus "
        f"`requires_verification: true`, per AR-200a-1) — do NOT remove the "
        f"obligation, which converts a loud blocker into a silent phantom-done.\n"
    )
    return header + "\n".join(v.describe() for v in violations)


# ---------------------------------------------------------------------------
# Synthetic fixture helpers (never written into templates/)
# ---------------------------------------------------------------------------


def _render_synthetic_template(
    frontmatter: dict, body: str, *, include_signoff_section: bool
) -> str:
    """Serialise a synthetic template through the REAL YAML serialiser.

    Per the fixture-authenticity rule, the frontmatter bytes are produced by
    ``yaml.safe_dump`` rather than hand-typed, so the parser under test is fed
    the same on-disk shape a real template has.
    """
    parts = ["---", yaml.safe_dump(frontmatter, sort_keys=False).rstrip(), "---", ""]
    parts.append(body.rstrip())
    if include_signoff_section:
        parts.append("")
        parts.append("## Sign-off (when ticket_path is provided)")
        parts.append("")
        parts.append("1. Load `.claude/skills/signoff/SKILL.md`.")
        parts.append("2. On success: follow the atomic sign-off recipe.")
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAgentSignoffCapability(unittest.TestCase):
    """AR-200a-1: obligation and capability must agree, in every template."""

    def test_every_signoff_obligated_agent_template_declares_a_write_capable_tool(
        self,
    ):
        # covers: AR-200a-1
        """Primary criterion, derived on both sides from templates/agents/*.md.

        No template may carry the sign-off obligation without declaring a tool
        that can perform the write. Every violator is named in the failure
        message so an operator can fix them all without opening this test.
        """
        self.assertTrue(
            AGENT_TEMPLATE_DIR.is_dir(),
            f"agent template directory not found: {AGENT_TEMPLATE_DIR}",
        )

        templates = load_agent_templates(AGENT_TEMPLATE_DIR)
        self.assertGreater(
            len(templates),
            10,
            "derived zero-or-few templates — the loader, not the registry, "
            "is probably broken",
        )

        obligated = [t for t in templates if t.is_signoff_obligated]
        self.assertGreater(
            len(obligated),
            0,
            "no template was detected as sign-off-obligated — the obligation "
            "signal has stopped matching and this rule is now vacuous",
        )

        violations = find_signoff_capability_violations(templates)

        self.assertEqual(
            [],
            violations,
            "\n" + format_violation_report(violations) if violations else "",
        )

    def test_the_rule_reports_a_synthetic_template_that_violates_it(self):
        # covers: AR-200a-1
        """Failure-path proof: the rule still bites once the real tree is fixed.

        Without this, the primary assertion above passes trivially after the
        known instances are corrected and could never fail again — the suite
        would record a rule it no longer checks. The synthetic template is
        written to a temp directory; nothing under templates/ is touched.
        """
        frontmatter_signoff_flag_only = {
            "name": "synthetic-readonly-phase-agent",
            "model": "sonnet",
            "tools": "Bash, Read",
            "portable": True,
            "signoff": True,
        }
        frontmatter_body_section_only = {
            "name": "synthetic-readonly-body-signoff-agent",
            "model": "sonnet",
            "tools": "Bash, Read, Agent",
            "portable": True,
        }
        frontmatter_control = {
            "name": "synthetic-readonly-analyst",
            "model": "haiku",
            "tools": "Read, Bash",
            "portable": True,
        }

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            (tmp_dir / "synthetic-readonly-phase-agent.md").write_text(
                _render_synthetic_template(
                    frontmatter_signoff_flag_only,
                    "Runs a suite and reports.",
                    include_signoff_section=False,
                ),
                encoding="utf-8",
            )
            (tmp_dir / "synthetic-readonly-body-signoff-agent.md").write_text(
                _render_synthetic_template(
                    frontmatter_body_section_only,
                    "Smokes a surface and reports.",
                    include_signoff_section=True,
                ),
                encoding="utf-8",
            )
            (tmp_dir / "synthetic-readonly-analyst.md").write_text(
                _render_synthetic_template(
                    frontmatter_control,
                    "Read-only analyst. It returns a payload; it writes nothing. "
                    "It may mention the sign-off of the agent that dispatched it.",
                    include_signoff_section=False,
                ),
                encoding="utf-8",
            )

            synthetic = load_agent_templates(tmp_dir)
            self.assertEqual(
                3,
                len(synthetic),
                "synthetic fixture did not round-trip through the loader",
            )

            violations = find_signoff_capability_violations(synthetic)

        reported = sorted(v.name for v in violations)
        self.assertEqual(
            [
                "synthetic-readonly-body-signoff-agent",
                "synthetic-readonly-phase-agent",
            ],
            reported,
            "the rule failed to report a synthetic sign-off-obligated, "
            "read-only template; it can no longer detect the defect it exists "
            f"to detect. Reported: {reported}",
        )

        report = format_violation_report(violations)
        for expected_fragment in (
            "synthetic-readonly-phase-agent",
            "synthetic-readonly-body-signoff-agent",
            "sign-off",
            "Edit",
            "Bash, Read",
        ):
            self.assertIn(
                expected_fragment,
                report,
                "failure report must name the template, the obligation and the "
                f"missing capability; missing {expected_fragment!r}",
            )

    def test_a_read_only_template_with_no_signoff_obligation_is_not_reported(self):
        # covers: AR-200a-1
        """CONTROL — the rule must not simply demand Edit on every template.

        A genuinely read-only, non-phase agent (analyst, classifier, triage)
        carries no sign-off obligation and must not be flagged. Checked both
        against a synthetic fixture and against the real registry, so the rule
        cannot be satisfied by granting Edit everywhere.
        """
        # -- synthetic half -------------------------------------------------
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            (tmp_dir / "synthetic-readonly-analyst.md").write_text(
                _render_synthetic_template(
                    {
                        "name": "synthetic-readonly-analyst",
                        "model": "sonnet",
                        "tools": "Read, Bash",
                        "portable": True,
                    },
                    "Single-perspective analyst. Returns a structured payload.\n"
                    "Does not sign off; the dispatching lead records the sign-off.",
                    include_signoff_section=False,
                ),
                encoding="utf-8",
            )
            synthetic_violations = find_signoff_capability_violations(
                load_agent_templates(tmp_dir)
            )
        self.assertEqual(
            [],
            synthetic_violations,
            "a read-only template with no sign-off obligation was reported: "
            f"{[v.name for v in synthetic_violations]}",
        )

        # -- real-registry half ---------------------------------------------
        templates = load_agent_templates(AGENT_TEMPLATE_DIR)
        read_only_unobligated = [
            t
            for t in templates
            if not t.is_signoff_obligated
            and not t.has_write_capable_tool
            and t.parse_error is None
        ]
        self.assertGreater(
            len(read_only_unobligated),
            0,
            "the registry contains no read-only, non-obligated template, so "
            "this control proves nothing — either the fixture assumption is "
            "stale or Edit has been granted indiscriminately (the failure mode "
            "AR-200a-1 explicitly forbids)",
        )

        reported_names = {v.name for v in find_signoff_capability_violations(templates)}
        wrongly_reported = sorted(
            t.name for t in read_only_unobligated if t.name in reported_names
        )
        self.assertEqual(
            [],
            wrongly_reported,
            "read-only templates with no sign-off obligation were reported as "
            f"violations: {wrongly_reported}",
        )


if __name__ == "__main__":
    unittest.main()
