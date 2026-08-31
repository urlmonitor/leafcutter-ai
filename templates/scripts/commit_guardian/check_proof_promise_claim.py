"""
MODULE: scripts/commit_guardian/check_proof_promise_claim.py
GOAL: Refuse a piece of work, by name, whose plan promised a kind of proof for a
    stated behaviour but whose test tree carries no matching claim for it.
BUSINESS CONTEXT: BP-1100g-3 built the CLAIM side (the second tag axis,
    ``collect_test_tag_records`` in ``scripts/ac_store/done_proof.py``,
    collected from real on-disk test files via a single-pass scanner). This
    module builds the PROMISE side (the ``## Test Requirements`` descriptors a
    ticket declares, each carrying an ``angle`` and a ``covers`` list) and the
    comparison between the two. The promise set is the denominator: a kind
    never promised for a piece of work is never named in its refusal, and a
    ticket that promises nothing is never refused. The outcome is never worded
    as reached, proven, verified, or done — it is either "promised and
    claimed" or a named list of what was promised and never claimed.
ARCHITECTURE: Pure comparison over two authored declarations only.

    Promise side (no I/O beyond the caller-supplied ticket text):
        extract_promised_kinds(ticket_content) -> list[dict]
            Parses the fenced YAML block under a ticket's own
            ``## Test Requirements`` heading (the exact shape
            ``generate_ticket_from_ac.py`` emits) into one promise dict per
            (descriptor, covers-id) pair: {"ac_id", "angle", "behaviour"}.

    Claim side (imported, never reimplemented — BO-2900a-2):
        ``done_proof.collect_test_tag_records`` is the single shared scanner
        for the ``# covers:`` / ``# angle:`` tag axes. This module never opens,
        parses, tokenizes, imports-for-inspection, or regexes a test's BODY —
        it only consumes the per-function records that scanner already
        produces.
        build_claim_index(records) -> dict[str, set[str]]
            Folds those records into {ac_id: {claimed angle, ...}}.

    Comparison (pure, iterates the promise set only):
        find_unmatched_promises(promises, claims) -> list[dict]
        format_refusal(violations) -> str

    CLI entry point (I/O boundary — the only place this module reads files or
    scans a directory tree):
        main(argv) -> int
            ``argv`` is the staged ticket ``.md`` paths (pre-commit's
            "pass_filenames" convention). Reads each ticket, extracts its
            promised kinds, scans the project's test tree via
            ``done_proof.collect_test_tag_records`` for the claim side, and
            prints ``format_refusal()``'s output. A ticket that cannot be read
            is reported as a distinct read failure — never folded into "a
            promise had no claim", which would misdirect the fix (BP-1100g-4's
            fail-closed distinction).

    Import resolution mirrors ``check_done_proof.py``'s existing pattern: the
    sibling ``scripts/ac_store/`` directory (source layout) or
    ``../ac_store/`` (deployed layout, both siblings of
    ``scripts/commit_guardian/``) is added to ``sys.path`` so
    ``done_proof.collect_test_tag_records`` resolves in both layouts. Its own
    dependency, ``test_enforcement.py``, is already required by
    ``done_proof.py`` and already present in ``build_ac_store``'s
    ``AC_STORE_DEPLOY_MAP`` (added alongside ``done_proof.py`` itself) — no new
    deploy-manifest entry is needed for this module's own import chain.

    Hook registration (REGISTRATION IS PART OF THE WORK): the hook id
    ``check-proof-promise-claim`` is registered in this directory's own
    ``commit_guardian.json``, so an unregistered gate never runs.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent

from _resolve_root import find_project_root  # noqa: E402

# ---------------------------------------------------------------------------
# Fail-safe import of the CLAIM-side scanner (mirrors check_done_proof.py's
# own pattern exactly): a module-level name that unittest.mock.patch can
# replace, with a lazy fallback for source layouts whose sibling ac_store/
# is not the deployed one (e.g. templates/ with only a placeholder ac_store/).
# ---------------------------------------------------------------------------
try:
    _ac_store = _HERE.parent / "ac_store"
    if str(_ac_store) not in sys.path:
        sys.path.insert(0, str(_ac_store))
    from done_proof import collect_test_tag_records
except (ImportError, ModuleNotFoundError):

    def collect_test_tag_records(*args, **kwargs):
        """Lazy shim used when done_proof is not importable at module load.

        Keeps ``collect_test_tag_records`` a real, patchable module-level
        attribute while deferring the real import until first call, resolved
        via the sibling ``ac_store`` in the deployed layout.
        """
        return _load_collect_test_tag_records()(*args, **kwargs)


def _load_collect_test_tag_records():
    """Import ``done_proof.collect_test_tag_records`` from the sibling ac_store.

    Serves as the None-fallback when the top-level import failed (e.g. in a
    source layout where ``scripts/ac_store/done_proof.py`` is absent).

    Returns:
        The ``collect_test_tag_records`` callable from ``done_proof``.
    """
    ac_store = _HERE.parent / "ac_store"
    if str(ac_store) not in sys.path:
        sys.path.insert(0, str(ac_store))
    from done_proof import collect_test_tag_records

    return collect_test_tag_records


# Locates the fenced YAML block immediately following a ## Test Requirements
# heading — the exact shape generate_ticket_from_ac.py's
# _build_test_requirements_section emits (mirrors
# check_ticket_test_requirements.py's own _TESTS_BLOCK_RE).
_TEST_REQUIREMENTS_BLOCK_RE = re.compile(
    r"##\s+Test\s+Requirements\b.*?```(?:yaml)?\s*(.*?)```",
    re.DOTALL | re.IGNORECASE,
)

# The generic placeholder wording an implementer writes first — this check's
# own output must never regress to it (BP-1100g-4's Wording section).
_PLACEHOLDER_WORDING = "proof requirements not met"


# ---------------------------------------------------------------------------
# Promise side — pure parsing of the caller-supplied ticket text.
# ---------------------------------------------------------------------------


def extract_promised_kinds(ticket_content: str) -> list[dict]:
    """Extract the promised (ac_id, angle, behaviour) triples from a ticket.

    Parses the fenced YAML block under the ticket's own ``## Test
    Requirements`` heading — the same ``tests:`` array shape
    ``generate_ticket_from_ac.py`` emits (``name``, ``file``, ``covers``,
    ``asserts``, ``framework``, ``type``, ``angle``). One promise dict is
    produced per (descriptor, covers-id) pair, since a single descriptor may
    promise the same kind of proof for more than one AC id.

    A descriptor with no ``angle`` or no ``covers`` entries contributes no
    promise — an unpromised kind must never be inferable from an incomplete
    descriptor.

    Args:
        ticket_content: Full text of a ticket markdown file (or, for the
            generator seam, the raw dry-run ticket body printed to stdout).

    Returns:
        List of ``{"ac_id": str, "angle": str, "behaviour": str}`` dicts.
        Empty when no ``## Test Requirements`` block is present, the block is
        unparseable, or no descriptor carries both ``angle`` and ``covers``.
    """
    match = _TEST_REQUIREMENTS_BLOCK_RE.search(ticket_content)
    if match is None:
        return []
    yaml_block = match.group(1)
    if not yaml_block.strip():
        return []
    try:
        parsed = yaml.safe_load(yaml_block)
    except yaml.YAMLError as exc:
        print(
            f"WARNING: check_proof_promise_claim: cannot parse Test "
            f"Requirements YAML: {exc}",
            file=sys.stderr,
        )
        return []
    if not isinstance(parsed, dict):
        return []
    descriptors = parsed.get("tests")
    if not isinstance(descriptors, list):
        return []

    promises: list[dict] = []
    for descriptor in descriptors:
        if not isinstance(descriptor, dict):
            continue
        angle = descriptor.get("angle")
        covers = descriptor.get("covers")
        if not angle or not covers:
            continue
        if isinstance(covers, str):
            covers = [covers]
        if not isinstance(covers, list):
            continue
        behaviour = str(descriptor.get("asserts") or descriptor.get("name") or "")
        for ac_id in covers:
            if not ac_id:
                continue
            promises.append(
                {"ac_id": str(ac_id), "angle": str(angle), "behaviour": behaviour}
            )
    return promises


# ---------------------------------------------------------------------------
# Claim side — pure grouping of records already collected by done_proof.
# ---------------------------------------------------------------------------


def build_claim_index(records: list[dict]) -> dict[str, set[str]]:
    """Fold per-function tag records into ``{ac_id: {claimed angle, ...}}``.

    A claim exists only when a SINGLE record (one test function) carries BOTH
    a ``covers`` id and an ``angle`` together — a function with covers but no
    angle tag (or an angle but no covers tag) contributes no claim for either
    axis alone. This mirrors ``done_proof``'s own "ONE SCANNER, TWO AXES"
    per-function record shape rather than treating the two axes as
    independently truthful about the same function.

    Args:
        records: The per-function records ``collect_test_tag_records``
            already produces (``{"covers": list[str], "angles": list[str],
            ...}``, one dict per test function).

    Returns:
        Dict mapping AC id strings to the set of angle strings claimed for
        that id by at least one test function that also covers it.
    """
    claims: dict[str, set[str]] = {}
    for record in records:
        covers = record.get("covers") or []
        angles = record.get("angles") or []
        if not covers or not angles:
            continue
        for ac_id in covers:
            claims.setdefault(ac_id, set()).update(angles)
    return claims


# ---------------------------------------------------------------------------
# Comparison — pure, iterates the promise set only (the denominator rule).
# ---------------------------------------------------------------------------


def find_unmatched_promises(promises: list[dict], claims: dict[str, set[str]]) -> list[dict]:
    """Return one violation per promised kind that has no matching claim.

    Iterates PROMISES only — never the claim set, and never the full
    permitted-angle vocabulary. An angle that was never promised for a given
    ac_id never appears in the output, for that ac_id or any other (the
    denominator rule: without it the check would demand every permitted kind
    of every piece of work, burying its own signal).

    Args:
        promises: Promise dicts from :func:`extract_promised_kinds`.
        claims: ``{ac_id: {claimed angle, ...}}`` from :func:`build_claim_index`.

    Returns:
        List of ``{"ac_id": str, "behaviour": str, "missing_kind": str}``
        dicts, one per promise with no matching claim. Empty when every
        promised kind has a matching claim (including when *promises* itself
        is empty).
    """
    violations: list[dict] = []
    for promise in promises:
        ac_id = promise["ac_id"]
        angle = promise["angle"]
        if angle not in claims.get(ac_id, set()):
            violations.append(
                {
                    "ac_id": ac_id,
                    "behaviour": promise.get("behaviour", ""),
                    "missing_kind": angle,
                }
            )
    return violations


def format_refusal(violations: list[dict]) -> str:
    """Render violations as human-readable, actionable refusal text.

    Empty *violations* renders as exactly ``"promised and claimed"`` — the
    outcome is established, never worded as reached, proven, verified, or
    done (BP-1100g-4's Wording section). Non-empty renders one line per
    violation naming the ac_id, the behaviour, and the missing kind by name,
    so the reader can go and write the specific missing test — never the
    generic placeholder an implementer writes first.

    Args:
        violations: Violation dicts from :func:`find_unmatched_promises`.

    Returns:
        Human-readable refusal text (or the success wording).
    """
    if not violations:
        return "promised and claimed"
    lines = [
        f"{v['ac_id']}: promised '{v['missing_kind']}' proof for "
        f"\"{v['behaviour']}\" was never claimed by any test — write a test "
        f"tagged '# covers: {v['ac_id']}' and '# angle: {v['missing_kind']}'"
        for v in violations
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI — the only I/O boundary in this module.
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Pre-commit hook: refuse a staged ticket whose promise has no claim.

    Reads each path in *argv* as a staged ticket markdown file, extracts its
    promised kinds, and compares them against the claim side scanned fresh
    from the project's test tree via ``done_proof.collect_test_tag_records``.
    Prints :func:`format_refusal`'s output and exits 1 when any promise has no
    matching claim, 0 otherwise — including when no ticket promises anything
    at all.

    A ticket that cannot be read is reported as a distinct read failure (not
    folded into "a promise had no claim") and also causes a non-zero exit —
    fail-closed on inputs the check cannot account for, without misdirecting
    the fix toward writing a test that was never actually promised.

    Args:
        argv: Staged ticket ``.md`` file paths (the pre-commit
            "pass_filenames" convention). Defaults to ``sys.argv[1:]``.

    Returns:
        0 when every promised kind has a matching claim (or no ticket
        promises anything); 1 when at least one promise has no matching
        claim, or at least one ticket could not be read.
    """
    if argv is None:
        argv = sys.argv[1:]

    all_promises: list[dict] = []
    unreadable: list[tuple[str, str]] = []
    for ticket_path_str in argv:
        ticket_path = Path(ticket_path_str)
        try:
            content = ticket_path.read_text(encoding="utf-8")
        except OSError as exc:
            unreadable.append((str(ticket_path), str(exc)))
            continue
        all_promises.extend(extract_promised_kinds(content))

    for path_str, err in unreadable:
        print(
            f"[check-proof-promise-claim] COULD NOT READ the promise in "
            f"{path_str}: {err} (a read failure, not a missing claim)",
            file=sys.stderr,
        )

    violations: list[dict] = []
    if all_promises:
        project_root = find_project_root()
        records = collect_test_tag_records(project_root)
        claims = build_claim_index(records)
        violations = find_unmatched_promises(all_promises, claims)

    print(format_refusal(violations))

    return 1 if (violations or unreadable) else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(
            f"[check-proof-promise-claim] unexpected error, skipping: {exc}",
            file=sys.stderr,
        )
        sys.exit(0)


# DECISION HISTORY
# ================================================================================
# - 2026-08-26 [python-coder]: Created check_proof_promise_claim.py (BP-1100g-4).
#   The promise side reads only the ## Test Requirements descriptors' angle +
#   covers fields (never a test's own source); the claim side is imported
#   unchanged from BP-1100g-3's collect_test_tag_records (never a second
#   scanner). The promise set is the denominator throughout — an angle never
#   promised for an ac_id is never named in its refusal. No new
#   build_ac_store deploy_map entry was required: done_proof.py and its own
#   dependency test_enforcement.py were already added to AC_STORE_DEPLOY_MAP
#   by BP-1100g-3, so this module's import chain already resolves in the
#   deployed layout — verified by running the deployed hook via run_hook.py
#   after a fresh build.py pass. (#TICKET-20260826-BP-1100g-4)
