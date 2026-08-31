"""
MODULE: check_identifier_uniqueness_authoring.py
GOAL: Evaluate GE-122's whole-collection numbering rule at AUTHORING time
    (PostToolUse Edit|Write), importing and calling the SAME evaluation
    module the commit-time and shared-build stages use — never a second,
    independently-maintained copy of the rule.
BUSINESS CONTEXT: GE-122d-1 requires that one rule, evaluated at three
    stages (authoring time, commit time, shared-build time), cannot give
    three different answers. A per-stage reimplementation is the exact
    failure mode this AC exists to forbid: three stages that all evaluate
    "the same rule" only in the sense that someone copied the code once are
    indistinguishable, from a reader's perspective, from three stages that
    silently drifted apart. This module therefore contains NO scanning logic
    of its own — it locates and imports
    ``check_identifier_uniqueness.run_uniqueness_pass`` (the GE-122a-1
    evaluation module) and reports whatever it returns.
ARCHITECTURE: A single public function, ``evaluate_identifier_uniqueness``,
    that resolves the shared module by path relative to this file's own
    location rather than via a fixed absolute import. This is deliberate,
    not incidental: the two stages deploy to two DIFFERENT layouts under a
    shared project root — this hook to ``<root>/.claude/hooks/`` (a shim
    into ``<root>/.leafcutter/hooks/``) and the shared module to
    ``<root>/scripts/commit_guardian/`` (a shim into
    ``<root>/.leafcutter/scripts/commit_guardian/``) — but ``hooks/`` and
    ``scripts/commit_guardian/`` are SIBLINGS under both the deployed
    ``.leafcutter/`` root and the source-tree ``templates/`` root alike. A
    single ``parent.parent / "scripts" / "commit_guardian" / ...`` resolution
    therefore reaches the correct sibling in both layouts with no
    layout-specific branching:
      - Source tree: ``templates/hooks/../scripts/commit_guardian/...``
        == ``templates/scripts/commit_guardian/check_identifier_uniqueness.py``
      - Deployed:    ``.leafcutter/hooks/../scripts/commit_guardian/...``
        == ``.leafcutter/scripts/commit_guardian/check_identifier_uniqueness.py``
    This is the deploy-path resolution GE-122d-1's it_requirements flag as
    "the hard part" of this criterion.

DOC_LINKS:
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122d-1.yaml
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122a-1.yaml
  - templates/scripts/commit_guardian/check_identifier_uniqueness.py

DECISION HISTORY:
  - 2026-08-31 [python-coder/GE-122d-1]: Created. Fills the previously-empty
    authoring-time stage for GE-122's numbering rule by importing the
    existing commit-time module (``check_identifier_uniqueness.py``, built
    for GE-122a-1) rather than reimplementing the scan — the coverage note
    on GE-122d-1 explicitly rejects any test (and, by the same reasoning,
    any implementation) that lets the three stages hold independent copies
    of the rule. PostToolUse hook wiring (reading Claude Code's stdin
    payload and emitting a blocking decision) is intentionally NOT added in
    this increment: GE-122d-1's own test_spec scopes this AC to proving the
    three stages evaluate identically, not to the authoring hook's full
    Claude Code integration, which is a separate, not-yet-scheduled
    increment.
"""

from __future__ import annotations

import importlib.util as _ilu
import json
import sys
from pathlib import Path

_THIS_FILE = Path(__file__).resolve()
_SHARED_MODULE_PATH = (
    _THIS_FILE.parent.parent
    / "scripts"
    / "commit_guardian"
    / "check_identifier_uniqueness.py"
)


def _load_shared_uniqueness_module():
    """Import the shared GE-122a-1 evaluation module by file path.

    Loaded via ``importlib.util.spec_from_file_location`` (rather than a
    normal package import) so this hook works unmodified from both the
    source tree and the deployed layout, neither of which necessarily has
    the sibling ``scripts/commit_guardian/`` directory on ``sys.path``.

    Returns:
        The executed ``check_identifier_uniqueness`` module object, exposing
        ``run_uniqueness_pass``.

    Raises:
        ModuleNotFoundError: if the shared module is not present at the
            resolved sibling path — this stage cannot evaluate the same rule
            as the commit-time stage without it, so it fails loudly rather
            than silently reporting no findings.
    """
    if not _SHARED_MODULE_PATH.exists():
        raise ModuleNotFoundError(
            f"Shared uniqueness evaluation module not found at "
            f"{_SHARED_MODULE_PATH}. The authoring-time stage cannot "
            "evaluate the same rule as the commit-time and shared-build "
            "stages without it (GE-122d-1)."
        )
    spec = _ilu.spec_from_file_location(
        "check_identifier_uniqueness", _SHARED_MODULE_PATH
    )
    module = _ilu.module_from_spec(spec)
    sys.modules.setdefault(spec.name, module)
    spec.loader.exec_module(module)
    return module


def evaluate_identifier_uniqueness(root_path: str) -> str:
    """Evaluate GE-122's whole-collection uniqueness rule at authoring time.

    Delegates entirely to the shared ``run_uniqueness_pass`` — this function
    performs no scanning of its own, per this module's ARCHITECTURE note.

    Args:
        root_path: Root directory of the collection to inspect (the same
            argument shape ``run_uniqueness_pass`` accepts).

    Returns:
        A JSON string of the form ``{"contested_numbers": [...]}``, naming
        every number claimed by two or more artifacts across every namespace
        the shared module is responsible for.
    """
    shared = _load_shared_uniqueness_module()
    verdict = shared.run_uniqueness_pass(root_path)
    contested = sorted(
        {
            finding.number
            for namespace_verdict in verdict.namespaces.values()
            for finding in namespace_verdict.findings
        }
    )
    return json.dumps({"contested_numbers": contested})
