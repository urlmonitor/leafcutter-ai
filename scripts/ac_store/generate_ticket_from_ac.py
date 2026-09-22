#!/usr/bin/env python3
"""
MODULE: generate_ticket_from_ac
GOAL: Generate a ticket file from an AC YAML record in the acceptance-criteria store.
BUSINESS CONTEXT: Ticket generation is the bridge between authored ACs and actionable
    work items — it converts machine-readable AC YAML into the frontmatter, agent map,
    test requirements, and sign-off sections that phase agents need.
ARCHITECTURE: CLI script in scripts/ac_store/; called by the /build-ac workflow and
    by ticket-supervisors; reads config/guardrail_gates.yaml + config/agent_registry.json
    to compute the agents map, and writes tickets to tickets/00_inbox/.

    This module is the SHELL of the generator. The implementation lives in the
    ``_gtfa_*`` sibling modules listed below; the shell imports them, wires the
    late-bound seams, and re-exports every name so that this module object
    remains the single namespace callers and tests use. That is a contract, not
    a convenience: roughly 80 test files reach into this module by attribute —
    calling ``gen._build_files_touched(...)``, reading ``gen._TEST_ANGLES``,
    patching ``generate_ticket_from_ac._find_worktree_root`` — and
    ``scripts/ac_store/ac_coverage_resolver.py`` does the same in production.

    Sibling modules:
      _gtfa_seams            late-bound access to this shell's patched seams
      _gtfa_constants        every shared constant + the AcRecord alias
      _gtfa_paths            worktree root, path canonicalisation, ticket filename
      _gtfa_config           guardrail-gates / agent-registry reads
      _gtfa_components       component vocabulary resolution
      _gtfa_phases           location-keyed phase deferral (+ its two error types)
      _gtfa_files_touched    files_touched derivation
      _gtfa_store            AC-store and ticket lookup, parent resolution
      _gtfa_test_descriptors criteria-derived descriptors + the reachability floor
      _gtfa_tests_section    the ## Test Requirements block
      _gtfa_doc_genre        Diataxis genre / doc-path / content-constraint
      _gtfa_contracts        the ## Agent Contracts section
      _gtfa_doc_gates        the documentation_gates policy (3 dimensions)
      _gtfa_agents_map       the agents map
      _gtfa_frontmatter      the YAML frontmatter block
      _gtfa_body             the ticket body and sign-offs
      _gtfa_implemented_by   the implemented_by back-reference write
      _gtfa_report           the --verify readiness report
      _gtfa_cli_parser       the argparse surface
      _gtfa_cli              main() and the write path
      _gtfa_decision_history this module's DECISION HISTORY, kept verbatim

Usage:
    python3 scripts/ac_store/generate_ticket_from_ac.py --ac <ac_id> [options]

Options:
    --ac AC_ID              AC id to generate a ticket for (required).
    --ac-root PATH          Root directory of the AC store (default:
                            docs/acceptance-criteria/ relative to worktree).
    --tickets-root PATH     Root directory for written tickets (default:
                            tickets/00_inbox/ relative to worktree).
    --dry-run               Print the ticket body to stdout without writing.

Exit codes:
    0  Ticket written successfully (or --dry-run printed the body).
    1  AC id not found, the ticket already exists (idempotency guard),
       or a file I/O / YAML error occurred. The error message names the
       affected file.

AC-2: Generator produces a valid ticket from an AC YAML.
AC-3: Generator writes implemented_by back-reference into source AC.
AC-4: Generator is idempotent — re-run with existing ticket exits non-zero.
AC-6: Ticket passes ticket_frontmatter_guard without errors.

DECISION HISTORY: see ``_gtfa_decision_history.py`` — the dated record of why
each behaviour here is the way it is. It lives in its own module because it is
174 lines of documentation and this shell must stay under the repo's 400-line
Python cap; the size gate must never be satisfied by deleting documentation.
"""

from __future__ import annotations

import importlib
import logging
import sys

# Part of this module's ATTRIBUTE SURFACE, not of its implementation. Before the
# decomposition these names were bound here by the implementation's own imports,
# so ``generate_ticket_from_ac.Path``, ``.yaml``, ``.subprocess`` and the rest
# were all reachable — and this repo's tests routinely reach a module's imported
# stdlib names, e.g. ``patch("<module>.subprocess.run")``. Dropping them would be
# a silent narrowing of the surface that no current test happens to catch, which
# is precisely the kind of change that only fails later and somewhere else. They
# are re-imported, in the original set, for that reason alone.
import argparse  # noqa: F401 - attribute surface, see above
import glob as _glob  # noqa: F401 - attribute surface, see above
import json  # noqa: F401 - attribute surface, see above
import re  # noqa: F401 - attribute surface, see above
import subprocess  # noqa: F401 - attribute surface, see above
from datetime import date  # noqa: F401 - attribute surface, see above
from pathlib import Path  # noqa: F401 - attribute surface, see above
from typing import TYPE_CHECKING, Any  # noqa: F401 - attribute surface, see above

import yaml  # noqa: F401 - attribute surface, see above

logger = logging.getLogger(__name__)


if TYPE_CHECKING:  # pragma: no cover - a static declaration, never executed
    # DECLARED FOR STATIC ANALYSIS, NOT FOR RUNTIME. The real imports are at the
    # bottom of the "Sibling wiring" block below and go through
    # ``importlib.import_module`` with a COMPUTED name, because the prefix
    # depends on which of the two layouts this module was imported under.
    #
    # A computed name is undecidable statically, so
    # scripts/build_referential_integrity.py's closure analyser sees no
    # dependency from this module to any sibling — and that analyser is exactly
    # what proves every module a deployed script needs is in
    # build_phases.AC_STORE_DEPLOY_MAP. Without these declarations the guard is
    # blind to this module's whole dependency chain, so a sibling omitted from
    # the manifest would ship a generator that dies at import in the deployed
    # layout while every unit test, importing from source, stayed green. That
    # is precisely the failure shape BP-900g-8 exists to close, and it is why
    # these lines are a safety mechanism rather than bookkeeping.
    #
    # The relative form is what the analyser resolves (it reads `from . import
    # X` against this file's own directory) and is also the form a type checker
    # resolves, since scripts/ac_store carries an __init__.py.
    from . import _gtfa_agents_inputs  # noqa: F401
    from . import _gtfa_agents_map  # noqa: F401
    from . import _gtfa_body  # noqa: F401
    from . import _gtfa_cli  # noqa: F401
    from . import _gtfa_cli_parser  # noqa: F401
    from . import _gtfa_components  # noqa: F401
    from . import _gtfa_config  # noqa: F401
    from . import _gtfa_constants  # noqa: F401
    from . import _gtfa_contracts  # noqa: F401
    from . import _gtfa_decision_history  # noqa: F401
    from . import _gtfa_doc_gates  # noqa: F401
    from . import _gtfa_doc_genre  # noqa: F401
    from . import _gtfa_files_touched  # noqa: F401
    from . import _gtfa_frontmatter  # noqa: F401
    from . import _gtfa_implemented_by  # noqa: F401
    from . import _gtfa_paths  # noqa: F401
    from . import _gtfa_phases  # noqa: F401
    from . import _gtfa_report  # noqa: F401
    from . import _gtfa_seams  # noqa: F401
    from . import _gtfa_store  # noqa: F401
    from . import _gtfa_test_descriptors  # noqa: F401
    from . import _gtfa_tests_section  # noqa: F401


# ---------------------------------------------------------------------------
# Sibling wiring
#
# The sibling package prefix is derived from THIS module's own ``__name__``
# rather than hard-coded, because the module is legitimately imported under two
# different names: bare ``generate_ticket_from_ac`` (after a ``sys.path``
# insert of ``scripts/ac_store``, which is what most tests and
# ``ac_coverage_resolver`` do) and dotted
# ``scripts.ac_store.generate_ticket_from_ac``. Deriving the prefix guarantees
# a sibling is always imported under the same layout as the shell importing it,
# so the two layouts can never end up sharing a half-initialised module.
#
# ``importlib.import_module`` is used rather than the
# ``importlib.util.spec_from_file_location`` pattern that ``_load_migration_map``
# uses for its data module: that pattern builds a FRESH, uncached module object
# on every call, which is right for a leaf data file and wrong for a set of
# interdependent modules that must share identity.
# ---------------------------------------------------------------------------

_SIBLING_PACKAGE = __name__.rpartition(".")[0]


def _sibling(name: str):
    """Import a ``_gtfa_*`` sibling under this module's own import layout.

    Args:
        name: Unqualified sibling module name, e.g. ``"_gtfa_constants"``.

    Returns:
        The imported sibling module object.
    """
    return importlib.import_module(
        f"{_SIBLING_PACKAGE}.{name}" if _SIBLING_PACKAGE else name
    )


_gtfa_seams = _sibling("_gtfa_seams")
_gtfa_constants = _sibling("_gtfa_constants")

# Bind the shell before anything below runs. Siblings resolve the seams they
# must see through the shell (a patched ``_find_worktree_root``, the current
# ``_COMPONENT_MIGRATION_MAP``) via this binding, at call time.
_gtfa_seams.bind_shell(sys.modules[__name__])

_gtfa_paths = _sibling("_gtfa_paths")
_gtfa_config = _sibling("_gtfa_config")
_gtfa_components = _sibling("_gtfa_components")
_gtfa_phases = _sibling("_gtfa_phases")
_gtfa_files_touched = _sibling("_gtfa_files_touched")
_gtfa_store = _sibling("_gtfa_store")
_gtfa_test_descriptors = _sibling("_gtfa_test_descriptors")
_gtfa_tests_section = _sibling("_gtfa_tests_section")
_gtfa_doc_genre = _sibling("_gtfa_doc_genre")
_gtfa_contracts = _sibling("_gtfa_contracts")
_gtfa_doc_gates = _sibling("_gtfa_doc_gates")
_gtfa_agents_map = _sibling("_gtfa_agents_map")
_gtfa_frontmatter = _sibling("_gtfa_frontmatter")
_gtfa_body = _sibling("_gtfa_body")
_gtfa_implemented_by = _sibling("_gtfa_implemented_by")
_gtfa_report = _sibling("_gtfa_report")
_gtfa_cli_parser = _sibling("_gtfa_cli_parser")
_gtfa_cli = _sibling("_gtfa_cli")
_gtfa_decision_history = _sibling("_gtfa_decision_history")


# ---------------------------------------------------------------------------
# Constants (defined in _gtfa_constants; re-exported here because the test
# suites read several of them off this module object)
# ---------------------------------------------------------------------------

_DEFAULT_AC_ROOT = _gtfa_constants._DEFAULT_AC_ROOT
_DEFAULT_TICKETS_ROOT = _gtfa_constants._DEFAULT_TICKETS_ROOT
TEST_ANGLE_CRITERION = _gtfa_constants.TEST_ANGLE_CRITERION
TEST_ANGLE_REACHABILITY = _gtfa_constants.TEST_ANGLE_REACHABILITY
_TEST_ANGLES = _gtfa_constants._TEST_ANGLES
_REACHABILITY_ASSERTS = _gtfa_constants._REACHABILITY_ASSERTS
_EDIT_SURFACE_RELATIONSHIPS = _gtfa_constants._EDIT_SURFACE_RELATIONSHIPS
_PROSE_PATH_EXTENSIONS = _gtfa_constants._PROSE_PATH_EXTENSIONS
_DOC_CONFIG_EXTENSIONS = _gtfa_constants._DOC_CONFIG_EXTENSIONS
_SOURCE_CODE_EXTENSIONS = _gtfa_constants._SOURCE_CODE_EXTENSIONS
_KNOWN_CODERS = _gtfa_constants._KNOWN_CODERS
_KNOWN_PATH_PREFIXES = _gtfa_constants._KNOWN_PATH_PREFIXES
_PROSE_PATH_TOKEN_RE = _gtfa_constants._PROSE_PATH_TOKEN_RE
_CANONICAL_SUPPORT_AGENTS = _gtfa_constants._CANONICAL_SUPPORT_AGENTS
_SQL_AGENTS = _gtfa_constants._SQL_AGENTS
_NOT_NEEDED_AGENTS = _gtfa_constants._NOT_NEEDED_AGENTS
_CANONICAL_PHASE_ORDER = _gtfa_constants._CANONICAL_PHASE_ORDER
_FLOW_CHANGE_PHASE_ORDER = _gtfa_constants._FLOW_CHANGE_PHASE_ORDER
_DEFAULT_AGENT_REGISTRY = _gtfa_constants._DEFAULT_AGENT_REGISTRY
_DEFAULT_GUARDRAIL_GATES = _gtfa_constants._DEFAULT_GUARDRAIL_GATES
_DEFAULT_PHASE_DEFERRAL = _gtfa_constants._DEFAULT_PHASE_DEFERRAL
AcRecord = _gtfa_constants.AcRecord


# ---------------------------------------------------------------------------
# Phase-deferral declaration (TKT-600b-1)
# ---------------------------------------------------------------------------

PhaseDeferralDeclarationError = _gtfa_phases.PhaseDeferralDeclarationError
UnresolvedDestinationError = _gtfa_phases.UnresolvedDestinationError
_default_phase_deferral_path = _gtfa_phases._default_phase_deferral_path
_load_phase_deferral = _gtfa_phases._load_phase_deferral
_location_kind_for_destination = _gtfa_phases._location_kind_for_destination
_resolve_deferred_phases = _gtfa_phases._resolve_deferred_phases


# ---------------------------------------------------------------------------
# Worktree root detection and path canonicalisation
#
# ``_find_worktree_root`` is re-exported as a module attribute rather than
# called through the sibling, because unit_tests/ac_store/test_tkt_500f_17.py
# patches ``generate_ticket_from_ac._find_worktree_root`` and drives main().
# Siblings reach it via _gtfa_seams.find_worktree_root, which resolves it off
# THIS module at call time so the patch is honoured everywhere it matters.
#
# Bound before the _COMPONENT_MIGRATION_MAP statement below, preserving the
# original file's deliberate ordering (see the function's DECISION HISTORY).
# ---------------------------------------------------------------------------

_find_worktree_root = _gtfa_paths._find_worktree_root
_normalise_repo_relative = _gtfa_paths._normalise_repo_relative
_canonicalise_to_repo_relative = _gtfa_paths._canonicalise_to_repo_relative
_derive_repo_root_from_git = _gtfa_paths._derive_repo_root_from_git
_ticket_filename = _gtfa_paths._ticket_filename


# ---------------------------------------------------------------------------
# Component vocabulary: kebab → underscore normalisation
# ---------------------------------------------------------------------------

_load_migration_map = _gtfa_components._load_migration_map
_load_valid_component_ids = _gtfa_components._load_valid_component_ids
_build_components_list = _gtfa_components._build_components_list

# Executed HERE, in the shell's own module body, and deliberately so:
# unit_tests/ac_store/test_tkt_500f_18_i.py calls importlib.reload() on this
# module under a patched importlib.util and requires the reload to re-run this
# statement. A re-export of a value computed in the sibling's body would
# survive the reload unchanged and make that test pass without exercising
# anything. _build_components_list reads this back through _gtfa_seams for the
# same reason.
_COMPONENT_MIGRATION_MAP: dict[str, str] = _load_migration_map()


# ---------------------------------------------------------------------------
# AC / ticket lookup
# ---------------------------------------------------------------------------

_find_ac_by_id = _gtfa_store._find_ac_by_id
_find_existing_ticket = _gtfa_store._find_existing_ticket
_load_derive_parent_id_fn = _gtfa_store._load_derive_parent_id_fn
_load_parent_ac = _gtfa_store._load_parent_ac
_expects_from_ac_ids = _gtfa_store._expects_from_ac_ids
_build_ticket_depends_on = _gtfa_store._build_ticket_depends_on


# ---------------------------------------------------------------------------
# files_touched derivation
# ---------------------------------------------------------------------------

_extract_local_paths = _gtfa_files_touched._extract_local_paths
_extract_paths_from_prose = _gtfa_files_touched._extract_paths_from_prose
_resolve_worktree_root_or_none = _gtfa_files_touched._resolve_worktree_root_or_none
_is_real_prose_path = _gtfa_files_touched._is_real_prose_path
_paths_declared_non_edit_surface_only = (
    _gtfa_files_touched._paths_declared_non_edit_surface_only
)
_build_files_touched = _gtfa_files_touched._build_files_touched
_resolve_reference_patterns = _gtfa_files_touched._resolve_reference_patterns


# ---------------------------------------------------------------------------
# Config reads and the agents map
# ---------------------------------------------------------------------------

_load_guardrail_gates = _gtfa_config._load_guardrail_gates
_load_production_code_agents = _gtfa_config._load_production_code_agents
_agent_produces_production_code = _gtfa_config._agent_produces_production_code
_computed_map_has_production_code_producer = (
    _gtfa_config._computed_map_has_production_code_producer
)
_build_agents_map = _gtfa_agents_map._build_agents_map


# ---------------------------------------------------------------------------
# Test requirements
# ---------------------------------------------------------------------------

_slugify_for_test = _gtfa_test_descriptors._slugify_for_test
_unique_test_name = _gtfa_test_descriptors._unique_test_name
_reachability_descriptor = _gtfa_test_descriptors._reachability_descriptor
_derive_tests_from_criteria = _gtfa_test_descriptors._derive_tests_from_criteria
_ensure_reachability_floor = _gtfa_test_descriptors._ensure_reachability_floor
_test_descriptors_from_spec = _gtfa_tests_section._test_descriptors_from_spec
_has_authored_test_spec = _gtfa_tests_section._has_authored_test_spec
_build_test_requirements_section = _gtfa_tests_section._build_test_requirements_section


# ---------------------------------------------------------------------------
# Documentation genre and agent contracts
# ---------------------------------------------------------------------------

_extract_doc_genre = _gtfa_doc_genre._extract_doc_genre
_resolve_genres_from_parent = _gtfa_doc_genre._resolve_genres_from_parent
_extract_doc_path = _gtfa_doc_genre._extract_doc_path
_derive_content_constraint = _gtfa_doc_genre._derive_content_constraint
_as_contract_entries = _gtfa_contracts._as_contract_entries
_build_doc_links_cross_link_lines = _gtfa_contracts._build_doc_links_cross_link_lines
_build_agent_contracts_section = _gtfa_contracts._build_agent_contracts_section


# ---------------------------------------------------------------------------
# Frontmatter, body, and the implemented_by back-reference
# ---------------------------------------------------------------------------

_build_frontmatter = _gtfa_frontmatter._build_frontmatter
_map_priority = _gtfa_frontmatter._map_priority
_normalize_change_target = _gtfa_frontmatter._normalize_change_target
_parse_test_constraints = _gtfa_frontmatter._parse_test_constraints
_infer_complexity = _gtfa_frontmatter._infer_complexity
_complexity_to_model_tier = _gtfa_frontmatter._complexity_to_model_tier
_should_escalate_to_opus = _gtfa_frontmatter._should_escalate_to_opus

_build_implementation_notes_section = _gtfa_body._build_implementation_notes_section
_build_signoffs_section = _gtfa_body._build_signoffs_section
reject_phantom_signoff = _gtfa_body.reject_phantom_signoff
_criteria_checkboxes = _gtfa_body._criteria_checkboxes
_build_ticket_body = _gtfa_body._build_ticket_body

_write_implemented_by = _gtfa_implemented_by._write_implemented_by


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_build_verification_report = _gtfa_report._build_verification_report
_build_parser = _gtfa_cli_parser._build_parser
_build_agents_map_for_write_path = _gtfa_cli._build_agents_map_for_write_path
main = _gtfa_cli.main


if __name__ == "__main__":
    sys.exit(main())
