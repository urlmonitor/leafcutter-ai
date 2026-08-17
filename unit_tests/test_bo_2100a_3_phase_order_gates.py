"""
MODULE: test_bo_2100a_3_phase_order_gates
GOAL: Prove — by EXECUTING the real dispatcher code, not by grepping it — that
      every registered ticket-phase agent is a member of the `phaseOrder`
      array in BOTH workflow twins, and that the pre-commit quality gates
      (`ac-validator` 11.5, `ac-fulfillment-gate` 11.7, `live-surface-tester`
      11.8) actually sort BEFORE `commit` (12) and `pull-request` (13).

WHY BEHAVIORAL, NOT STRUCTURAL
------------------------------
`getPriority()` returns `phaseOrder.length` for any agent absent from the
array. Three *registered* phase agents were missing, so all three resolved to
the same sentinel and sorted AFTER commit and pull-request: every ticket's AC
coverage gate and AC fulfillment gate ran once the commit and PR had already
happened, so a failing gate could not block anything and its sign-off landed
off the PR.

A test that only greps for the agent name in the file would have passed the
moment the string was added, even if `getPriority` still ignored it. These
tests therefore extract the REAL `phaseOrder` / `getPriority` /
`sortByCanonicalPriority` declarations from the real workflow files and run
them in Node.js, asserting on the *computed* sort output and on the *observed*
stderr of the fallback path.

HOW THE JS IS EXECUTED
----------------------
Both workflow scripts are E2 "top-level body" ESM modules: importing them
would immediately execute `agent(...)` / `phase(...)` calls against globals
that only the workflow engine provides. So the tests slice out the single
contiguous, side-effect-free region that runs from `const phaseOrder = [`
through the closing brace of `function sortByCanonicalPriority`, append a
driver, and pipe the result to `node --input-type=module`. That region is the
production source verbatim — nothing is re-implemented in the test.

Node is required. If `node` is absent the tests ERROR loudly; they never skip,
because a silent skip is the same class of invisible failure this module exists
to catch.

REGISTRY IS THE SOURCE OF TRUTH
-------------------------------
Expected ordering is derived from `config/agent_registry.json`
(`is_ticket_phase: true` + `priority`), never hardcoded to a summary.

Known, PRE-EXISTING deviation (not introduced or fixed here): `llm-expert` is
declared priority 6 in the registry but sits at array index 9, after
`frontend-coder` (priority 8). It is listed in `_KNOWN_PRIORITY_DEVIATIONS` so
the monotonicity guard stays meaningful for every other agent while a NEW
deviation still fails the suite.

COVERS
------
BO-2100a-3   — live-surface-tester is a member of build-ticket.js phaseOrder,
               after user-surface-smoker and before commit.
BO-2100a-3-i — relative index ordering 11.5 < 11.8 < 12 holds and no
               pre-existing entry's relative order changed.
BO-2100a-4   — building-epics SKILL.md documents live-surface-tester at 11.8
               in BOTH the prose and the priority table.
UNKNOWN      — everything else here is authorised extended scope with no AC
               backing it yet: ac-validator (11.5) and ac-fulfillment-gate
               (11.7) insertion, the build-feature.js twin, the general
               registry->phaseOrder membership invariant, and the loud
               getPriority fallback.
"""

from __future__ import annotations

import json
import re
import subprocess
import unittest
from functools import lru_cache
from pathlib import Path

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent

_BUILD_TICKET_JS = _REPO_ROOT / "templates" / "workflows-js" / "build-ticket.js"
_BUILD_FEATURE_JS = _REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"
_BUILDING_EPICS_SKILL = (
    _REPO_ROOT / "templates" / "skills" / "building-epics" / "SKILL.md"
)
_AGENT_REGISTRY = _REPO_ROOT / "config" / "agent_registry.json"

_TWINS = (("build-ticket.js", _BUILD_TICKET_JS), ("build-feature.js", _BUILD_FEATURE_JS))

# The three gates that were silently sorting after commit/pull-request.
_GATE_AGENTS = ("ac-validator", "ac-fulfillment-gate", "live-surface-tester")

# Registry-declared priority is authoritative; llm-expert's array slot predates
# this work and is deliberately left untouched (see module docstring).
_KNOWN_PRIORITY_DEVIATIONS = frozenset({"llm-expert"})

# The exact phaseOrder contents BEFORE the three gates were inserted. Used to
# assert the insertion did not reorder anything that was already there
# (BO-2100a-3-i: "no pre-existing entry's relative order is changed").
_PRE_EXISTING_ORDER = (
    "status-checker",
    "adr-author",
    "architecture-diagram-author",
    "architect-review",
    "test-writer",
    "python-coder",
    "sql-coder",
    "sql-query",
    "frontend-coder",
    "llm-expert",
    "test-runner",
    "change-scope-reviewer",
    "documentation-expert",
    "explanation-author",
    "how-to-author",
    "reference-author",
    "pr-reviewer",
    "user-surface-smoker",
    "documentation-verifier",
    "commit",
    "pull-request",
)

_UNKNOWN_AGENT = "totally-unregistered-agent-xyz"


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------


def _load_registry_phase_agents() -> dict[str, float]:
    """Return {agent_id: priority} for every registry agent with is_ticket_phase: true."""
    try:
        raw = _AGENT_REGISTRY.read_text(encoding="utf-8")
    except OSError as exc:
        raise OSError(f"Cannot read {_AGENT_REGISTRY}: {exc}") from exc  # noqa: TRY003

    data = json.loads(raw)
    agents = data["agents"]
    result: dict[str, float] = {}
    for entry in agents:
        if entry.get("is_ticket_phase") is True:
            result[entry["id"]] = float(entry["priority"])
    assert result, "No is_ticket_phase agents found in agent_registry.json"
    return result


# ---------------------------------------------------------------------------
# JS extraction + execution helpers
# ---------------------------------------------------------------------------


def _extract_ordering_region(js_path: Path) -> str:
    """Slice the real, side-effect-free phase-ordering region out of a workflow file.

    Runs from ``const phaseOrder = [`` through the closing brace of
    ``function sortByCanonicalPriority``. Everything in between (the array, any
    module-level helper state, and ``getPriority``) is production source used
    verbatim — the test never re-implements it.
    """
    try:
        source = js_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise OSError(f"Cannot read {js_path}: {exc}") from exc  # noqa: TRY003

    start = source.find("const phaseOrder = [")
    assert start != -1, f"'const phaseOrder = [' not found in {js_path.name}"

    fn_start = source.find("function sortByCanonicalPriority(", start)
    assert fn_start != -1, (
        f"'function sortByCanonicalPriority(' not found after phaseOrder in {js_path.name}"
    )

    depth = 0
    opened = False
    for i in range(fn_start, len(source)):
        char = source[i]
        if char == "{":
            depth += 1
            opened = True
        elif char == "}" and opened:
            depth -= 1
            if depth == 0:
                return source[start : i + 1]

    raise AssertionError(  # noqa: TRY003
        f"sortByCanonicalPriority closing brace not found in {js_path.name}"
    )


def _run_node(region_js: str, driver_js: str) -> tuple[dict, str]:
    """Execute the extracted region + a driver in Node; return (stdout JSON, stderr text)."""
    script = f"{region_js}\n{driver_js}\n"
    try:
        proc = subprocess.run(
            ["node", "--input-type=module"],
            input=script,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(  # noqa: TRY003
            "node binary not found — Node.js is required to execute the real "
            "phaseOrder/getPriority code. These tests must not be skipped."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Node.js subprocess timed out after 20s") from exc  # noqa: TRY003

    assert proc.returncode == 0, (
        f"Node exited {proc.returncode}. stderr: {proc.stderr!r}"
    )
    try:
        return json.loads(proc.stdout), proc.stderr
    except json.JSONDecodeError as exc:
        raise ValueError(  # noqa: TRY003
            f"Cannot parse node stdout as JSON: {exc}. stdout={proc.stdout!r}"
        ) from exc


@lru_cache(maxsize=None)
def _probe_cached(js_path: Path, agents: tuple[str, ...]) -> str:
    """Node-subprocess-backed probe, memoized (each call spawns a node process)."""
    shuffled = [{"agent": name, "status": "needed"} for name in reversed(agents)]
    driver = (
        f"const AGENTS = {json.dumps(list(agents))};\n"
        f"const SHUFFLED = {json.dumps(shuffled)};\n"
        "const priorities = {};\n"
        "for (const a of AGENTS) { priorities[a] = getPriority(a); }\n"
        "const out = {\n"
        "  phase_order: phaseOrder,\n"
        "  phase_order_length: phaseOrder.length,\n"
        "  priorities: priorities,\n"
        "  sorted_agents: sortByCanonicalPriority(SHUFFLED).map((p) => p.agent),\n"
        "};\n"
        "process.stdout.write(JSON.stringify(out));\n"
    )
    result, _stderr = _run_node(_extract_ordering_region(js_path), driver)
    return json.dumps(result)


def _probe(js_path: Path, agents: list[str]) -> dict:
    """Run the REAL getPriority / sortByCanonicalPriority over ``agents``.

    ``agents`` is fed to the sorter in REVERSE canonical order so a passing
    result can only come from the comparator actually working.
    """
    return json.loads(_probe_cached(js_path, tuple(agents)))


# ---------------------------------------------------------------------------
# 1 + 4. Membership — the three gates, and the general registry invariant
# ---------------------------------------------------------------------------


class TestPhaseAgentMembership(unittest.TestCase):
    """Every registered ticket phase must be a member of both phaseOrder arrays."""

    def test_live_surface_tester_is_member_of_build_ticket_phase_order(self):
        # covers: BO-2100a-3
        """live-surface-tester resolves to a real index, not the sorts-last sentinel."""
        result = _probe(_BUILD_TICKET_JS, ["live-surface-tester"])
        self.assertIn(
            "live-surface-tester",
            result["phase_order"],
            "live-surface-tester is absent from build-ticket.js phaseOrder; "
            f"array is {result['phase_order']}",
        )
        self.assertNotEqual(
            result["priorities"]["live-surface-tester"],
            result["phase_order_length"],
            "getPriority('live-surface-tester') returned the fallback sentinel "
            f"({result['phase_order_length']}) — the agent is not really registered "
            "in the array, so it would sort after commit and pull-request.",
        )

    def test_ac_gates_are_members_of_both_phase_orders(self):
        # covers: UNKNOWN
        """ac-validator and ac-fulfillment-gate resolve to real indices in BOTH twins.

        Extended scope: no AC covers the ac-validator / ac-fulfillment-gate
        insertion or the build-feature.js twin.
        """
        for label, path in _TWINS:
            with self.subTest(source=label):
                result = _probe(path, list(_GATE_AGENTS))
                for agent in _GATE_AGENTS:
                    self.assertIn(
                        agent,
                        result["phase_order"],
                        f"[{label}] {agent} absent from phaseOrder: {result['phase_order']}",
                    )
                    self.assertNotEqual(
                        result["priorities"][agent],
                        result["phase_order_length"],
                        f"[{label}] getPriority({agent!r}) returned the sorts-last "
                        f"sentinel {result['phase_order_length']} — it would run "
                        "after commit and pull-request.",
                    )

    def test_every_registry_ticket_phase_is_in_both_phase_orders(self):
        # covers: UNKNOWN
        """GENERAL INVARIANT — the assertion that stops the next silent omission.

        Generalised from BO-2200b-6 (which pinned only documentation-verifier):
        every agent in config/agent_registry.json with is_ticket_phase: true
        must be a member of BOTH phaseOrder arrays. An agent that is
        dispatchable as a ticket phase but missing here silently sorts last,
        i.e. after commit (12) and pull-request (13).

        Extended scope: no AC covers this generalisation.
        """
        registry = _load_registry_phase_agents()
        for label, path in _TWINS:
            with self.subTest(source=label):
                result = _probe(path, sorted(registry))
                missing = [
                    agent
                    for agent in sorted(registry)
                    if result["priorities"][agent] == result["phase_order_length"]
                ]
                wanted = {a: registry[a] for a in missing}
                self.assertEqual(
                    [],
                    missing,
                    f"[{label}] registered ticket-phase agents missing from "
                    f"phaseOrder (each silently sorts after commit and "
                    f"pull-request): {missing}. Add each at its "
                    f"registry-declared priority: {wanted}",
                )


# ---------------------------------------------------------------------------
# 2. Computed ordering relative to the anchors
# ---------------------------------------------------------------------------


class TestComputedGateOrdering(unittest.TestCase):
    """The REAL sort must place the gates before commit and pull-request."""

    def test_live_surface_tester_sorts_after_smoker_and_before_commit(self):
        # covers: BO-2100a-3
        # covers: BO-2100a-3-i
        """Index ordering user-surface-smoker < live-surface-tester < commit, computed.

        Assertions are relative index comparisons (per BO-2100a-3-i
        it_requirements), never tied to the absolute 11.8 literal.
        """
        agents = [
            "user-surface-smoker",
            "live-surface-tester",
            "documentation-verifier",
            "commit",
            "pull-request",
        ]
        result = _probe(_BUILD_TICKET_JS, agents)
        order = result["sorted_agents"]
        self.assertEqual(
            [
                "user-surface-smoker",
                "live-surface-tester",
                "documentation-verifier",
                "commit",
                "pull-request",
            ],
            order,
            "build-ticket.js sortByCanonicalPriority produced the wrong dispatch "
            f"order for the live-app gate block: {order}",
        )
        prio = result["priorities"]
        self.assertLess(prio["user-surface-smoker"], prio["live-surface-tester"])
        self.assertLess(prio["live-surface-tester"], prio["commit"])
        self.assertLess(prio["live-surface-tester"], prio["pull-request"])

    def test_all_three_gates_sort_before_commit_and_pr_in_both_twins(self):
        # covers: UNKNOWN
        """ac-validator / ac-fulfillment-gate / live-surface-tester all precede commit.

        Extended scope for the two ac-* gates and for build-feature.js.
        """
        agents = [*_GATE_AGENTS, "pr-reviewer", "user-surface-smoker", "commit", "pull-request"]
        for label, path in _TWINS:
            with self.subTest(source=label):
                prio = _probe(path, agents)["priorities"]
                for gate in _GATE_AGENTS:
                    self.assertLess(
                        prio[gate],
                        prio["commit"],
                        f"[{label}] {gate} (idx {prio[gate]}) must sort BEFORE commit "
                        f"(idx {prio['commit']}) — otherwise the gate runs after the "
                        "commit it is supposed to block.",
                    )
                    self.assertLess(
                        prio[gate],
                        prio["pull-request"],
                        f"[{label}] {gate} (idx {prio[gate]}) must sort BEFORE "
                        f"pull-request (idx {prio['pull-request']}) — otherwise its "
                        "sign-off lands off the PR.",
                    )
                    self.assertGreater(
                        prio[gate],
                        prio["pr-reviewer"],
                        f"[{label}] {gate} must sort AFTER pr-reviewer.",
                    )

    def test_gate_block_matches_registry_priority_sequence_in_both_twins(self):
        # covers: UNKNOWN
        """The computed post-review sequence equals the registry-priority sequence.

        Derived from agent_registry.json rather than from a hardcoded list, so
        the registry stays the source of truth. ac-validator and
        user-surface-smoker are both priority 11.5 (a genuine tie), so their
        mutual order is not asserted — only their position relative to the
        non-tied neighbours.
        """
        registry = _load_registry_phase_agents()
        block = sorted(
            (p, a) for a, p in registry.items() if p >= 11 and a not in _KNOWN_PRIORITY_DEVIATIONS
        )
        agents = [a for _p, a in block]
        for label, path in _TWINS:
            with self.subTest(source=label):
                prio = _probe(path, agents)["priorities"]
                for (prio_a, agent_a), (prio_b, agent_b) in zip(block, block[1:]):
                    if prio_a == prio_b:
                        continue  # genuine tie — mutual order is unconstrained
                    self.assertLess(
                        prio[agent_a],
                        prio[agent_b],
                        f"[{label}] registry says {agent_a} ({prio_a}) runs before "
                        f"{agent_b} ({prio_b}), but phaseOrder puts {agent_a} at index "
                        f"{prio[agent_a]} and {agent_b} at index {prio[agent_b]}.",
                    )

    def test_full_registry_sort_is_monotonic_in_registry_priority(self):
        # covers: UNKNOWN
        """Sorting ALL registry phase agents reproduces non-decreasing registry priority.

        One known pre-existing deviation is excluded by name
        (_KNOWN_PRIORITY_DEVIATIONS = llm-expert, registry priority 6 but array
        index 9); any NEW deviation fails here.
        """
        registry = _load_registry_phase_agents()
        agents = sorted(a for a in registry if a not in _KNOWN_PRIORITY_DEVIATIONS)
        for label, path in _TWINS:
            with self.subTest(source=label):
                sorted_agents = _probe(path, agents)["sorted_agents"]
                sorted_agents = [a for a in sorted_agents if a in set(agents)]
                priorities = [registry[a] for a in sorted_agents]
                self.assertEqual(
                    sorted(priorities),
                    priorities,
                    f"[{label}] the real sort produced an order whose registry "
                    f"priorities are not non-decreasing: "
                    f"{list(zip(sorted_agents, priorities))}",
                )


# ---------------------------------------------------------------------------
# 3. No pre-existing entry's relative order changed
# ---------------------------------------------------------------------------


class TestPreExistingOrderPreserved(unittest.TestCase):
    """BO-2100a-3-i: the insertion must not move anything that was already there."""

    def test_pre_existing_entries_keep_their_relative_order_in_both_twins(self):
        # covers: BO-2100a-3-i
        """The 21 pre-insertion entries still appear as an ordered subsequence."""
        for label, path in _TWINS:
            with self.subTest(source=label):
                order = _probe(path, ["commit"])["phase_order"]
                observed = [a for a in order if a in set(_PRE_EXISTING_ORDER)]
                self.assertEqual(
                    list(_PRE_EXISTING_ORDER),
                    observed,
                    f"[{label}] the relative order of pre-existing phaseOrder entries "
                    f"changed.\n  expected subsequence: {list(_PRE_EXISTING_ORDER)}\n"
                    f"  observed subsequence: {observed}",
                )

    def test_no_pre_existing_entry_was_dropped_in_both_twins(self):
        # covers: BO-2100a-3-i
        """Every pre-insertion entry is still a member (nothing removed to make room)."""
        for label, path in _TWINS:
            with self.subTest(source=label):
                result = _probe(path, list(_PRE_EXISTING_ORDER))
                dropped = [
                    a
                    for a in _PRE_EXISTING_ORDER
                    if result["priorities"][a] == result["phase_order_length"]
                ]
                self.assertEqual(
                    [], dropped, f"[{label}] pre-existing entries lost from phaseOrder: {dropped}"
                )

    def test_the_two_twins_declare_identical_phase_orders(self):
        # covers: UNKNOWN
        """build-ticket.js and build-feature.js phaseOrder arrays stay byte-parity twins.

        Extended scope: the twin-parity requirement has no AC of its own; the
        files themselves declare "TWIN: mirrors build-ticket.js phaseOrder.
        Keep in sync."
        """
        ticket_order = _probe(_BUILD_TICKET_JS, ["commit"])["phase_order"]
        feature_order = _probe(_BUILD_FEATURE_JS, ["commit"])["phase_order"]
        self.assertEqual(
            ticket_order,
            feature_order,
            "The twin phaseOrder arrays have diverged.\n"
            f"  build-ticket.js:  {ticket_order}\n"
            f"  build-feature.js: {feature_order}",
        )


# ---------------------------------------------------------------------------
# 5. The getPriority fallback must be loud, not silent
# ---------------------------------------------------------------------------


class TestGetPriorityFallbackIsLoud(unittest.TestCase):
    """An unknown agent still sorts last, but the omission is reported on stderr.

    Design decision (extended scope, no AC): the fallback LOGS rather than
    THROWS. getPriority is only ever reached from inside the
    sortByCanonicalPriority comparator, which is called once per drive on
    planner output; a throw there would propagate out of Array.prototype.sort
    with no try/catch anywhere on the path and kill an entire ticket or epic
    drive over a merely-unregistered project-local agent. Logging keeps the
    deterministic sorts-last behaviour while making the omission impossible to
    miss.
    """

    def _run_unknown(self, js_path: Path) -> tuple[dict, str]:
        driver = (
            f"const first = getPriority({_UNKNOWN_AGENT!r});\n"
            f"const second = getPriority({_UNKNOWN_AGENT!r});\n"
            "process.stdout.write(JSON.stringify({\n"
            "  first: first, second: second, phase_order_length: phaseOrder.length,\n"
            "}));\n"
        )
        return _run_node(_extract_ordering_region(js_path), driver)

    def test_unknown_agent_does_not_throw_and_still_sorts_last(self):
        # covers: UNKNOWN
        """The chosen fallback keeps returning the sorts-last sentinel."""
        for label, path in _TWINS:
            with self.subTest(source=label):
                result, _stderr = self._run_unknown(path)
                self.assertEqual(
                    result["phase_order_length"],
                    result["first"],
                    f"[{label}] unknown agent must still resolve to the sorts-last "
                    "sentinel so the drive stays deterministic.",
                )

    def test_unknown_agent_is_reported_on_stderr_naming_agent_and_file(self):
        # covers: UNKNOWN
        """The silent fallback is what made the defect invisible — it must be loud."""
        for label, path in _TWINS:
            with self.subTest(source=label):
                _result, stderr = self._run_unknown(path)
                self.assertIn(
                    _UNKNOWN_AGENT,
                    stderr,
                    f"[{label}] getPriority fell back silently for an unknown agent. "
                    "stderr must name the offending agent. "
                    f"Captured stderr: {stderr!r}",
                )
                self.assertIn(
                    label,
                    stderr,
                    f"[{label}] the diagnostic must name the file whose phaseOrder is "
                    f"incomplete. Captured stderr: {stderr!r}",
                )

    def test_unknown_agent_diagnostic_is_emitted_once_per_agent(self):
        # covers: UNKNOWN
        """Deduped so an O(n log n) comparator cannot flood the drive log."""
        for label, path in _TWINS:
            with self.subTest(source=label):
                _result, stderr = self._run_unknown(path)
                self.assertEqual(
                    1,
                    stderr.count("PHASE-ORDER GAP"),
                    f"[{label}] expected exactly one diagnostic for two getPriority "
                    f"calls on the same unknown agent. stderr: {stderr!r}",
                )


# ---------------------------------------------------------------------------
# building-epics SKILL.md documentation surfaces (BO-2100a-4)
# ---------------------------------------------------------------------------


def _parse_building_epics_table() -> list[tuple[str, str]]:
    """Return [(priority, agent)] rows from the §2.1.1 Canonical Phase Ordering Table."""
    content = _BUILDING_EPICS_SKILL.read_text(encoding="utf-8")
    rows: list[tuple[str, str]] = []
    in_section = False
    for line in content.splitlines():
        if "§2.1.1 Canonical Phase Ordering Table" in line:
            in_section = True
            continue
        if in_section:
            if re.match(r"^#{2,}", line):
                break
            match = re.search(r"\|\s*([\d.]+)\s*\|\s*`([^`]+)`", line)
            if match:
                rows.append((match.group(1), match.group(2)))
    return rows


class TestBuildingEpicsSkillDocumentsTheGates(unittest.TestCase):
    """BO-2100a-4: both the prose and the priority table must document 11.8."""

    def test_priority_table_lists_live_surface_tester_at_11_8(self):
        # covers: BO-2100a-4
        rows = _parse_building_epics_table()
        table = dict((agent, prio) for prio, agent in rows)
        self.assertIn(
            "live-surface-tester",
            table,
            f"live-surface-tester missing from the §2.1.1 table. Rows: {rows}",
        )
        self.assertEqual("11.8", table["live-surface-tester"])

    def test_priority_table_places_it_after_the_smoker_and_before_commit(self):
        # covers: BO-2100a-4
        agents = [agent for _prio, agent in _parse_building_epics_table()]
        for name in ("user-surface-smoker", "live-surface-tester", "commit"):
            self.assertIn(name, agents, f"{name} missing from §2.1.1 table: {agents}")
        self.assertLess(agents.index("user-surface-smoker"), agents.index("live-surface-tester"))
        self.assertLess(agents.index("live-surface-tester"), agents.index("commit"))

    def test_natural_language_dispatch_prose_names_live_surface_tester(self):
        # covers: BO-2100a-4
        """BO-2100a-4 it_requirements: prose AND table, so the doc cannot drift internally."""
        content = _BUILDING_EPICS_SKILL.read_text(encoding="utf-8")
        match = re.search(
            r"ties broken\s*\n\s*by canonical phase ordering(.*?)\n\s*\n",
            content,
            re.DOTALL,
        )
        self.assertIsNotNone(
            match,
            "Could not locate the canonical-phase-ordering prose block in "
            "building-epics/SKILL.md",
        )
        prose = match.group(1)
        self.assertIn(
            "live-surface-tester",
            prose,
            f"live-surface-tester missing from the dispatch-order prose: {prose!r}",
        )
        self.assertIn("11.8", prose)

    def test_skill_table_and_both_phase_order_arrays_agree_on_the_gate_block(self):
        # covers: UNKNOWN
        """Cross-source parity: the SKILL.md table order matches the executed sort.

        Extended scope — ac-validator / ac-fulfillment-gate cross-source parity
        has no AC of its own. ``_KNOWN_PRIORITY_DEVIATIONS`` (llm-expert) is
        excluded: the SKILL.md table lists it at 6 while the arrays place it at
        index 9, a pre-existing disagreement outside this change's scope.
        """
        table_agents = [
            agent
            for _prio, agent in _parse_building_epics_table()
            if agent not in _KNOWN_PRIORITY_DEVIATIONS
        ]
        for label, path in _TWINS:
            with self.subTest(source=label):
                array_order = [
                    a
                    for a in _probe(path, ["commit"])["phase_order"]
                    if a not in _KNOWN_PRIORITY_DEVIATIONS
                ]
                shared = [a for a in array_order if a in set(table_agents)]
                table_shared = [a for a in table_agents if a in set(array_order)]
                self.assertEqual(
                    table_shared,
                    shared,
                    f"[{label}] the building-epics §2.1.1 table and the phaseOrder "
                    f"array disagree on ordering.\n  table:  {table_shared}\n"
                    f"  array:  {shared}",
                )


if __name__ == "__main__":
    unittest.main()
