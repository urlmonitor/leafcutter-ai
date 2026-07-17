"""
Tests for BP-300e-6: Agents dispatched for a machine-parsed result return only
the structured payload, with any anomaly carried inside it.

Covers:
- status-checker.md's machine-parsed dispatch path instructs "return ONLY the JSON
  object/array, no prose/headings before or after"
- No trailing '## Anomalies' markdown section instruction remains in any producer
- Anomalies/warnings carried as a field INSIDE the JSON payload
- Class-level check derived from the JS workflow files (phaseOrder, PT_ORDER, pipeline
  arrays, and literal schema/JSON.parse dispatch sites)
- Guard: any new machine-parsed dispatch whose agent template lacks the contract fails
"""
import glob
import os
import re
import unittest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Locate the repo root relative to this test file (unit_tests/ → repo root)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_AGENTS = os.path.join(REPO_ROOT, "templates", "agents")
WORKFLOWS_JS_DIR = os.path.join(REPO_ROOT, "templates", "workflows-js")

# Phrase that must appear in every machine-parsed producer template.
CONTRACT_PHRASE = "Machine-Parsed Dispatch Output Contract"

# Old instruction that must NOT appear in any producer template that has been migrated.
OLD_ANOMALIES_INSTRUCTION = "append an `## Anomalies` section"


# ---------------------------------------------------------------------------
# Helper: read files
# ---------------------------------------------------------------------------

def _read_template(agent_name: str) -> str:
    path = os.path.join(TEMPLATES_AGENTS, f"{agent_name}.md")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _read_js(filename: str) -> str:
    path = os.path.join(WORKFLOWS_JS_DIR, filename)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# Helper: extract producers from JS sources (the key derivation logic)
# ---------------------------------------------------------------------------

def _extract_phase_order() -> list:
    """
    Parse the canonical phaseOrder array from build-ticket.js.

    Every agent in phaseOrder is dispatched with PHASE_RESULT_SCHEMA (schema: param),
    making it a machine-parsed producer regardless of surrounding JSON.parse calls.
    Parsing from source ensures the test tracks the array as it evolves.
    """
    js = _read_js("build-ticket.js")
    match = re.search(r"const phaseOrder\s*=\s*\[([^\]]+)\]", js, re.DOTALL)
    if not match:
        return []
    block = match.group(1)
    return re.findall(r'"([^"]+)"', block)


def _extract_pt_order() -> list:
    """
    Parse agent names from the PT_ORDER constant in plan-feature.js.

    PT_ORDER drives the product-truth authoring phase: mock-data-author,
    mockup-author, flow-author. Each is dispatched via ptStep.agent and the
    reply is JSON.parse'd — making them always machine-parsed producers.
    """
    js = _read_js("plan-feature.js")
    match = re.search(r"const PT_ORDER\s*=\s*\[([^\]]+)\]", js, re.DOTALL)
    if not match:
        return []
    block = match.group(1)
    return re.findall(r'agent:\s*"([^"]+)"', block)


def _extract_pipeline_agents() -> set:
    """
    Parse all agent names from all pipeline = [...] assignments in plan-feature.js.

    The strategic / behavioral / technical pipeline arrays contain product-owner,
    business-analyst, and it-po. Each is dispatched via step.agent and the reply
    is JSON.parse'd — making them machine-parsed producers.
    Returning the UNION covers all route variants.
    """
    js = _read_js("plan-feature.js")
    agents: set = set()
    for block in re.findall(r"pipeline\s*=\s*\[([^\]]+)\]", js, re.DOTALL):
        agents.update(re.findall(r'agent:\s*"([^"]+)"', block))
    return agents


def _extract_literal_schema_dispatches() -> set:
    """
    Find all literal agentType dispatch sites in the workflow JS files that
    include a schema: param in the same opts object.

    schema: means the E2 engine enforces the schema and returns an already-parsed
    object — the dispatch is always machine-parsed, regardless of surrounding
    JSON.parse calls. This catches dispatches like brainstorm-lead (CLASSIFY_SCHEMA)
    and status-checker (PLANNER_SCHEMA / WORKTREE_SCHEMA / PHASE_RESULT_SCHEMA).
    """
    agents: set = set()
    for js_file in glob.glob(os.path.join(WORKFLOWS_JS_DIR, "*.js")):
        with open(js_file, encoding="utf-8") as fh:
            content = fh.read()
        # Scan each literal agentType occurrence. Look for schema: in the opts
        # object that follows the same agent() call (typically within 200 chars).
        for match in re.finditer(r'agentType:\s*"([^"]+)"', content):
            agent_name = match.group(1)
            # Check a generous forward window for schema:
            end = min(len(content), match.end() + 300)
            context = content[match.start() : end]
            if "schema:" in context:
                agents.add(agent_name)
    return agents


def _derive_all_machine_parsed_producers() -> set:
    """
    Derive the COMPLETE set of machine-parsed producer agent names by combining:

    1. All agents in phaseOrder (build-ticket.js) — dispatched with PHASE_RESULT_SCHEMA.
    2. All agents in PT_ORDER (plan-feature.js) — dispatched via ptStep.agent, JSON.parse'd.
    3. All agents in pipeline arrays (plan-feature.js) — via step.agent, JSON.parse'd.
    4. All literal agentType dispatch sites in any JS file that carry schema: in opts.
    5. Window scan: any literal agentType dispatch near a JSON.parse / safeParseJSON call
       (legacy detection for dispatch sites that do not use the schema: param).

    This multi-source derivation ensures variable agentTypes are fully resolved
    from their canonical source arrays, so the test tracks JS source changes.
    """
    producers: set = set()

    # 1. Phase agents from phaseOrder (all dispatched with PHASE_RESULT_SCHEMA)
    producers.update(_extract_phase_order())

    # 2. PT authoring agents from PT_ORDER
    producers.update(_extract_pt_order())

    # 3. AC pipeline agents from plan-feature pipeline arrays
    producers.update(_extract_pipeline_agents())

    # 4. Literal schema dispatches (catches brainstorm-lead as classifier, etc.)
    producers.update(_extract_literal_schema_dispatches())

    # 5. Window scan for JSON.parse / safeParseJSON near any literal agentType
    for js_file in glob.glob(os.path.join(WORKFLOWS_JS_DIR, "*.js")):
        with open(js_file, encoding="utf-8") as fh:
            lines = fh.readlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Skip comment lines to avoid JSDoc false positives.
            if (
                stripped.startswith("//")
                or stripped.startswith("*")
                or stripped.startswith("/*")
            ):
                continue
            match = re.search(r'agentType:\s*"([^"]+)"', line)
            if not match:
                continue
            agent_name = match.group(1)
            window_start = max(0, i - 5)
            window_end = min(len(lines), i + 20)
            window = "".join(lines[window_start:window_end])
            if "JSON.parse(" in window or "safeParseJSON(" in window:
                producers.add(agent_name)

    return producers


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestBP300e6AgentJsonOnlyContract(unittest.TestCase):
    """BP-300e-6 — machine-parsed producers return only structured payload."""

    # ------------------------------------------------------------------ #
    # Test 1: status-checker.md instructs JSON-only on machine-parsed path #
    # ------------------------------------------------------------------ #

    def test_status_checker_instructs_json_only(self):
        """
        status-checker.md's machine-parsed dispatch path must carry the contract
        and must NOT instruct appending a trailing '## Anomalies' section.
        """
        content = _read_template("status-checker")

        self.assertIn(
            CONTRACT_PHRASE,
            content,
            f"status-checker.md must contain a '## {CONTRACT_PHRASE}' section "
            f"that instructs the agent to return ONLY JSON when dispatched for a "
            f"machine-parsed result.",
        )

        self.assertNotIn(
            OLD_ANOMALIES_INSTRUCTION,
            content,
            "status-checker.md must NOT instruct appending a trailing "
            "'## Anomalies' section — the old instruction conflicts with the "
            "machine-parsed JSON-only contract (BP-300e-6). Anomalies must be "
            "carried inside the JSON payload.",
        )

    # ------------------------------------------------------------------ #
    # Test 2: status-checker.md carries anomalies inside JSON payload     #
    # ------------------------------------------------------------------ #

    def test_status_checker_carries_anomalies_inside_payload(self):
        """
        status-checker.md must document an 'anomalies' field inside the returned
        JSON payload, not as a trailing prose section.
        """
        content = _read_template("status-checker")

        self.assertIn(
            '"anomalies"',
            content,
            "status-checker.md must document an 'anomalies' field inside the "
            "JSON payload so callers can access warnings without parsing free text.",
        )

    # ------------------------------------------------------------------ #
    # Test 3: derivation sanity-check — known authoritative set is found  #
    # ------------------------------------------------------------------ #

    def test_derivation_finds_all_authoritative_producers(self):
        """
        Sanity-check that _derive_all_machine_parsed_producers() correctly finds
        all agents in the authoritative producer inventory.

        If this test fails, the derivation logic is broken (e.g. the phaseOrder
        array syntax changed, or a JS file was moved) — not a template gap.

        Authoritative inventory verified against templates/workflows-js/*.js:
        - 19 agents in phaseOrder (PHASE_RESULT_SCHEMA in build-ticket.js)
        - 3 PT_ORDER agents (ptStep.agent in plan-feature.js)
        - 3 pipeline agents (step.agent in plan-feature.js)
        - brainstorm-lead (CLASSIFY_SCHEMA in build-ticket.js)
        - ticket-supervisor (TICKET_RESULT_SCHEMA in build-epic.js)
        Total = 32 producers (some overlap between phaseOrder and others).
        """
        producers = _derive_all_machine_parsed_producers()

        # Original 8 from commit b8172a1e:
        original_8 = {
            "status-checker",
            "ac-triage",
            "pt-classifier",
            "worktree-agent",
            "commit",
            "pull-request",
            "test-runner",
            "test-failure-triage",
        }
        # 15 phase agents via phaseOrder (subset; status-checker etc. already in original_8).
        # NOTE: llm-expert is intentionally EXCLUDED here: it is not in phaseOrder in
        # build-ticket.js (no literal string in the JS), so the derivation cannot detect
        # it. The contract IS added to llm-expert.md (it CAN be dispatched as a phase
        # agent with PHASE_RESULT_SCHEMA when it appears in a ticket's agents: map), but
        # the derivation sanity-check only asserts agents reachable from JS source.
        phase_agents = {
            "adr-author",
            "architecture-diagram-author",
            "architect-review",
            "test-writer",
            "python-coder",
            "sql-coder",
            "sql-query",
            "frontend-coder",
            "change-scope-reviewer",
            "documentation-expert",
            "explanation-author",
            "how-to-author",
            "reference-author",
            "pr-reviewer",
            "user-surface-smoker",
        }
        # Schema-literal dispatches:
        schema_literal = {"brainstorm-lead", "ticket-supervisor"}
        # plan-feature.js raw JSON.parse'd agents:
        plan_feature_agents = {
            "mock-data-author",
            "mockup-author",
            "flow-author",
            "product-owner",
            "business-analyst",
            "it-po",
        }

        authoritative = (
            original_8 | phase_agents | schema_literal | plan_feature_agents
        )

        for agent_name in sorted(authoritative):
            self.assertIn(
                agent_name,
                producers,
                f"Expected '{agent_name}' in derived producer set but it was not found. "
                f"The derivation logic may be broken or the JS dispatch syntax changed. "
                f"Full derived set: {sorted(producers)}",
            )

    # ------------------------------------------------------------------ #
    # Test 4: every derived producer template carries the contract         #
    # (GUARD: fails if a new dispatch is added without updating template)  #
    # ------------------------------------------------------------------ #

    def test_all_machine_parsed_producers_carry_json_only_contract(self):
        """
        Class-level check: every agent dispatched for a machine-parsed result
        (derived from phaseOrder, PT_ORDER, pipeline arrays, schema: dispatches,
        and JSON.parse window scans in templates/workflows-js/*.js) MUST have
        a template that carries the return-only-JSON contract phrase.

        GUARD: if a new machine-parsed dispatch is added to the JS workflows
        whose agent template lacks the contract section, this test FAILS —
        ensuring future drift is caught rather than silently missed.
        """
        producers = _derive_all_machine_parsed_producers()

        missing_contract: list = []
        skipped_no_template: list = []

        for agent_name in sorted(producers):
            template_path = os.path.join(TEMPLATES_AGENTS, f"{agent_name}.md")
            if not os.path.exists(template_path):
                # No template file — skip with a note (built-in/inline helpers).
                skipped_no_template.append(agent_name)
                continue
            with open(template_path, encoding="utf-8") as fh:
                content = fh.read()
            if CONTRACT_PHRASE not in content:
                missing_contract.append(agent_name)

        self.assertEqual(
            missing_contract,
            [],
            f"The following machine-parsed producer template(s) are MISSING the "
            f"'## {CONTRACT_PHRASE}' section: {missing_contract}. "
            f"Every agent whose reply a delivery workflow JSON.parses must carry "
            f"this contract (BP-300e-6). "
            f"(Skipped — no template file: {skipped_no_template})",
        )

    # ------------------------------------------------------------------ #
    # Test 5: no producer template still instructs trailing ## Anomalies  #
    # ------------------------------------------------------------------ #

    def test_no_producer_instructs_trailing_anomalies_section(self):
        """
        Negative assertion: no machine-parsed producer template may instruct
        'append an ## Anomalies section' after its structured output. Such an
        instruction directly contradicts the JSON-only contract (BP-300e-6).

        This catches regressions where a template is edited to restore the old
        instruction after BP-300e-6 migration.
        """
        producers = _derive_all_machine_parsed_producers()

        violating: list = []
        for agent_name in sorted(producers):
            template_path = os.path.join(TEMPLATES_AGENTS, f"{agent_name}.md")
            if not os.path.exists(template_path):
                continue
            with open(template_path, encoding="utf-8") as fh:
                content = fh.read()
            if OLD_ANOMALIES_INSTRUCTION in content:
                violating.append(agent_name)

        self.assertEqual(
            violating,
            [],
            f"The following producer template(s) still instruct appending a "
            f"trailing '## Anomalies' section: {violating}. "
            f"Anomalies must be carried inside the JSON payload per BP-300e-6. "
            f"The old instruction conflicts with the machine-parsed output contract.",
        )

    # ------------------------------------------------------------------ #
    # Test 6: guard — every literal schema dispatch has the contract      #
    # ------------------------------------------------------------------ #

    def test_guard_all_literal_schema_dispatches_are_covered(self):
        """
        Guard test: every literal agentType dispatch site in the workflow JS files
        that uses a schema: constraint MUST have a template with the contract phrase.

        This is the primary future-drift guard: if a new agent is wired into a
        workflow with schema: (making it always machine-parsed) without updating
        its template, this test fails immediately — before the undocumented
        behaviour has a chance to cause a parse error at runtime.
        """
        literal_schema_agents = _extract_literal_schema_dispatches()

        missing: list = []
        for agent_name in sorted(literal_schema_agents):
            template_path = os.path.join(TEMPLATES_AGENTS, f"{agent_name}.md")
            if not os.path.exists(template_path):
                continue  # No template — built-in helper; skip.
            with open(template_path, encoding="utf-8") as fh:
                content = fh.read()
            if CONTRACT_PHRASE not in content:
                missing.append(agent_name)

        self.assertEqual(
            missing,
            [],
            f"New schema-dispatch agent(s) found in workflow JS files without the "
            f"machine-parsed contract in their templates: {missing}. "
            f"Add a '## {CONTRACT_PHRASE}' section to each listed template. "
            f"All literal schema-dispatch agents found: {sorted(literal_schema_agents)}",
        )

    # ------------------------------------------------------------------ #
    # Test 7: guard — phaseOrder array is self-consistent                 #
    # (fails if build-ticket.js phaseOrder changes but test logic is old)  #
    # ------------------------------------------------------------------ #

    def test_guard_phase_order_extraction_is_parseable(self):
        """
        Guard: _extract_phase_order() must return a non-empty list.

        If this fails, the phaseOrder constant in build-ticket.js changed
        syntax in a way that broke the regex — update _extract_phase_order().
        """
        phase_order = _extract_phase_order()
        self.assertGreater(
            len(phase_order),
            10,
            f"_extract_phase_order() returned only {len(phase_order)} entries "
            f"(expected > 10). The phaseOrder array in build-ticket.js may have "
            f"changed syntax. Update _extract_phase_order() to match. "
            f"Parsed: {phase_order}",
        )

    def test_guard_pt_order_extraction_is_parseable(self):
        """
        Guard: _extract_pt_order() must return at least the 3 known PT agents.

        If this fails, the PT_ORDER constant in plan-feature.js changed
        syntax — update _extract_pt_order().
        """
        pt_order = _extract_pt_order()
        expected_pt = {"mock-data-author", "mockup-author", "flow-author"}
        for agent_name in expected_pt:
            self.assertIn(
                agent_name,
                pt_order,
                f"Expected '{agent_name}' in PT_ORDER from plan-feature.js. "
                f"Parsed PT_ORDER: {pt_order}. "
                f"The PT_ORDER constant syntax may have changed — update "
                f"_extract_pt_order().",
            )

    def test_guard_pipeline_agents_extraction_is_parseable(self):
        """
        Guard: _extract_pipeline_agents() must return the 3 known AC pipeline agents.

        If this fails, the pipeline array syntax in plan-feature.js changed —
        update _extract_pipeline_agents().
        """
        pipeline_agents = _extract_pipeline_agents()
        expected_pipeline = {"product-owner", "business-analyst", "it-po"}
        for agent_name in expected_pipeline:
            self.assertIn(
                agent_name,
                pipeline_agents,
                f"Expected '{agent_name}' in pipeline arrays from plan-feature.js. "
                f"Parsed pipeline agents: {sorted(pipeline_agents)}. "
                f"The pipeline array syntax may have changed — update "
                f"_extract_pipeline_agents().",
            )


if __name__ == "__main__":
    unittest.main()
