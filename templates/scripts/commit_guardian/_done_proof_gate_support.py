"""
MODULE: scripts/commit_guardian/_done_proof_gate_support.py
GOAL: Give check_done_proof.py's three entry points one shared way to read an
    AC record and one shared way to ask "is this record retired", with the
    whole-store id set computed at most once per run.
BUSINESS CONTEXT: ACS-900d-4. A record that was superseded by existing
    successors is no longer held to the covering-test rule, so each of
    check_staged_done_proofs, check_changed_done_acs and check_all_done_acs
    must consult the ONE predicate (scripts/ac_store/ac_retirement.py) before
    applying its rule. The three functions also carried three identical copies
    of the read-and-parse block; this module holds the single copy and was
    split out so check_done_proof.py repays its file-size ratchet instead of
    growing.
ARCHITECTURE: Sibling of check_done_proof.py (deploys with the directory, no
    deploy-map entry of its own). ``ac_retirement`` and
    ``_done_proof_composite.collect_store_ids`` live in scripts/ac_store/ and
    are reached through ``_ac_store_locator.ensure_ac_store_on_syspath``, which
    check_done_proof.py has already called. Both are imported lazily so a layout
    where they are missing degrades to "no record is retired" (fail closed:
    the covering-test rule applies) with a stderr WARNING, never to a crash.
    ``ac_retirement.is_retired`` is looked up on the module at call time, so a
    caller that replaces it (the seam test) is honoured.

DECISION HISTORY:
  - 2026-10-15 [python-coder]: Created for ACS-900d-4. read_ac_yaml returns an
    empty mapping on any read or parse failure so callers' existing
    ``work_status != "done"`` skip covers it, exactly as the inline blocks it
    replaces ``continue``d. (#TICKETLESS reason=acs-900d-4-ac-driven-no-ticket-file)
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml


def read_ac_yaml(yaml_path: Path) -> dict:
    """Read and parse one AC YAML file; return ``{}`` on any failure.

    Read and parse failures are logged to stderr at WARNING and treated as "not
    a done record" by the callers, matching the fail-open static scan the three
    check_done_proof entry points always had.

    Args:
        yaml_path: Path to the AC YAML file.

    Returns:
        The parsed mapping, or ``{}`` when the file cannot be read, cannot be
        parsed, or does not hold a YAML mapping.
    """
    try:
        with open(yaml_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (yaml.YAMLError, OSError) as exc:
        print(f"WARNING: check_done_proof: cannot read {yaml_path}: {exc}", file=sys.stderr)
        return {}
    return data if isinstance(data, dict) else {}


class RetirementLookup:
    """Per-run retired-record lookup; the store-id set is built once per store root."""

    def __init__(self) -> None:
        """Start with no store root resolved."""
        self._ids: dict[Path | None, frozenset[str]] = {}

    def store_ids(self, ac_root: object) -> frozenset[str]:
        """Return every AC id under *ac_root*, computing it on first use only.

        Args:
            ac_root: The ``acceptance-criteria`` directory, or anything else
                (``None``) when it could not be determined.

        Returns:
            The whole-store id set. Empty when the root is unknown, when
            ``_done_proof_composite`` cannot be imported, or when the store
            cannot be walked, so no record can be judged retired (fail closed).
        """
        root = ac_root if isinstance(ac_root, Path) else None
        if root not in self._ids:
            try:
                from _done_proof_composite import collect_store_ids
            except ImportError as exc:
                print(
                    f"WARNING: check_done_proof: store ids unavailable ({exc}); "
                    "no record is treated as retired.",
                    file=sys.stderr,
                )
                self._ids[root] = frozenset()
            else:
                self._ids[root] = collect_store_ids(root)
        return self._ids[root]

    def is_retired(self, data: dict, ac_root: object) -> bool:
        """Return whether the record *data* is retired (ACS-900d-4).

        The store walk happens only for a record whose status is a superseded
        status, so ordinary runs pay nothing.

        Args:
            data: The parsed AC record.
            ac_root: The ``acceptance-criteria`` directory, or ``None``.

        Returns:
            ``True`` only when ``ac_retirement.is_retired`` says so; ``False``
            when the predicate module is unavailable (fail closed).
        """
        try:
            import ac_retirement
        except ImportError as exc:
            print(
                f"WARNING: check_done_proof: ac_retirement unavailable ({exc}); "
                "no record is treated as retired.",
                file=sys.stderr,
            )
            return False
        if data.get("status") not in ac_retirement.RETIRED_STATUSES:
            return False
        return ac_retirement.is_retired(data, self.store_ids(ac_root))
