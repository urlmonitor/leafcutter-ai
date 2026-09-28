"""
MODULE: unit_tests/ac_store/test_tkt_500f_5_i_registry_fallback.py
GOAL: Lock the two-location registry probe in ``_gtfa_phase_agent`` —
      ``<root>/config/agent_registry.json`` first, then
      ``<root>/.leafcutter/config/agent_registry.json`` — so the phase-agent
      eligibility check keeps WORKING in the layout a consumer install actually
      has, not only in the package source tree.
COVERS: TKT-500f-5-i

BUSINESS CONTEXT: this file exists because of a real, shipped no-op. The first
version of ``_registry_candidates`` resolved one location only — the
worktree-relative ``<root>/config/`` convention its neighbour
``_gtfa_agents_inputs._resolve_config_path`` uses. A consumer install keeps the
package's config at ``<root>/.leafcutter/config/``, so on every consumer install
the registry read found nothing, ``_load_registry_entries`` took its documented
degrade-and-warn path ("the ticket-phase eligibility check is skipped"), and the
AC's ineligible ``assigned_agent`` was emitted verbatim. The whole substitution
feature was dead everywhere it ships. Every source-tree test stayed green
throughout, because in the source tree the first candidate hits.

That is TKT-500f-5-i's third it_requirement — the unknown/unreadable-registry
path — reached by the layout rather than by a corrupt file: an unreadable
registry must degrade loudly, but a registry that is merely *somewhere else*
must be FOUND, not degraded to.

ARCHITECTURE: nothing is patched, and in particular ``_gtfa_seams`` is not.
``_registry_candidates`` resolves the root through its own module globals, so a
``patch()`` on the root resolver is the kind of binding that can silently fail
to apply and leave a green test over an unexercised code path. Instead the
behavioural test builds a REAL temporary root — a ``.git`` marker, a copy of
``scripts/ac_store/``, and a registry written by ``json.dump`` at the deployed
location only — and runs the module in a genuinely fresh subprocess. A fresh
interpreter is required rather than ``importlib.reload``, which re-executes in
an already-populated namespace and would resolve the root from the repo.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _tkt_500f_support import REPO_ROOT, agent_registry_entries  # noqa: E402

import _gtfa_phase_agent  # noqa: E402  (sys.path prepared by _tkt_500f_fixtures)

#: Where a consumer install keeps the deployed config, relative to the root.
_DEPLOYED_SUFFIX = ".leafcutter/config/agent_registry.json"

#: The ineligible agent driven through the substitution. A real registry entry
#: with ``is_ticket_phase: false`` rather than an invented id, so this file
#: tests the non-phase branch the AC is about and not a registry miss.
_INELIGIBLE_AGENT = "workflow-architect"

#: The two eligible agents ``substitute_for_surface`` may choose between. Both
#: are carried into the fixture registry so the substitute it picks is itself a
#: real ``is_ticket_phase: true`` entry, exactly as in production.
_ELIGIBLE_AGENTS = ("python-coder", "llm-expert")

#: A non-template edit surface, so the expected substitute is python-coder.
_IMPL_SURFACE = "scripts/ac_store/some_module.py"

#: Substring of the degrade-and-warn message in ``_load_registry_entries``.
#: Its presence in the subprocess's stderr is the fingerprint of the original
#: defect: it means no candidate location yielded a registry.
_DEGRADE_FINGERPRINT = "eligibility check is skipped"

#: Run inside the temporary root, by a fresh interpreter. Kept deliberately
#: small: it imports the COPIED module (its own ``__file__`` is what the root
#: resolution walks up from) and prints one JSON line for the test to read.
_RUNNER_SOURCE = '''
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root / "scripts" / "ac_store"))

import _gtfa_phase_agent as phase_agent

print(json.dumps({
    "candidates": [str(p) for p in phase_agent._registry_candidates(None)],
    "resolved": phase_agent.resolve_phase_agent(
        sys.argv[1], sys.argv[2], [sys.argv[3]]
    ),
}))
'''


def _fixture_registry_entries() -> list[dict]:
    """Return the real registry entries this fixture needs, read off disk.

    Taken from the live ``config/agent_registry.json`` rather than hand-typed so
    the fixture cannot drift into describing agents that no longer exist, or
    into claiming an ``is_ticket_phase`` value the real registry contradicts.

    Returns:
        list[dict]: The entries for the ineligible agent and both substitutes.

    Raises:
        AssertionError: When the real registry no longer backs the fixture's
            premise — the ineligible agent has become a phase agent, an expected
            entry has disappeared, or a substitute is no longer eligible. Any of
            those would silently turn this file into a test of a different path.
    """
    wanted = {_INELIGIBLE_AGENT, *_ELIGIBLE_AGENTS}
    entries = [e for e in agent_registry_entries() if e.get("id") in wanted]
    found = {e.get("id") for e in entries}
    missing = sorted(wanted - found)
    if missing:
        raise AssertionError(  # noqa: TRY003
            f"config/agent_registry.json no longer has entries for {missing}; "
            "pick replacements, or this fixture stops describing the registry."
        )
    by_id = {e.get("id"): e for e in entries}
    if by_id[_INELIGIBLE_AGENT].get("is_ticket_phase") is True:
        raise AssertionError(  # noqa: TRY003
            f"{_INELIGIBLE_AGENT!r} is now is_ticket_phase: true, so it is no "
            "longer ineligible and no substitution would fire at all."
        )
    not_eligible = [a for a in _ELIGIBLE_AGENTS if by_id[a].get("is_ticket_phase") is not True]
    if not_eligible:
        raise AssertionError(  # noqa: TRY003
            f"{not_eligible} are no longer is_ticket_phase: true, so they "
            "cannot serve as the substitute this test expects."
        )
    return entries


def _build_deployed_only_root(root: Path) -> Path:
    """Populate *root* as a consumer-shaped install with no ``<root>/config/``.

    Args:
        root: An empty temporary directory to build the layout in.

    Returns:
        Path: The registry path actually written, for the test to assert on.
    """
    (root / ".git").mkdir()
    package = root / "scripts" / "ac_store"
    package.mkdir(parents=True)
    for module in (REPO_ROOT / "scripts" / "ac_store").glob("*.py"):
        shutil.copy2(module, package / module.name)

    registry_path = root / _DEPLOYED_SUFFIX
    registry_path.parent.mkdir(parents=True)
    with registry_path.open("w", encoding="utf-8") as handle:
        json.dump({"agents": _fixture_registry_entries()}, handle)
    return registry_path


def _run_in(root: Path) -> subprocess.CompletedProcess:
    """Resolve a phase agent inside *root*, in a fresh interpreter.

    Args:
        root: A root built by :func:`_build_deployed_only_root`.

    Returns:
        subprocess.CompletedProcess: The completed runner process.
    """
    runner = root / "run_resolve.py"
    runner.write_text(_RUNNER_SOURCE, encoding="utf-8")
    return subprocess.run(  # noqa: S603 - fixed argv, no shell, test-owned paths
        [
            sys.executable,
            str(runner),
            _INELIGIBLE_AGENT,
            "TKT-500f-5-i-deployed-layout",
            _IMPL_SURFACE,
        ],
        capture_output=True,
        text=True,
        cwd=str(root),
        timeout=60,
        check=False,
    )


class TestRegistryLocationFallback(unittest.TestCase):
    """TKT-500f-5-i: the eligibility check must find the registry in both layouts."""

    def test_registry_candidates_includes_the_deployed_config_location(self):
        # covers: TKT-500f-5-i
        # angle: criterion
        """The probe must offer ``.leafcutter/config/`` as well as ``config/``.

        A structural floor only — it proves the candidate list contains the
        deployed location, not that anything consumes it. The behavioural test
        below is what actually locks the fallback; this one localises the
        failure when the list itself is the thing that regressed.
        """
        candidates = [str(path) for path in _gtfa_phase_agent._registry_candidates(None)]

        self.assertTrue(
            any(path.endswith(_DEPLOYED_SUFFIX) for path in candidates),
            "A consumer install keeps the agent registry at "
            f"<root>/{_DEPLOYED_SUFFIX}. With that location absent from the "
            "candidate list the registry read can never succeed there, the "
            "eligibility check degrades, and the AC's ineligible assigned_agent "
            f"is emitted verbatim on every install. Got: {candidates}",
        )

    def test_substitution_still_fires_when_only_the_deployed_registry_exists(self):
        # covers: TKT-500f-5-i
        # angle: real_artifact
        """The regression lock: a deployed-only layout must still substitute.

        Builds a real root whose ONLY registry is at
        ``<root>/.leafcutter/config/agent_registry.json`` — written by json.dump,
        from the live registry's own entries — with no ``<root>/config/`` copy at
        all, and runs the module there in a fresh interpreter. Against the
        original one-location code this returns the ineligible agent verbatim
        and logs the degrade warning; both are asserted, because the return
        value alone cannot distinguish "found the registry elsewhere" from
        "found nothing and happened to agree".
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            registry_path = _build_deployed_only_root(root)

            self.assertTrue(
                registry_path.is_file(),
                f"Fixture did not write the deployed registry at {registry_path}.",
            )
            self.assertFalse(
                (root / "config").exists(),
                "The fixture root must have NO <root>/config/ copy — with one "
                "present the first candidate hits and the fallback this test "
                "exists for is never exercised.",
            )

            proc = _run_in(root)

        self.assertEqual(
            proc.returncode,
            0,
            "Resolving a phase agent in a consumer-shaped layout must not fail. "
            f"stdout={proc.stdout!r} stderr={proc.stderr[-2000:]!r}",
        )
        payload = json.loads(proc.stdout.strip().splitlines()[-1])

        self.assertEqual(
            payload["resolved"],
            "python-coder",
            f"{_INELIGIBLE_AGENT!r} is is_ticket_phase: false, so a ticket "
            "generated on a consumer install must name python-coder instead. "
            f"Getting {payload['resolved']!r} back means the registry at "
            f"<root>/{_DEPLOYED_SUFFIX} was never read and the substitution is "
            "a no-op on every install — the defect this test locks out.",
        )
        self.assertNotIn(
            _DEGRADE_FINGERPRINT,
            proc.stderr,
            "The degrade-and-warn path fired, which means no candidate location "
            "yielded a registry. The registry WAS on disk at "
            f"<root>/{_DEPLOYED_SUFFIX} — the probe simply did not look there. "
            f"stderr={proc.stderr[-2000:]!r}",
        )


if __name__ == "__main__":
    unittest.main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-23 [TKT-500f-5-i/test-writer]: Added to cover _registry_candidates'
  second location, which shipped with no unit test and only a one-off manual run
  of the deployed copy as evidence. The behavioural test copies the package into
  a temp root and re-runs the module in a subprocess rather than patching the
  root resolver: _registry_candidates reaches it through its own module globals,
  where a patch can silently fail to bind and leave a green test over the
  untouched path. Discrimination was verified by reducing _registry_candidates
  to the <root>/config/ location only — the behavioural test goes red (returns
  'workflow-architect' and logs the degrade warning) and the structural test
  goes red with it; both pass again once restored.
====================================================================
"""
