"""
Tests for BP-300e-6: Agents dispatched for a machine-parsed result return only
the structured payload, with any anomaly carried inside it.

Covers:
- status-checker.md's machine-parsed dispatch path instructs "return ONLY the JSON
  object/array, no prose/headings before or after"
- No trailing '## Anomalies' markdown section remains in its output contract
- Anomalies/warnings carried as a field INSIDE the JSON payload
- Class-level check: every machine-parsed producer template carries the contract
  (derived dynamically from JSON.parse dispatch sites in templates/workflows-js/*.js)
"""
import glob
import os
import re
import unittest

# Locate the repo root relative to this test file (unit_tests/ → repo root)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_AGENTS = os.path.join(REPO_ROOT, "templates", "agents")
WORKFLOWS_JS_DIR = os.path.join(REPO_ROOT, "templates", "workflows-js")

# Phrase that must appear in every machine-parsed producer template.
# Added by this ticket to each of the four producer templates.
CONTRACT_PHRASE = "Machine-Parsed Dispatch Output Contract"

# Old instruction that must NOT appear in templates that have been migrated:
# status-checker previously instructed "append an `## Anomalies` section"
OLD_ANOMALIES_INSTRUCTION = "append an `## Anomalies` section"


def _read_template(agent_name: str) -> str:
    path = os.path.join(TEMPLATES_AGENTS, f"{agent_name}.md")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _derive_machine_parsed_producers() -> set:
    """
    Derive the set of agent types that are dispatched for machine-parsed results
    by scanning templates/workflows-js/*.js for agentType dispatch sites that are
    followed by JSON.parse() or safeParseJSON() within a close window.

    This is intentionally data-driven — not a hard-coded list — so newly added
    producers automatically inherit the contract check.
    """
    js_files = glob.glob(os.path.join(WORKFLOWS_JS_DIR, "*.js"))
    producers: set = set()

    for js_file in js_files:
        with open(js_file, encoding="utf-8") as fh:
            lines = fh.readlines()

        for i, line in enumerate(lines):
            # Skip comment lines to avoid false positives from JSDoc and inline
            # comments that mention agentType as documentation, not dispatch code.
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*") or stripped.startswith("/*"):
                continue

            match = re.search(r'agentType:\s*"([^"]+)"', line)
            if not match:
                continue
            agent_name = match.group(1)

            # Look in a window of ±15 lines around the dispatch site for a
            # JSON parsing call.  The window is asymmetric: parse calls appear
            # either on the same line or in the lines immediately following the
            # agent() call that closes the dispatch block.
            window_start = max(0, i - 5)
            window_end = min(len(lines), i + 20)
            window = "".join(lines[window_start:window_end])

            if "JSON.parse(" in window or "safeParseJSON(" in window:
                producers.add(agent_name)

    return producers


class TestBP300e6AgentJsonOnlyContract(unittest.TestCase):
    """BP-300e-6 — machine-parsed producers return only structured payload."""

    # ------------------------------------------------------------------ #
    # Test 1: status-checker.md instructs JSON-only on machine-parsed path #
    # ------------------------------------------------------------------ #

    def test_status_checker_instructs_json_only(self):
        """
        status-checker.md's machine-parsed dispatch path must instruct
        'return ONLY the JSON object/array, no prose/headings before or after';
        no trailing '## Anomalies' markdown section instruction may remain.
        """
        content = _read_template("status-checker")

        self.assertIn(
            CONTRACT_PHRASE,
            content,
            f"status-checker.md must contain a '## {CONTRACT_PHRASE}' section "
            f"that instructs agents to return ONLY JSON when dispatched for a "
            f"machine-parsed result.",
        )

        self.assertNotIn(
            OLD_ANOMALIES_INSTRUCTION,
            content,
            "status-checker.md must NOT instruct appending a trailing "
            "'## Anomalies' section — the old instruction conflicts with the "
            "machine-parsed JSON-only contract (BP-300e-6).",
        )

    # ------------------------------------------------------------------ #
    # Test 2: status-checker.md carries anomalies inside JSON payload     #
    # ------------------------------------------------------------------ #

    def test_status_checker_carries_anomalies_inside_payload(self):
        """
        status-checker.md must document anomalies/warnings as a field INSIDE
        the returned JSON payload (e.g. an 'anomalies' array) rather than as
        a trailing prose section appended after the structured output.
        """
        content = _read_template("status-checker")

        self.assertIn(
            '"anomalies"',
            content,
            "status-checker.md must document an 'anomalies' field inside the "
            "JSON payload so callers can access warnings without parsing free text.",
        )

    # ------------------------------------------------------------------ #
    # Test 3: all machine-parsed producers carry the JSON-only contract   #
    # ------------------------------------------------------------------ #

    def test_all_machine_parsed_producers_carry_json_only_contract(self):
        """
        Class-level check: every agent type that is dispatched for a machine-parsed
        result (derived from JSON.parse / safeParseJSON dispatch sites in
        templates/workflows-js/*.js) must have a template that carries the
        return-only-JSON contract phrase.

        Known producers at authoring time: status-checker, ac-triage, pt-classifier,
        worktree-agent.  The test is data-driven — if a new producer is wired in
        the JS workflows without its template being updated, this test will catch it.
        """
        producers = _derive_machine_parsed_producers()

        # Sanity-check that the scanner found the known set
        known_producers = {"status-checker", "ac-triage", "pt-classifier", "worktree-agent"}
        for agent_name in known_producers:
            self.assertIn(
                agent_name,
                producers,
                f"Expected '{agent_name}' in machine-parsed producer set derived "
                f"from workflow JS files, but it was not found. "
                f"Full derived set: {sorted(producers)}",
            )

        # Verify each producer template carries the contract
        missing_contract: list = []
        for agent_name in sorted(producers):
            template_path = os.path.join(TEMPLATES_AGENTS, f"{agent_name}.md")
            if not os.path.exists(template_path):
                # Skip agents that have no template file (e.g. built-in helpers)
                continue
            with open(template_path, encoding="utf-8") as fh:
                content = fh.read()
            if CONTRACT_PHRASE not in content:
                missing_contract.append(agent_name)

        self.assertEqual(
            missing_contract,
            [],
            f"The following machine-parsed producer template(s) are missing the "
            f"'## {CONTRACT_PHRASE}' section: {missing_contract}. "
            f"Every agent whose reply a delivery workflow JSON.parses must carry "
            f"this contract (BP-300e-6).",
        )


if __name__ == "__main__":
    unittest.main()
