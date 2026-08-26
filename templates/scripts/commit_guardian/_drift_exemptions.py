"""
MODULE: _drift_exemptions
GOAL: Shared exemption-registry loading, validation, and scan-result shape for
    check_build_drift.py and check_output_drift.py (BP-100k-3). An artifact
    either gate cannot compare against the manifest must be reported as a
    declared exemption (naming its ground) or a coverage gap (naming the
    registering action) — never folded into a silent, clean-looking pass.
BUSINESS CONTEXT: AC-5 requires both drift gates to honour the SAME
    exemption registry — a declaration honoured by one gate and ignored by
    its sibling reintroduces the ambiguity BP-100k-3 removes. Splitting this
    logic into one shared, private module (mirroring the
    _presence_only_scanner.py precedent used by
    check_presence_only_assertions.py) is what makes "the same registry"
    mechanically true rather than an aspiration two near-identical copies
    could silently drift apart from.
ARCHITECTURE: ``load_exemption_registry()`` reads ``HOOK_TEST_CONFIG`` (a
    path to a JSON file containing ONLY the ``drift_gate_exemption_registry``
    key) when set, for testing; otherwise it reads the real
    ``commit_guardian.json`` colocated with the calling gate module — the
    REGISTRATION SURFACE named in this ticket's Implementation Notes.
    ``validate_exemption_registry()`` rejects any entry with no non-blank
    ``ground`` (AC-5's "groundless entry" clause) rather than silently
    honouring it. ``ScanResult`` is the shared per-family scan outcome shape
    (verified / uncomparable / violations) both gates' ``main()`` functions
    aggregate into one ``RESULT verified=<N> uncomparable=<M> drifted=<D>``
    summary line.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger(__name__)


class ScanResult(NamedTuple):
    """Outcome of scanning one artifact family against the build manifest.

    Attributes:
        verified: Count of artifacts found in the manifest/output_mappings
            and hash-compared (regardless of match/drift outcome). Never
            includes uncomparable artifacts (AC-4) or missing artifacts
            (BP-100k-6).
        uncomparable: Count of artifacts neither found in the manifest
            (coverage gap) nor validly declared exempt — i.e.
            ``gaps + exempt_count``. Reported transparently in the RESULT
            summary line, but does NOT by itself drive the exit verdict —
            see ``gaps``. Never includes ``missing`` artifacts: an artifact
            IS in the manifest/output_mappings but absent from disk, which
            demands a different remedy (restore or deliberately un-record
            it) than a coverage gap (register it) or a declared exemption,
            and the two must stay distinguishable (BP-100k-6).
        gaps: Count of uncomparable artifacts that are NOT validly declared
            exempt (a subset of ``uncomparable``). This is what the exit
            verdict is keyed on: BP-100k-3's own three-way distinction (gap /
            declared exemption / clean pass) requires that stating a ground
            and getting blocked anyway would collapse it back to two, making
            the exemption registry pointless. A declared, grounded exemption
            is reported (the ``UNCOMPARABLE: EXEMPT`` line and the
            ``uncomparable`` count) but never blocks the commit on its own.
        missing: Count of artifacts recorded in the manifest/output_mappings
            whose file is absent from disk (BP-100k-6) — deletion is the
            most complete form of drift there is. Reported as its own
            ``UNCOMPARABLE: MISSING <key> reason=recorded but not found on
            disk`` line and its own ``missing=<X>`` RESULT field; never
            folded into ``verified`` or ``uncomparable``, and always drives
            a non-clean exit.
        violations: Drifted-artifact records (shape is caller-defined — a
            plain key for template drift, a (key, template) pair for output
            drift).
    """

    verified: int
    uncomparable: int
    gaps: int
    missing: int
    violations: list


def load_exemption_registry(gate_name: str) -> list:
    """Load the raw drift_gate_exemption_registry entries.

    Uses ``HOOK_TEST_CONFIG`` (a path to a JSON file containing ONLY the
    ``drift_gate_exemption_registry`` key) when set, for testing. Otherwise
    reads ``commit_guardian.json`` colocated with this module — which
    build.py deploys verbatim alongside check_build_drift.py and
    check_output_drift.py as part of the whole-directory
    scripts/commit_guardian/ copy — and returns its
    ``drift_gate_exemption_registry`` key, the SAME registry both drift
    gates read (AC-5).

    Args:
        gate_name: Gate name used in diagnostic prefixes ("check-build-drift"
            or "check-output-drift").

    Returns:
        The raw list of entry dicts (may be empty). Malformed entries are
        not filtered here — see ``validate_exemption_registry``.
    """
    test_config_path = os.environ.get("HOOK_TEST_CONFIG")
    config_path = (
        Path(test_config_path)
        if test_config_path
        else Path(__file__).resolve().parent / "commit_guardian.json"
    )
    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
    except OSError as exc:
        logger.warning("%s: cannot read exemption registry at %s: %s", gate_name, config_path, exc)
        return []
    except json.JSONDecodeError as exc:
        logger.warning(
            "%s: exemption registry at %s is not valid JSON: %s", gate_name, config_path, exc
        )
        return []

    entries = config.get("drift_gate_exemption_registry", [])
    if not isinstance(entries, list):
        logger.warning(
            "%s: drift_gate_exemption_registry in %s is not a list; ignoring.",
            gate_name,
            config_path,
        )
        return []
    return entries


def validate_exemption_registry(entries: list) -> dict[str, str]:
    """Split raw registry entries into a valid path -> ground map.

    An entry whose ``ground`` is missing, empty, or whitespace-only is
    rejected rather than silently honoured (AC-5): a ``REJECTED EXEMPTION
    ENTRY: <key> reason=no ground stated`` line is printed and the entry is
    excluded from the returned map, so its artifact falls through to the GAP
    form during scanning.

    Args:
        entries: Raw entries from ``load_exemption_registry``.

    Returns:
        Mapping of artifact key to non-blank ground text, for valid entries only.
    """
    valid: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path")
        if not path:
            continue
        ground = entry.get("ground", "")
        if isinstance(ground, str) and ground.strip():
            valid[path] = ground.strip()
        else:
            print(f"REJECTED EXEMPTION ENTRY: {path} reason=no ground stated", file=sys.stderr)
    return valid


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-19 [python-coder/EPIC-BuildPipelinePhantomRemediation/08]: Created
#   module. Split out of check_build_drift.py / check_output_drift.py so
#   BP-100k-3's AC-5 ("both gates honour the same exemption registry") is
#   mechanically enforced by a single shared implementation rather than two
#   copies that could drift apart, and so neither gate module exceeds the
#   400-line file-size limit. Mirrors the _presence_only_scanner.py /
#   check_presence_only_assertions.py split precedent (BP-1100b-5).
# ====================================================================
