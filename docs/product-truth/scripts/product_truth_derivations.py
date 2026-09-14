"""
MODULE: product_truth_derivations
GOAL: The pure derivations write_index() assembles the store index from.
BUSINESS CONTEXT: Split out of generate_product_truth.py, which the
    UXP-700e-2 summary derivation pushed over its GE-127a-1 limit and so into
    the GE-127b-1 no-growth ratchet. Everything here is a pure function of the
    artifacts it is handed -- no STORE, no filesystem, no module state -- which
    is what makes the index reproducible from the sources on every run rather
    than something maintained by hand.
ARCHITECTURE: Leaf module. generate_product_truth imports and re-exports the
    whole set, so `gpt.build_by_entity`, `gpt.derive_artifact_summary` and the
    rest still resolve for every existing caller and test; nothing imports back,
    so there is no cycle.
"""
from __future__ import annotations



def _without_asof(entry: dict) -> dict:
    """Return *entry* without its ``asof`` key (re-exported from generate)."""
    return {k: v for k, v in entry.items() if k != "asof"}


def build_by_component(artifacts: list) -> dict:
    """Group artifact ids by component and type."""
    type_key = {"flow": "flows", "mock_data": "mock_data", "mockup": "mockups"}
    result: dict[str, dict] = {}
    for artifact in artifacts:
        key = type_key.get(artifact.get("type"))
        if key is None:
            continue
        bucket = result.setdefault(artifact["component"], {"flows": [], "mock_data": [], "mockups": []})
        bucket[key].append(artifact["id"])
    for component in result:
        for key in result[component]:
            result[component][key] = sorted(result[component][key])
    return dict(sorted(result.items()))


def build_by_entity(flows: dict, mocks: dict) -> dict:
    """Map each entity to its canonical mock-data and the flows that use it."""
    result: dict[str, dict] = {}

    def bucket(entity: str) -> dict:
        return result.setdefault(entity, {"canonical_mock_data": {}, "flows": {}})

    for mock in mocks.values():
        for entity in mock.get("entities", {}):
            bucket(entity)["canonical_mock_data"][mock["component"]] = mock["id"]
    for flow in flows.values():
        for entity in flow.get("entities", []):
            flows_by_component = bucket(entity)["flows"].setdefault(flow["component"], [])
            if flow["id"] not in flows_by_component:
                flows_by_component.append(flow["id"])
    for entity in result:
        result[entity]["canonical_mock_data"] = dict(sorted(result[entity]["canonical_mock_data"].items()))
        result[entity]["flows"] = {
            component: sorted(ids) for component, ids in sorted(result[entity]["flows"].items())
        }
    return dict(sorted(result.items()))


def _preserve_entry_asof(new_entries: list[dict], existing_truth: list, run_date: str) -> list[dict]:
    """Return new_entries with asof preserved from existing_truth where content matches.

    For each new entry, locate the stored entry with the same (flow, node) key.
    If the non-asof fields are identical, keep the stored asof; otherwise stamp
    with run_date. This is a pure helper — no I/O.
    """
    if not isinstance(existing_truth, list):
        return new_entries
    existing_by_key: dict[tuple, dict] = {}
    for ex in existing_truth:
        if isinstance(ex, dict):
            key = (ex.get("flow"), ex.get("node"))
            existing_by_key[key] = ex
    result = []
    for entry in new_entries:
        key = (entry.get("flow"), entry.get("node"))
        existing = existing_by_key.get(key)
        if existing is not None and _without_asof(existing) == _without_asof(entry) and "asof" in existing:
            result.append({**_without_asof(entry), "asof": existing["asof"]})
        else:
            result.append(entry)
    return result


#: Longest an index artifact's derived `summary` may run. The authoritative
#: descriptions this is derived FROM run 365-938 characters; the hand-authored
#: index copies this replaces ran 89-218. 200 keeps the index scannable while
#: staying inside the range the store already used (UXP-700e-2).
_ARTIFACT_SUMMARY_LENGTH = 200


#: Appended when a derivation actually had to cut, so a reader can tell a
#: shortened form from one that simply fitted.
_ELLIPSIS = "\u2026"


def derive_artifact_summary(authoritative: str) -> str:
    """Return the short form of *authoritative*, derived rather than authored.

    A description that already fits is returned unchanged — the short form of a
    short description is itself, not a second, differently-worded string.

    A longer one is shortened from BOTH ENDS: how it opens, an ellipsis, and
    how it closes. Not a head-only truncation, because the authoritative text
    is the only place a description is authored and an edit to its final
    sentence must still show up in the short form (UXP-700e-2: "changing the
    authoritative description changes every shorter form"); a prefix cut would
    silently swallow exactly that edit. Both ends are cut at word boundaries so
    the result reads as prose.

    LIMIT, stated rather than implied: this is a lossy shortening, so an edit
    confined to the MIDDLE of a long description can leave the short form
    unchanged. What actually prevents the two from drifting into two
    independent descriptions is the derivation being recomputed on every run
    and the --check gate failing when the stored value differs from a fresh
    one — not this function being injective.

    Args:
        authoritative: The artifact's own, authored description.

    Returns:
        The derived short form.
    """
    text = " ".join((authoritative or "").split())
    if len(text) <= _ARTIFACT_SUMMARY_LENGTH:
        return text

    joiner = f" {_ELLIPSIS} "
    budget = _ARTIFACT_SUMMARY_LENGTH - len(joiner)
    head_budget = (budget * 7) // 10

    head = text[:head_budget]
    boundary = head.rfind(" ")
    if boundary > 0:
        head = head[:boundary]
    head = head.rstrip(" ,;:.")

    tail = text[-(budget - len(head)):]
    boundary = tail.find(" ")
    if boundary != -1:
        tail = tail[boundary + 1:]

    return f"{head}{joiner}{tail}"

"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-10 [python-coder]: Extracted the pure index derivations from
  generate_product_truth.py so that file could come back under its limit after
  UXP-700e-2 added derive_artifact_summary(). Pure move: none of these touched
  module state, so behaviour is unchanged and generate_product_truth re-exports
  them for every caller. (#EPIC-TruthfulProjectRecord)
====================================================================
"""
