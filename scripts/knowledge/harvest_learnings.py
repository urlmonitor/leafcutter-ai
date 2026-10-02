"""
MODULE: harvest_learnings
GOAL: Read unprocessed knowledge_captured events from the emission sink and
    route each to the knowledge surface it names, without ever inventing
    content the emitting agent did not actually write.
BUSINESS CONTEXT: Agents emit learnings via the signoff Sec7 knowledge-capture
    step; this harvester is the batch process that drains those emissions
    into durable, curated knowledge files. A record with no learning text is
    a receipt of a past write, not new knowledge, and must never become a
    placeholder line on a real file (INF-700c-1); a line that is not a valid
    JSON object must never derail the read of the records around it
    (INF-700c-1-i).
ARCHITECTURE: Entry point for the Knowledge System component
    (docs/architecture/components/knowledge-system.md). Reads
    ``debugging/logs/knowledge_emissions.jsonl`` (retained sink per ADR-011)
    and writes via the capture-learning write protocol
    (docs/architecture/adrs/ADR-034-knowledge-write-ownership.md).

harvest_learnings.py — Knowledge emission harvester for leafcutter-ai.

Reads unprocessed ``knowledge_captured`` events from
``debugging/logs/knowledge_emissions.jsonl`` (per ADR-011), invokes the
capture-learning write protocol for each event, marks processed events via
a hash-based state file so re-runs are idempotent, and prints a summary.

Usage
-----
    python scripts/knowledge/harvest_learnings.py [--sink PATH] [--dry-run] [--verbose]
    python scripts/knowledge/harvest_learnings.py --print-sink
    python scripts/knowledge/harvest_learnings.py --status

Options
-------
--sink PATH
    Path to the JSONL sink file.
    Default (AC INF-400c-4-v): the build-time declaration recorded at
    config/knowledge_sink.json beside this deployed script -- the absolute
    path fixed when the package was built into this project. Falls back to
    debugging/logs/knowledge_emissions.jsonl (relative to CWD) only when no
    declaration is present (e.g. an un-built source-tree run).

--state PATH
    Path to the JSON state file tracking processed event hashes.
    Default: debugging/logs/harvest_state.json (relative to CWD).

--print-sink
    Print the resolved absolute sink path (and nothing else) to stdout and
    exit 0. Reads the build-time declaration only -- never opens, creates,
    or stats the sink file itself or its parent directories (AC
    INF-400c-4-v: obtainable without emitting or harvesting).
    AC INF-400c-4-i: when no build-time declaration is present, this REFUSES
    (exit 1, message naming the missing declaration on stderr, nothing on
    stdout) rather than falling back to the historical CWD-relative default.
    This is a deliberate divergence from the ordinary (non-print-sink) run's
    ``--sink`` default, which keeps that fallback -- see the ordinary-run
    Notes below. The four emit surfaces this flag now backs are about to
    depend on it to resolve a single, install-wide destination; a CWD
    fallback here would hand each of them a different answer depending on
    where the invoking agent happens to be standing, which is exactly the
    corpus split those surfaces exist to prevent.

--status
    Print ONE line of JSON -- {"last_run": ..., "sink": ..., "sink_exists":
    ...} -- to stdout and exit 0, ALWAYS (never an error, including
    never-run). Side-effect free: reads the marker only, never creates it,
    its parent directory, or the sink's parent directory (AC INF-700a-2).
    ``last_run`` is the literal sentinel "never-run" when the marker has
    never been written in this tree, else an ISO-8601 UTC timestamp for the
    last COMPLETED (non-status, non-print-sink) run. ``sink_exists`` is a
    fresh stat taken at answer time, never inferred from a past run. This
    answers whether the routing step has run HERE and over WHICH sink; for
    agent-run / capture-attempt counts, see the capture-health report
    instead (INF-700b-3) -- the two never share a figure.

--marker PATH
    Path to the last-completed-run marker (default:
    debugging/logs/harvest_last_run.json). An ordinary run writes/updates
    this on reaching a completed harvest() call, regardless of --dry-run and
    regardless of the resulting exit code; --status reads it.

--dry-run
    Read events and decide routing but do not write to any knowledge surface.

--verbose
    Print each event as it is processed.

Exit codes
----------
0   Drained with nothing left to ROUTE. Read this literally: it does NOT mean
    the sink is empty and it does NOT mean every record was written. Records
    classified `no learning text` are deliberately not written and are NOT
    counted as unroutable, so a run over a corpus that is entirely textless
    exits 0 while writing nothing at all -- which is the current state of the
    real 28-record sink. Always read the summary's `no learning text` segment
    alongside this code; the count is the only thing that distinguishes
    "nothing to do" from "nothing eligible to do".
1   Sink file not found or unreadable. AC INF-400c-4-v extends this same code
    to a declared sink whose DIRECTORY no longer exists at all -- reported as
    STALE, naming the declared path, distinctly from the ordinary
    never-written-to case (directory present, file simply not yet written),
    which still reports this same code without the word "stale". No new
    exit status is introduced for the distinction; only the message differs.
2   State file exists but cannot be parsed (corrupted).
3   Drained with unroutable events left behind (see summary for the
    per-entry_kind breakdown). Distinct from 0 so a caller cannot mistake a
    run that routed nothing because there was unroutable input for a run
    that had nothing to route.
4   The run was not clean: at least one destination write failed, and/or the
    state file could not be persisted. Outranks 3 -- a broken run is more
    urgent than a retained backlog. Both conditions leave the affected events
    retryable, but a state-persist failure additionally means the learnings
    routed by this run WILL be routed (and re-appended) again next run.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import sys
from pathlib import Path
from typing import Any, Callable, cast

logger = logging.getLogger("harvest_learnings")


# ---------------------------------------------------------------------------
# Required sibling modules (extracted seams, GE-127b-1 file-size fix)
# ---------------------------------------------------------------------------


def _load_required_sibling_module(module_name: str, filename: str) -> Any:
    """Load a required sibling module from this file's own directory.

    ``harvest_learnings.py`` is loaded three different ways across this
    codebase (see ``_load_entry_kind_vocabulary_module``'s docstring below
    for the full account): as ``__main__`` via subprocess, and via
    ``importlib.util.spec_from_file_location`` from several pre-existing
    test files that do NOT add ``scripts/knowledge/`` to ``sys.path`` first.
    A bare top-level ``import`` only resolves in the first case, so every
    sibling module this file depends on is instead located relative to
    *this* file's own on-disk path.

    Unlike ``_load_entry_kind_vocabulary_module``, the modules loaded here
    (``harvest_result``, ``sink_resolution``, ``capture_write``,
    ``harvest_cli``, ``harvest_status``) are load-bearing plumbing with no
    degraded fallback --
    a load failure is re-raised rather than swallowed, since there is
    nothing sensible for the harvester to do without them.

    Registers the module in ``sys.modules`` under *module_name* BEFORE
    executing it -- exactly the sequence the pre-existing test bootstrap
    already uses for ``harvest_learnings`` itself. This is not merely
    convention: ``harvest_result.py``'s ``@dataclasses.dataclass`` combined
    with ``from __future__ import annotations`` needs
    ``sys.modules[cls.__module__]`` to exist when the decorator resolves its
    field types, and raises a bare ``AttributeError`` if it does not.

    Raises
    ------
    ImportError
        If the sibling module cannot be located at all (missing file or
        unbuildable spec). Any exception the sibling module itself raises
        while executing (e.g. a syntax or dataclass-resolution error)
        propagates as-is -- this is load-bearing plumbing with no
        degraded fallback, so there is nothing this wrapper can usefully do
        besides let the real failure surface.
    """
    module_path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not build an import spec for {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_harvest_result_mod = _load_required_sibling_module("harvest_result", "harvest_result.py")
HarvestResult = _harvest_result_mod.HarvestResult

_sink_resolution = _load_required_sibling_module("sink_resolution", "sink_resolution.py")

_capture_write = _load_required_sibling_module("capture_write", "capture_write.py")

_harvest_cli = _load_required_sibling_module("harvest_cli", "harvest_cli.py")

_harvest_status = _load_required_sibling_module("harvest_status", "harvest_status.py")


# ---------------------------------------------------------------------------
# State helpers (hash-based idempotency, per ADR-011)
# ---------------------------------------------------------------------------


# The idempotency key, per INF-400b-2-i / INF-400b-2-ii: exactly the fields
# the reconciled record shape requires of every producer. `ticket` and
# `text` are optional and MUST NOT appear here under any spelling -- not
# even as a defaulted-to-empty lookup, which is the substitution path that
# produced the original defect (a constant key component that silently
# discriminated nothing).
_REQUIRED_DIGEST_FIELDS: tuple[str, ...] = (
    "timestamp",
    "agent",
    "component",
    "destination",
    "entry_kind",
)


def _event_hash(event: dict[str, Any]) -> str:
    """Return a stable SHA-256 hex digest for a knowledge_captured event.

    The hash key is built from exactly ``_REQUIRED_DIGEST_FIELDS`` --
    ``(timestamp, agent, component, destination, entry_kind)`` -- the set of
    fields the reconciled record shape requires of every producer
    (INF-400b-2-ii). Optional fields (``ticket``, ``text``) are deliberately
    excluded: they must never contribute to identity, either because they
    carry no discriminating information (``ticket`` is absent from every
    real record) or because they carry content rather than identity
    (``text``). This is stable across file rotation and compaction.

    Pure function: no I/O, no shared-state mutation, so per the project
    error-handling policy it is not wrapped in try/except here. A record
    missing one of the required fields raises ``KeyError`` naming that
    field; the caller (``harvest()``, at the I/O boundary) is responsible
    for catching it, reporting the record's line number, and leaving the
    record unprocessed rather than silently substituting an empty string.

    Raises
    ------
    KeyError
        If *event* is missing any field in ``_REQUIRED_DIGEST_FIELDS``.
    """
    key = json.dumps(
        {field: event[field] for field in _REQUIRED_DIGEST_FIELDS},
        sort_keys=True,
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _is_no_learning_text(event: dict[str, Any]) -> bool:
    """Return ``True`` if *event* carries no real learning content.

    A record is ineligible to be written to any knowledge surface when its
    ``text`` field is absent, ``null``, empty (after whitespace
    normalisation), or is merely a restatement of the record's own
    descriptive fields in the exact shape the deleted harvester placeholder
    used to compose (``"[<entry_kind>] Learning from <ticket>"``). The
    restatement check exists so an emitter cannot undo the deletion of that
    placeholder by inlining the same string as if it were real ``text``
    (INF-700c-1 it_requirements #3).

    Pure function: no I/O, no shared-state mutation.
    """
    text = event.get("text")
    if text is None or not isinstance(text, str):
        return True
    normalized = text.strip()
    if not normalized:
        return True
    entry_kind = event.get("entry_kind", "")
    ticket = event.get("ticket", "")
    placeholder = f"[{entry_kind}] Learning from {ticket}".strip()
    return normalized == placeholder


def _load_state(state_path: Path) -> set[str]:
    """Load the set of already-processed event hashes from *state_path*.

    Returns an empty set if the file does not exist.

    Raises
    ------
    ValueError
        If the file exists but cannot be parsed as a JSON list of strings.
    """
    if not state_path.exists():
        return set()
    try:
        with open(state_path, encoding="utf-8") as fh:
            raw = json.load(fh)
        if not isinstance(raw, list):
            raise TypeError("State file must contain a JSON list of strings")  # noqa: TRY003
        return set(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("State file is not valid JSON") from exc  # noqa: TRY003


def _save_state(state_path: Path, hashes: set[str]) -> None:
    """Persist *hashes* to *state_path* (atomic-style: write then rename).

    The list is sorted so diffs are deterministic.
    """
    tmp_path = state_path.with_suffix(".json.tmp")
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(sorted(hashes), fh, indent=2)
        tmp_path.replace(state_path)
    except OSError as exc:
        logger.warning("Failed to persist harvest state: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Build-time sink declaration resolution (AC INF-400c-4-v)
# ---------------------------------------------------------------------------
#
# The declaration-read, default/staleness/legacy resolution, --print-sink
# handling, and (as of INF-700a-2) the deployed-output-root computation this
# cluster used to hold here now all live in the sibling ``sink_resolution``
# module (loaded above via ``_load_required_sibling_module`` as
# ``_sink_resolution``) -- a cohesive "where things live" concern distinct
# from draining the sink once resolved. See that module's own docstring for
# the extraction rationale.

# ---------------------------------------------------------------------------
# Default capture function (production wiring via capture-learning protocol)
# ---------------------------------------------------------------------------

# The _known_entry_kinds set enumerates the entry_kind values that the
# harvester can route.  Any value not in this set triggers a WARNING log and
# capture_fn is NOT called.  Per INF-400c-2-ii, the event is NOT marked
# processed — it is left out of the idempotency record so a later run (after
# the routing rules are extended) reads and retries it. The backlog stays
# visible via HarvestResult.unroutable_by_kind / skipped_unknown rather than
# growing an unbounded reprocessing loop silently: every run reports it.
#
# AC INF-400c-5: this set is the harvester's half of the single declared
# entry_kind vocabulary at config/entry_kind_vocabulary.json — the emission
# helper (scripts/knowledge/emit_knowledge.py) validates against the same
# JSON declaration via scripts/knowledge/entry_kind_vocabulary.py, and this
# literal set must be kept equal to that declaration's "members" keys (a
# reconciliation test reads this literal frozenset from source and compares
# it against the JSON file — see tests/knowledge/test_inf_400c_5.py). It is
# the union of the pre-INF-400c-5 11 harvester-only kinds with the 16
# route-knowledge classifier target_surface values (4 already overlapped),
# so every previously-routable kind stays routable and every classifier
# label becomes routable too.
#
# AC INF-400c-5-i / DECISION HISTORY (why this frozenset still exists rather
# than being deleted outright): the routability *decision* below no longer
# compares a raw on-disk entry_kind against this frozenset directly -- that
# was the H-2 defect a fast-lane pr-review caught (an event surviving on disk
# under a separator/case variant, e.g. "component_convention" for the
# canonical "component-convention", compared unequal to every member here and
# was misreported as unroutable). The comparison now goes through
# `_resolve_entry_kind_canonical`, which normalises via
# `entry_kind_vocabulary.resolve_canonical` -- the SAME shared function
# `emit_knowledge.py` calls -- against the JSON-declared vocabulary read at
# harvest time, so the write-side and read-side normalisation are provably
# one mechanism, not two hand-kept-in-sync ones. This literal frozenset is
# kept only as (a) the target the reconciliation test above pins the JSON
# declaration against, and (b) a defense-in-depth fallback set for the rare
# case the sibling `entry_kind_vocabulary.py` module or the JSON declaration
# cannot be loaded at all at runtime (see `_resolve_entry_kind_canonical`) --
# in that fallback path there is deliberately no normalisation, since without
# the shared module there is no shared function left to apply.
_KNOWN_ENTRY_KINDS: frozenset[str] = frozenset(
    {
        "adr",
        "agent-frontmatter",
        "architecture-doc",
        "claude-md",
        "claude-md-inline",
        "claude-md-toc",
        "code-comment",
        "explanation",
        "explanation-doc",
        "glossary",
        "how-to",
        "memory-project",
        "memory-reference",
        "memory-user",
        "per-agent-memory",
        "per-folder-readme",
        "reference",
        "reference-doc",
        "retrospective",
        "settings-json",
        "skill-context",
        "skills-config",
        "ticket-body",
    }
)


def _load_entry_kind_vocabulary_module() -> Any:
    """Load the sibling ``entry_kind_vocabulary`` module by file path.

    ``harvest_learnings.py`` is loaded three different ways across this
    codebase: as ``__main__`` via subprocess (Python auto-adds this file's
    own directory to ``sys.path[0]``, so a bare ``import
    entry_kind_vocabulary`` would resolve); via
    ``importlib.util.spec_from_file_location`` from several pre-existing test
    files (``tests/knowledge/test_harvest_learnings.py`` and siblings) that
    do NOT add ``scripts/knowledge/`` to ``sys.path`` first; and, after this
    change, potentially re-executed under a different registered module name
    by more than one of those test files in the same process. A bare
    top-level ``import`` only resolves in the first case and would break
    every pre-existing test using the second -- so instead the sibling module
    is located relative to *this* file's own on-disk path, exactly the
    approach those same test files already use to load this module.

    Returns ``None`` (never raises) if the sibling module cannot be loaded --
    e.g. a non-standard layout where it is genuinely absent -- so the caller
    falls back to a plain, unnormalised membership check against
    ``_KNOWN_ENTRY_KINDS`` rather than crashing the harvest run. External I/O
    (file read), so wrapped and logged per the project error-handling policy.
    """
    module_path = Path(__file__).resolve().parent / "entry_kind_vocabulary.py"
    try:
        spec = importlib.util.spec_from_file_location("entry_kind_vocabulary", module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"could not build an import spec for {module_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except (OSError, ImportError) as exc:
        logger.warning(
            "Could not load sibling entry_kind_vocabulary module at %s: %s -- "
            "entry_kind routing falls back to an unnormalised membership "
            "check against _KNOWN_ENTRY_KINDS.",
            module_path,
            exc,
        )
        return None
    return module


_ENTRY_KIND_VOCAB_MODULE: Any = _load_entry_kind_vocabulary_module()


def _entry_kind_members_for_routing() -> dict[str, Any]:
    """Return the members mapping to validate/normalise an entry_kind against.

    Deliberately built from this file's own live ``_KNOWN_ENTRY_KINDS`` --
    NOT re-read from the JSON declaration at harvest time -- for two reasons:
    (1) ``_KNOWN_ENTRY_KINDS`` is already reconciled against the JSON
    declaration by ``test_every_vocabulary_member_has_a_harvester_routing_rule``
    (tests/knowledge/test_inf_400c_5.py), so it is not an independently
    drifting copy; and (2) ``tests/knowledge/test_harvest_learnings.py``'s
    ``TestExtendedRoutingRulesReroutesPreviouslyUnroutable`` monkeypatches
    the module-level ``_KNOWN_ENTRY_KINDS`` attribute directly to simulate
    the routing table being extended, and expects that patched value to take
    effect on the very next ``harvest()`` call -- reading from the JSON file
    instead would silently ignore that monkeypatch and break an existing,
    untouched test. Read at call time (not cached at import time) so the
    monkeypatch is honoured.

    Pure function: no I/O, no shared-state mutation.
    """
    return {name: {} for name in _KNOWN_ENTRY_KINDS}


def _resolve_entry_kind_canonical(
    raw_entry_kind: str, members: dict[str, Any] | None
) -> str | None:
    """Return the canonical vocabulary member for *raw_entry_kind*, or ``None``.

    Delegates to ``entry_kind_vocabulary.resolve_canonical`` -- the SAME
    shared function the emission helper (``emit_knowledge.py``) uses -- so a
    separator/case variant already on disk (e.g. a legacy
    ``"component_convention"`` or ``"CLAUDE.md-inline"`` record) is
    normalised identically on both the write and the read path (AC
    INF-400c-5-i it_requirements: "Normalisation must be applied at both the
    emission helper and the harvester read path, from one shared function").
    A normalised value that still matches no member returns ``None``:
    normalisation never invents a member.

    Falls back to a bare, unnormalised membership check against
    ``_KNOWN_ENTRY_KINDS`` only when *members* is ``None`` -- meaning the
    sibling module could not be loaded at all (see
    ``_load_entry_kind_vocabulary_module``'s docstring) and there is no
    shared function left to call.

    Pure function: no I/O, no shared-state mutation.
    """
    if _ENTRY_KIND_VOCAB_MODULE is None or members is None:
        return raw_entry_kind if raw_entry_kind in _KNOWN_ENTRY_KINDS else None
    return cast(
        "str | None", _ENTRY_KIND_VOCAB_MODULE.resolve_canonical(raw_entry_kind, members)
    )


# The production capture-learning write path now lives in the sibling
# capture_write module (loaded above as _capture_write) -- see that module's
# docstring for the extraction rationale. Bound to this name so harvest()'s
# default parameter value and this file's own docstrings are unchanged.
_default_capture = _capture_write.default_capture


# ---------------------------------------------------------------------------
# Core harvest function
# ---------------------------------------------------------------------------


def harvest(
    sink_path: Path,
    state_path: Path,
    capture_fn: Callable[[str, str], None] = _default_capture,
    dry_run: bool = False,
    verbose: bool = False,
) -> HarvestResult:
    """Process unhandled ``knowledge_captured`` events from *sink_path*.

    Parameters
    ----------
    sink_path:
        Path to the JSONL sink file (``knowledge_emissions.jsonl``).
    state_path:
        Path to the JSON file that persists processed event hashes.
    capture_fn:
        Callable invoked for each routable event.  Signature:
        ``(learning_text: str, destination_path: str) -> None``.
        Defaults to ``_default_capture`` (production path).
    dry_run:
        When ``True``, decisions are logged but ``capture_fn`` is not called
        and state is not updated.
    verbose:
        When ``True``, log each event at DEBUG level.

    Returns
    -------
    HarvestResult
        Counts of routed, previously processed, and skipped-unknown events,
        plus a per-kind breakdown and the derived ``outstanding`` count
        (INF-700c-2) of text-bearing records not yet durably written.

    Raises
    ------
    SystemExit(1)
        If *sink_path* exists but cannot be read (permissions, a directory
        in its place, or another OS-level read failure).
    SystemExit(2)
        If *state_path* exists but is corrupted.

    Notes
    -----
    INF-400c-4-iv: a sink that does not exist at all is a no-work run, not
    an error. A fresh clone or newly provisioned install has never had
    anything written to the declared sink, and the routing step runs at the
    end of every completed unit of work -- including on trees where nothing
    has been emitted yet. An absent sink is therefore treated exactly like
    an existing-but-empty one (zero lines to read), reported at INFO level
    (never ERROR) with the exact path that was looked for, and produces the
    same zero-record ``HarvestResult`` and the same exit status as the
    empty-sink case. It must never widen into reading some other file (e.g.
    the operational stream) in its place, and must never create the sink or
    its parent directory as a side effect of finding them absent -- both
    are covered by dedicated tests in
    ``tests/knowledge/test_harvest_learnings.py``. A sink that EXISTS but
    cannot be read keeps the pre-existing distinct ``SystemExit(1)``.
    """
    result = HarvestResult()

    # Resolve the entry_kind members mapping once per run (AC INF-400c-5-i):
    # built fresh from the current `_KNOWN_ENTRY_KINDS` (see
    # `_entry_kind_members_for_routing`'s docstring for why it is not
    # re-read from the JSON declaration here), reused for every event's
    # normalisation/routability check below via `_resolve_entry_kind_canonical`.
    entry_kind_members = (
        _entry_kind_members_for_routing() if _ENTRY_KIND_VOCAB_MODULE is not None else None
    )

    # 1. Read sink file
    #
    # Staleness (AC INF-400c-4-v: a build-time declaration whose install was
    # moved by hand names a directory that is no longer there) is detected
    # and reported one layer up, in main(), BEFORE this function is even
    # called -- see _stale_declaration_message(). That detection needs the
    # deployed output root to recompute the current-layout value for
    # comparison, which this lower-level, sink/state-only function
    # deliberately does not take as a parameter (existing direct callers in
    # tests/knowledge/test_harvest_learnings.py construct it with an
    # explicit sink_path and no notion of a build-time declaration at all).
    if not sink_path.exists():
        logger.info("Declared sink not found (no-work run): %s", sink_path)
        raw_lines: list[str] = []
    else:
        try:
            raw_lines = sink_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            logger.exception("Cannot read sink file %s", sink_path)
            sys.exit(1)

    # 2. Load previously processed hashes
    try:
        seen: set[str] = _load_state(state_path)
    except ValueError:
        logger.exception("State file corrupted (%s)", state_path)
        sys.exit(2)

    new_hashes: set[str] = set()

    # enumerate() over raw_lines (from splitlines(), so no trailing newline
    # entry) gives the 1-based line number exactly as it appears on disk,
    # including blank lines -- required so a reported malformed-line number
    # can be used to open the real file at that line (INF-700c-1-i).
    for line_no, raw_line in enumerate(raw_lines, start=1):
        line = raw_line.strip()
        if not line:
            continue

        # Parse JSON line. Two distinct ways a line can fail to be a usable
        # record: it is not valid JSON at all (JSONDecodeError), or it parses
        # but is not a JSON object (e.g. a bare string/number/list/null),
        # which would otherwise raise AttributeError on the .get() calls
        # below. Both are "malformed line" (INF-700c-1-i) -- a line-level
        # condition, never written to a knowledge surface, and the read does
        # not stop: subsequent lines are still processed.
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            logger.warning(
                "Skipping malformed line %d (not valid JSON): %s — %s",
                line_no,
                line[:80],
                exc,
            )
            result.malformed_lines += 1
            result.malformed_line_numbers.append(line_no)
            continue

        if not isinstance(event, dict):
            logger.warning(
                "Skipping malformed line %d (valid JSON but not an object): %s",
                line_no,
                line[:80],
            )
            result.malformed_lines += 1
            result.malformed_line_numbers.append(line_no)
            continue

        # Filter: only knowledge_captured events
        if event.get("event") != "knowledge_captured":
            if verbose:
                logger.debug("Skipping non-knowledge event: %s", event.get("event"))
            continue

        # The record parsed as a valid JSON object and is a genuine
        # knowledge_captured event, but it may still lack a field the
        # idempotency digest requires (INF-400b-2-i). This is distinct from
        # a malformed line -- the line itself is well-formed JSON -- so it
        # is counted in its own bucket, reported with its line number, and
        # the record is left unprocessed (never hashed, routed, or added to
        # the idempotency state) rather than silently hashed on a
        # defaulted-to-empty substitute, which is the mechanism that
        # produced the original defect.
        try:
            h = _event_hash(event)
        except KeyError as exc:
            missing_field = exc.args[0] if exc.args else "<unknown>"
            logger.warning(
                "Skipping event at line %d: missing required digest field %r. "
                "Event stays unprocessed and will be retried once the "
                "producer emits it.",
                line_no,
                missing_field,
            )
            result.missing_required_field_count += 1
            result.missing_required_field_lines.append(line_no)
            # A record that carries a REAL learning and was not written is
            # outstanding, whatever the reason it could not be written.
            # INF-700c-2-ii states the figure admits "no floor, no cap, no
            # exclusion by age, agent, kind or destination" -- and a missing
            # digest field is exactly such an exclusion if we let this
            # `continue` skip the count. Without this the one number the
            # feature exists to make truthful reads 0 while a genuine
            # unwritten learning sits in the sink.
            if not _is_no_learning_text(event):
                result.outstanding += 1
            continue

        # Already processed?
        if h in seen:
            result.previously_processed += 1
            continue

        entry_kind = event.get("entry_kind", "")
        destination = event.get("destination", "")
        ticket = event.get("ticket", "")

        if verbose:
            logger.debug(
                "Processing event: entry_kind=%s destination=%s ticket=%s",
                entry_kind,
                destination,
                ticket,
            )

        # Eligibility check MUST run before entry_kind routing (INF-700c-1
        # it_requirements: classification order is load-bearing). All 28
        # retained real records are simultaneously textless AND
        # unknown-entry_kind; a kind-first check would route every one of
        # them into skipped_unknown and pin the exit code non-zero forever.
        if _is_no_learning_text(event):
            result.no_learning_text += 1
            result.no_learning_by_kind[entry_kind] = (
                result.no_learning_by_kind.get(entry_kind, 0) + 1
            )
            # Log at WARNING like every sibling branch. Without this the
            # bucket is the only classification in the module that is
            # silent on stderr, and over the real 28-record corpus that
            # takes the run from 28 warnings to zero while the exit code
            # goes 3 -> 0. A record deliberately not written is still a
            # record not written, and an operator reading only stderr
            # would see a clean run.
            logger.warning(
                "No learning text in event (entry_kind: %r, destination: %r). "
                "Nothing written; the record is left unprocessed so a later "
                "run re-derives it once a real learning body is emitted.",
                entry_kind,
                destination,
            )
            # NOT added to new_hashes / seen: the classification must be
            # re-derived from the record on every run, per INF-700c-1 (the
            # idempotency state file lives under gitignored debugging/logs/
            # and is not durable across a fresh clone or install).
            continue

        # Route based on entry_kind, normalised through the SAME shared
        # function the emission helper uses (AC INF-400c-5-i it_requirements:
        # "Normalisation must be applied at both the emission helper and the
        # harvester read path, from one shared function"). Without this, a
        # legacy or hand-written record on disk carrying a separator/case
        # variant of a routable kind (e.g. "component_convention" instead of
        # the canonical "component-convention") compared unequal to every
        # member of _KNOWN_ENTRY_KINDS and was misreported as unroutable even
        # though its normalised form IS a known kind (H-2, 2026-09-14).
        canonical_entry_kind = _resolve_entry_kind_canonical(entry_kind, entry_kind_members)
        if canonical_entry_kind is None:
            logger.warning(
                "Unrecognised entry_kind %r in event from ticket %r (destination: %r). "
                "Event stays unprocessed and will be retried on a later run.",
                entry_kind,
                ticket,
                destination,
            )
            result.skipped_unknown += 1
            result.unroutable_by_kind[entry_kind] = (
                result.unroutable_by_kind.get(entry_kind, 0) + 1
            )
            # Outstanding per INF-700c-2-ii: this record carries real text
            # and has not been written anywhere, regardless of whether the
            # routing table can currently place its entry_kind. Counting it
            # here (rather than deriving "outstanding" from
            # skipped_unknown/unroutable_by_kind after the fact) is what
            # keeps a text-bearing-but-unroutable record from being able to
            # hide in either bucket alone.
            result.outstanding += 1
            # Intentionally NOT added to new_hashes / seen: per INF-400c-2-ii
            # an unroutable event must remain retryable, not be silently
            # discarded via the idempotency record.
            continue

        # From here on, use the canonical spelling -- for routing, counting,
        # and the capture-write destination lookup -- since it is "the one
        # form ... used in every report" per INF-400c-5-i, not whatever
        # separator/case variant the on-disk record happened to carry.
        entry_kind = canonical_entry_kind

        # By this point `_is_no_learning_text` has already confirmed `text`
        # is present and carries real content, so it is used verbatim. Per
        # INF-700c-1 it_requirements, there is deliberately NO fallback here
        # — a default that synthesises a stand-in string from the record's
        # descriptive fields is exactly the defect this AC closes.
        # cast, not a runtime check: `_is_no_learning_text` above has already
        # rejected absent / null / blank / self-restating values and issued a
        # `continue`, so by here `text` is necessarily a non-empty str. mypy
        # cannot see across that helper, and adding an `isinstance` branch
        # would be unreachable code asserting an invariant the helper owns.
        # If that helper's contract ever changes, this cast is the line to
        # revisit.
        learning_text = cast(str, event.get("text"))

        if not dry_run:
            try:
                capture_fn(learning_text, destination)
            except OSError:
                # capture_fn already logged the specific error. Record the
                # failure and move on to the next event: one unwritable
                # destination must not abort the whole drain. The event's
                # hash is deliberately NOT added to new_hashes, so the write
                # is retried on the next run — same retention rule as an
                # unroutable event (INF-400c-2-ii).
                result.write_failures += 1
                result.failed_by_kind[entry_kind] = (
                    result.failed_by_kind.get(entry_kind, 0) + 1
                )
                # Outstanding per INF-700c-2-ii: the count follows the
                # write, not the attempt. A write that raised was not
                # persisted, so the record remains unwritten and must stay
                # outstanding on this and every subsequent run until a
                # write actually succeeds.
                result.outstanding += 1
                continue

        result.routed += 1
        result.by_kind[entry_kind] = result.by_kind.get(entry_kind, 0) + 1
        new_hashes.add(h)
        if dry_run:
            # A dry run never calls capture_fn and never persists state (see
            # the persistence step below), so this record is still
            # genuinely unwritten. Only a real (non-dry-run) write that
            # reaches this line has actually captured the learning, so only
            # the dry-run case counts toward `outstanding` here.
            result.outstanding += 1

    # 3. Persist updated state
    #
    # Only when there is something new to record. With new_hashes empty the
    # write is a no-op (seen | {} == seen), so attempting it can only
    # manufacture a failure that costs nothing: nothing was routed, so
    # nothing can be re-routed. Reporting that as a failed run would raise
    # the exit code to 4 and mask the exit-3 backlog signal on precisely the
    # run that most needs it -- an all-unroutable sink, which is today's
    # real corpus.
    if not dry_run and new_hashes:
        try:
            _save_state(state_path, seen | new_hashes)
        except OSError:
            # _save_state already warned with the specific errno. Do not abort
            # -- the learnings were written and that work is real -- but the
            # run is NOT clean: without the state file every hash in
            # new_hashes is forgotten, so the next run re-routes all of them
            # and appends each learning to its destination a second time.
            # Recording this is what stops the caller reading a duplicating
            # run as a successful one.
            result.state_persist_failed = True
            logger.warning(
                "Harvest state was not persisted; the %d learnings routed by "
                "this run will be routed again (and re-appended to their "
                "destinations) on the next run.",
                result.routed,
            )

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
#
# Argument parsing now lives in the sibling harvest_cli module (loaded above
# as _harvest_cli) -- see that module's docstring for the extraction
# rationale.


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the knowledge harvester.

    Returns
    -------
    int
        ``0`` if the run drained cleanly, ``3`` if unroutable events remain
        in the sink (see the printed summary for the per-entry_kind
        breakdown), ``4`` if any destination write failed or the state file
        could not be persisted. ``4`` outranks ``3``: a broken run is more
        urgent than a retained backlog. ``harvest()`` itself may also
        ``sys.exit(1)``/``sys.exit(2)`` for sink/state read failures before
        this function returns.
    """
    args = _harvest_cli.parse_args(argv)

    output_root = _sink_resolution.deployed_output_root()

    # AC INF-400c-4-v: obtainable without emitting or harvesting -- reads
    # the declaration only and returns before anything else (logging setup,
    # the sink-existence check, the legacy-divergence check) can touch the
    # filesystem beyond that one read.
    if args.print_sink:
        return _sink_resolution.handle_print_sink(output_root)

    # AC INF-700a-2: also reads only, exits 0 always, never touches the
    # marker/sink parent directories -- see harvest_status.handle_status.
    if args.status:
        status_sink = _sink_resolution.resolve_sink_for_status(args, output_root)
        return _harvest_status.handle_status(status_sink, args.marker)

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s %(name)s: %(message)s")

    sink_path = _sink_resolution.resolve_sink_or_log_stale(args, output_root)
    if sink_path is None:
        return 1

    _sink_resolution.warn_if_diverging_from_legacy(sink_path, output_root)

    result = harvest(
        sink_path=sink_path,
        state_path=args.state,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )
    # AC INF-700a-2: a completed harvest() call -- i.e. this line was
    # reached, so main() did not hit SystemExit(1)/(2) first -- always
    # updates the marker, regardless of --dry-run and regardless of the
    # 0/3/4 exit code this function returns below.
    _harvest_status.write_last_run_marker(args.marker, sink_path)

    print(result.summary())

    return result.exit_code()


if __name__ == "__main__":
    sys.exit(main())


# DECISION HISTORY
# ================================================================================
# - 2026-08-31 12:00 [python-coder]: Deleted the placeholder-synthesis default for
#   learning_text and added a no-learning-text eligibility bucket, evaluated
#   BEFORE entry_kind routing so a record that is both textless and
#   unknown-kinded (the shape of all 28 retained real records) is never
#   double-counted into skipped_unknown. Also added a malformed-line counter
#   with 1-based line numbers and a not-a-JSON-object guard so a bare JSON
#   scalar line no longer crashes the run with AttributeError. Neither change
#   introduces a new exit code. (#TICKETLESS reason=ac-scoped-fastlane-build-INF-700c-1)
# - 2026-08-31 [python-coder]: Re-keyed `_event_hash` on the reconciled
#   required-field set (timestamp, agent, component, destination, entry_kind)
#   per INF-400b-2-ii's contract, dropping the always-absent `ticket` field
#   that made the digest effectively three-fields-wide (INF-400b-2-i /
#   KI-KM-010). A record missing a required field now raises `KeyError` from
#   `_event_hash` instead of being silently hashed on a defaulted-to-empty
#   substitute; `harvest()` catches it per-record, reports the 1-based line
#   number via new `HarvestResult.missing_required_field_count` /
#   `missing_required_field_lines` counters (distinct from `malformed_lines`
#   per KI-KM-011's separate territory), and leaves the record unprocessed
#   so it is retried once the producer is fixed. No new exit code.
#   CONSEQUENCE (documented per this AC's own it_requirements): changing the
#   key invalidates every digest computed under the old (ticket, timestamp,
#   destination, entry_kind) key -- any state file persisted before this
#   change will no longer recognise its own entries as processed. Harmless
#   for the current real corpus (INF-700c establishes all 28 records are
#   ineligible-to-write, so nothing was ever actually routed under the old
#   key), but deliberate and called out here rather than discovered later.
#   KNOWN COLLATERAL: 15 pre-existing tests in
#   tests/knowledge/test_harvest_learnings.py (all tagged for INF-400c-2 /
#   INF-400c-2-ii, none for this AC) construct events via the `_make_event`
#   helper, which predates INF-400b-2-ii's reconciled record shape and
#   supplies `ticket` but never `agent`/`component`. Those fixtures are now
#   stale relative to the shape INF-400b-2-ii made authoritative (classify:
#   test_drift -- production is correct per the now-`done` INF-400b-2-ii
#   contract; the fixtures were never updated to match it). Per this
#   project's Test Delegation rule, test files are not touched here; flagged
#   for test-writer to update `_make_event` call sites (or migrate them to
#   `_make_bare_event`) to include `agent`/`component`. The fast-lane gate
#   scoped to INF-400b-2-i's own `# covers:` tags is unaffected (verified
#   green + coverage_ok). (#TICKETLESS reason=ac-scoped-fastlane-build-INF-400b-2-i)
# - 2026-09-01 [python-coder]: Added `HarvestResult.outstanding` -- the "still
#   waiting to be written" count INF-700c-2 / INF-700c-2-ii require -- and
#   always print it in `summary()` (including when zero), since "visible is
#   not the same as outstanding" (INF-700c-2 it_requirements #5). The count is
#   derived per-record inside the existing loop, never stored: a record
#   contributes 1 unless it is eligibility-excluded (`no_learning_text`, per
#   INF-700c-1), already watermarked (`previously_processed`), or actually
#   written by this exact (non-dry-run) invocation. Deliberately NOT derived
#   from `skipped_unknown`/`unroutable_by_kind`, so a text-bearing record with
#   an unrecognised `entry_kind` still counts as outstanding -- the
#   anti-cheat boundary INF-700c-2-ii exists to pin. A write that raises
#   OSError leaves the record outstanding (the count follows the write, not
#   the attempt); a dry-run "route" never persists, so it also leaves the
#   record outstanding. No new exit code: `main()`'s 0/3/4 vocabulary is
#   still derived solely from `skipped_unknown` / `write_failures` /
#   `state_persist_failed`. Introduces no corpus identifier, no new runtime
#   state file, and mutates neither the sink nor any destination -- the 28
#   real records reach `outstanding == 0` because the definition of
#   outstanding is corrected, not because they were disposed of.
#   (#TICKETLESS reason=ac-scoped-fastlane-build-INF-700c-2)
# - 2026-09-07 [python-coder]: Added `--print-sink` and re-derived the `--sink`
#   default from the build-time knowledge-sink declaration
#   (config/knowledge_sink.json, written by build_knowledge_sink_declaration
#   in build_phases.py) instead of a hardcoded CWD-relative path, falling back
#   to the historical default when no declaration is present. Added staleness
#   detection (_stale_declaration_message): a declared sink whose install was
#   moved by hand no longer matches what the current layout would recompute,
#   which is reported as STALE (naming the declared path) and reuses exit
#   code 1 rather than a new one, distinctly from the ordinary
#   never-written-to case. Added a one-time legacy-divergence notice
#   (_warn_if_diverging_from_legacy) naming both locations when a
#   pre-existing accumulation differs from the newly adopted declaration.
#   No behaviour change for existing callers that pass --sink explicitly.
#   (#TICKETLESS reason=ac-scoped-fastlane-build-INF-400c-4-v)
# - 2026-09-14 [python-coder/INF-400c-4-i]: Hardened `--print-sink`: with no
#   build-time declaration present it now REFUSES (exit 1, stderr message,
#   nothing on stdout) instead of falling back to `_resolve_default_sink`'s
#   CWD-relative default -- the four shipped emit surfaces depend on
#   `--print-sink` as their single source of truth, so a CWD fallback would
#   reproduce the corpus split those surfaces exist to prevent. Scoped to
#   `_handle_print_sink` only; the ordinary `harvest` run's `--sink` default
#   (INF-400c-4-v) is unchanged. Reuses exit 1, no new code.
#   (#TICKETLESS reason=ac-scoped-fastlane-build-INF-400c-4-i)
# - 2026-09-14 15:10 [python-coder/INF-400c-4]: `_stale_declaration_message`
#   now treats a non-absolute declared value as "nothing to report" instead
#   of misreporting it as install-moved -- that shape is the different
#   resolution-hazard defect INF-400c-4's own parity check already rejects,
#   and never "used to match" an absolute recomputation. Ordinary relative
#   -value handling (resolve against CWD) is unchanged.
#   (#TICKETLESS reason=ac-scoped-fastlane-build-INF-400c-4)
# - 2026-09-14 [python-coder/INF-400c-5-i, H-2 fix]: A fast-lane pr-review
#   found the routing check at the bottom of `harvest()` compared a raw
#   on-disk `entry_kind` directly against `_KNOWN_ENTRY_KINDS` with no
#   normalisation, while `emit_knowledge.py` normalised via
#   `entry_kind_vocabulary.resolve_canonical` before writing -- so a legacy
#   or hand-written record already on disk under a separator/case variant of
#   a routable kind (this AC's own Given clause: "component_convention" vs
#   "component-convention") compared unequal to every frozenset member and
#   was misreported unroutable, even though every OTHER value in
#   `_KNOWN_ENTRY_KINDS` uses the canonical hyphenated-lowercase spelling.
#   Two hand-kept-in-sync mechanisms (a literal frozenset here, a shared
#   function there) reconciled only by a structural test is explicitly not
#   "one shared function" per this AC's own it_requirements. Fixed by adding
#   `_load_entry_kind_vocabulary_module` (loads the sibling module by file
#   path rather than a bare top-level `import`, since several pre-existing
#   tests -- test_harvest_learnings.py and siblings -- load this file via
#   `importlib.util.spec_from_file_location` without putting
#   scripts/knowledge/ on sys.path; a bare import would have broken all of
#   them), `_entry_kind_members_for_routing` (builds the members mapping
#   from the current `_KNOWN_ENTRY_KINDS`, read fresh at each `harvest()`
#   call rather than from the JSON declaration -- an earlier draft of this
#   fix read the JSON directly and broke the pre-existing
#   `TestExtendedRoutingRulesReroutesPreviouslyUnroutable` test, which
#   monkeypatches the module-level `_KNOWN_ENTRY_KINDS` attribute and expects
#   that patched value, not the JSON file, to govern the very next
#   `harvest()` call), and `_resolve_entry_kind_canonical` (calls the SAME
#   `entry_kind_vocabulary.resolve_canonical` the emission helper uses to
#   normalise *before* the membership check, rather than comparing the raw
#   value). The routing check now branches on the canonical value and
#   reassigns `entry_kind` to it before any downstream counting/capture use,
#   so a normalised-but-still-unknown value still correctly routes to
#   `skipped_unknown` (normalisation never invents a member) while a known
#   variant is now routed and reported under its canonical spelling.
#   `_KNOWN_ENTRY_KINDS` is deliberately NOT deleted: it remains the
#   harvester's live, single routing table (now normalised-against via the
#   shared function instead of compared raw), the pre-existing
#   `test_every_vocabulary_member_has_a_harvester_routing_rule`
#   (tests/knowledge/test_inf_400c_5.py) structurally asserts its literal
#   presence and equality with the JSON declaration, and per this project's
#   constraint no existing test is weakened to land a fix. It also serves as
#   an explicit fallback set for the (expected to be rare, and itself the
#   subject of the sibling H-1 deploy-manifest fix) case where the sibling
#   `entry_kind_vocabulary` module cannot be loaded at runtime at all -- that
#   fallback path has no normalisation, since there is no shared function
#   left to call. No new exit code; no change to the idempotency hash
#   (`_event_hash` reads the raw event dict, computed before this
#   normalisation). New coverage:
#   `tests/knowledge/test_inf_400c_5_i_h2_harvester_normalises_variant_on_read.py`
#   writes a variant-spelled `entry_kind` directly into the sink (bypassing
#   the emission CLI, as a legacy record would be) and asserts the real
#   harvester CLI routes it. (#TICKETLESS reason=fast-lane-pr-review-fix-INF-400c-5-i-H2)
