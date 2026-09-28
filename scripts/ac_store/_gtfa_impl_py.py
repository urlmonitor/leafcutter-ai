#!/usr/bin/env python3
"""
MODULE: _gtfa_impl_py
GOAL: Own — once, for every AC-to-ticket generator — the question "does this
    ticket's ``files_touched`` put an implementation ``.py`` in scope?", and the
    emission consequence that follows from the answer: whether a generated
    ticket carries a ``## Test Requirements`` section, and which implementation
    file each stub in that section names.
BUSINESS CONTEXT: The presence or absence of ``## Test Requirements`` is the
    authoritative signal the ticket-supervisor reads to decide whether the
    test-writer phase is required (TKT-500f-6, TKT-500f-6-iii-a). A signal is
    only worth reading if it is reliable in BOTH directions: emitted when an
    implementation file is genuinely in scope, and silently absent when one is
    not. Two generators produce tickets — the direct path
    (``generate_ticket_from_ac.py``) and the goal path
    (``epic_tickets.py``) — and the AC's it_requirements forbid inlining or
    duplicating the predicate in either of them, because a duplicated predicate
    agrees with itself only until the day one copy is edited.
ARCHITECTURE: :func:`is_implementation_python_path` is the SINGLE owner of the
    predicate; nothing else in ``scripts/`` may re-implement it, and
    ``unit_tests/ac_store/test_tkt_500f_6_iii_a.py`` enforces that by AST
    fingerprint — it fails on zero implementations and on two alike. Everything
    else here is a thin fold over that one function.

    The rule is stated normatively in ``docs/reference/ac-schema.md`` under
    "Implementation ``.py`` in scope". That document, not this module, is the
    reconciliation point with the ticket-supervisor template: the supervisor is
    markdown prose and cannot import Python, so the two sides are kept in step
    by SPEC PARITY against that one normative statement, never by a shared
    import across the ``.py``/``.md`` boundary.
"""

from __future__ import annotations

from typing import Any, Iterable

#: Key added to each emitted test descriptor naming the implementation files
#: the stub applies to. A stub that names only a derived unit-test path tells
#: test-writer where to put a file, not what production surface the test has to
#: constrain — which is what makes the section actionable rather than decorative.
IMPLEMENTATION_FILES_KEY = "implementation_files"


def is_implementation_python_path(path: str) -> bool:
    """Return True when *path* names an implementation ``.py`` file.

    THE normative predicate, and the only implementation of it in this
    repository. A path qualifies when ALL of the following hold:

    * it ends in ``.py`` (which also settles the ``.yaml`` / ``.json``
      exclusion — a path cannot end in two extensions at once);
    * no directory component of it is ``docs``;
    * no directory component of it is ``tickets``;
    * its basename matches neither ``test_*.py`` nor ``*_test.py``.

    Pure: no I/O, no filesystem probe, no shared state — so per the repo's
    error-handling policy Rule 4 it carries no ``try``/``except``. A malformed
    entry simply fails the predicate rather than raising.

    Args:
        path: One ``files_touched`` entry, as a repo-relative path string.

    Returns:
        bool: True when the entry is an implementation ``.py`` in scope.
    """
    candidate = str(path).strip().replace("\\", "/")
    if not candidate.endswith(".py"):
        return False
    segments = [part for part in candidate.split("/") if part not in ("", ".")]
    if not segments:
        return False
    if "docs" in segments[:-1] or "tickets" in segments[:-1]:
        return False
    basename = segments[-1]
    if basename.startswith("test_"):
        return False
    return not basename.endswith("_test.py")


def qualifying_implementation_paths(files_touched: Iterable[Any]) -> list[str]:
    """Return the entries of *files_touched* that satisfy the predicate.

    Classification is strictly PER ENTRY and the result is a filter, never a
    unanimity check: one qualifying entry among twenty is still one qualifying
    entry. This is the any-vs-all boundary TKT-500f-6-i exists to pin — an
    implementation that required every entry to qualify would pass the
    single-file case and the all-excluded case and fail only the mixed one.

    Order is preserved and duplicates are collapsed, so regenerating the same
    AC yields a byte-identical stub set.

    Args:
        files_touched: The generated ticket's ``files_touched`` list.

    Returns:
        list[str]: The qualifying entries, de-duplicated, in first-seen order.
    """
    qualifying: list[str] = []
    for entry in files_touched or ():
        if not isinstance(entry, str):
            continue
        if is_implementation_python_path(entry) and entry not in qualifying:
            qualifying.append(entry)
    return qualifying


def requires_test_requirements_section(
    files_touched: Iterable[Any], *, fallback: bool
) -> bool:
    """Decide whether a generated ticket must carry ``## Test Requirements``.

    A ``files_touched`` list that holds at least one qualifying entry requires
    the section; one that holds entries but none qualifying legitimately omits
    it, and that omission is silent — a warning on every docs/config-only
    ticket is how a warning channel becomes noise.

    An EMPTY ``files_touched`` is a third state, and is deliberately not read as
    "no implementation file is in scope". It means the AC declared no edit
    surface the generator could derive anything from, so the classification has
    no evidence either way and must not manufacture a negative: ~70% of the
    real store's coder-assigned records with no authored ``test_spec`` derive an
    empty list. For those the caller's *fallback* — the computed agent map's
    production-code classification, the signal that governed this section
    before the predicate existed — is used unchanged. A section emitted
    unnecessarily is noise; a section silently withheld skips test-writer, which
    is the strictly worse error.

    Args:
        files_touched: The generated ticket's ``files_touched`` list.
        fallback: The verdict to use when *files_touched* is empty.

    Returns:
        bool: True when the section must be emitted.
    """
    entries = [entry for entry in (files_touched or ()) if isinstance(entry, str)]
    if not entries:
        return fallback
    return bool(qualifying_implementation_paths(entries))


def annotate_descriptors(
    descriptors: list[dict[str, Any]], implementation_files: list[str]
) -> list[dict[str, Any]]:
    """Name *implementation_files* on every descriptor in *descriptors*.

    Each stub is annotated rather than a separate per-file stub being appended,
    for two reasons. It keeps "at least one stub entry per qualifying file"
    satisfied by construction — every stub names every qualifying file, so no
    file is left without one — and it leaves the descriptor COUNT and the
    ``angle`` distribution of the emitted plan untouched, which the
    reachability-floor contract (BO-2900g-1) and its real-store sweeps depend
    on.

    A no-op when there is nothing to name, so an AC with no implementation file
    in scope emits exactly the block it emitted before this key existed.

    Args:
        descriptors: The finalised test descriptors, in emission order.
        implementation_files: The qualifying implementation paths.

    Returns:
        list[dict]: New descriptor dicts with the key appended last, so ``name``
        stays first (``check_ticket_test_requirements._TESTS_ENTRY_RE`` matches
        on ``- name:`` and stops matching if the key order changes).
    """
    if not implementation_files:
        return descriptors
    annotated: list[dict[str, Any]] = []
    for descriptor in descriptors:
        if not isinstance(descriptor, dict):
            annotated.append(descriptor)
            continue
        entry = dict(descriptor)
        entry[IMPLEMENTATION_FILES_KEY] = list(implementation_files)
        annotated.append(entry)
    return annotated


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-21 [TKT-500f-6 / -6-i / -6-ii / -6-iii-a]: Created as the SINGLE
  shared classification-and-emission helper the ACs' it_requirements demand.
  Before this the ``## Test Requirements`` gate in ``_gtfa_body`` asked whether
  the COMPUTED AGENT MAP held a production_code producer — the right answer for
  the common case, reached by the wrong question, so an AC whose files_touched
  held nothing but test files and a ``tickets/`` path received a fully populated
  section and an AC whose stubs should have named a production surface named
  only a derived unit-test path.

  Two deliberate boundaries, both of which a later edit is likely to want to
  "simplify" away:

  (1) The empty-files_touched fallback in
      :func:`requires_test_requirements_section`. Reading an empty list as "no
      implementation file in scope" makes the predicate a clean iff and strips
      the section from 769 of the 1,100 coder-assigned, no-test_spec records in
      the real store — measured 2026-09-21. Absence of evidence is not evidence
      of absence here.

  (2) :func:`annotate_descriptors` annotates rather than appends. Appending a
      per-file stub changes the emitted descriptor count and the ``angle``
      distribution, both of which real-store sweeps assert on
      (``unit_tests/ac_store/test_derived_test_reachability_floor.py`` requires
      the criterion-tagged count to equal the AC's Then-clause count).
====================================================================
"""
