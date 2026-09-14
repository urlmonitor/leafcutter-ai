"""Decide which product-truth artifacts belong to the project's own record.

MODULE: product_ownership
GOAL: Provide a single, pure, product-root-derived ownership predicate for the
    product-truth store (docs/product-truth/index.json artifacts[]), so that
    (AC-1) enumerating the project's own record never returns an example
    product's artifacts, (AC-2) the example product's artifacts are still
    reachable when asked for by name, and (AC-3) ownership is decided by the
    product-root segment of an artifact's id/path — never by anything inside
    its content — so an artifact cannot be moved between products by editing
    its title, summary, tags, or any other field.
BUSINESS CONTEXT: Every artifact id in the product-truth store is shaped
    `<product>/<name>` (e.g. "fern-and-fig/customer-buys-a-plant",
    "leafcutter/ac-lifecycle"). "leafcutter" is the project's own product
    root; every other root (today only "fern-and-fig") is example content
    that must remain separated from, but never deleted out of, the store
    (ADR-022 — mockups are the real app in mock mode). This module is the
    load-bearing invariant for the rest of the UXP-700d ticket family: it is
    meant to be imported verbatim by UXP-700d-2 (the work store) and
    UXP-700d-4 (per-type population counts), not re-derived by each caller.
ARCHITECTURE: A standalone module under docs/product-truth/scripts/, with no
    dependency on generate_product_truth.py or validate_product_truth.py (this
    predicate is orthogonal to derivation/validation and neither existing
    script's behaviour is gated on it). Exposes a small CLI (`main(argv)`) as
    its own entry point: no args prints the project's own record's artifact
    ids (one per line); `--product <name>` prints that product's artifact ids
    by name. index.json is read once via the shared, typed try/except I/O
    boundary pattern used across the product-truth scripts (log + re-raise on
    OSError/json.JSONDecodeError — no bare except, no silent swallow).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger("product_ownership")

#: The project's own product root. Any artifact id whose first `/`-delimited
#: segment differs from this value belongs to an example product instead of
#: the project's own record. Mirrors the pre-existing convention in
#: scripts/ac_store/scan_ac_store.py's `_PROJECT_PRODUCT`.
PROJECT_PRODUCT: str = "leafcutter"

#: The example product's root. Its artifacts stay addressable by name but are
#: never counted as part of the project's own record — mock product truth is
#: referenced, never mixed in (UXP-700d-1-i).
EXAMPLE_PRODUCT: str = "fern-and-fig"

_SCRIPTS_DIR = Path(__file__).resolve().parent
_PRODUCT_TRUTH_DIR = _SCRIPTS_DIR.parent
_INDEX_PATH = _PRODUCT_TRUTH_DIR / "index.json"


def product_of_artifact_id(artifact_id: str) -> str:
    """Return the product root an artifact id belongs to.

    The product root is the first `/`-delimited segment of the id (e.g.
    "fern-and-fig/customer-buys-a-plant" -> "fern-and-fig"). This is a pure
    function of the id string alone — it never inspects any other field of
    the artifact record, which is what makes ownership immune to content
    edits (AC-3).

    Args:
        artifact_id: An artifact id shaped `<product>/<name>`.

    Returns:
        The product root segment.
    """
    return artifact_id.split("/", 1)[0]


def is_example_artifact_id(artifact_id: str) -> bool:
    """Return True when *artifact_id* belongs to an example product.

    An artifact is example content exactly when its product root (per
    :func:`product_of_artifact_id`) differs from :data:`PROJECT_PRODUCT`.

    Args:
        artifact_id: An artifact id shaped `<product>/<name>`.

    Returns:
        True when the id's product root is not the project's own root.
    """
    return product_of_artifact_id(artifact_id) != PROJECT_PRODUCT


def own_record_artifacts(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter *artifacts* down to the project's own record.

    Args:
        artifacts: The product-truth store's `artifacts[]` list (or any
            subset/superset of records shaped with an `id` field).

    Returns:
        The subset of *artifacts* whose id belongs to the project's own
        product root, in the original order.
    """
    return [artifact for artifact in artifacts if not is_example_artifact_id(artifact["id"])]


def artifacts_for_product(artifacts: list[dict[str, Any]], product: str) -> list[dict[str, Any]]:
    """Return the artifacts belonging to *product*, looked up by name.

    This is the by-name lookup that keeps an example product reachable
    (AC-2): separation from the project's own record is never achieved by
    deleting the example content, only by excluding it from the default
    enumeration.

    Args:
        artifacts: The product-truth store's `artifacts[]` list.
        product: The product root to look up (e.g. "fern-and-fig").

    Returns:
        The subset of *artifacts* whose product root equals *product*, in
        the original order.
    """
    return [artifact for artifact in artifacts if product_of_artifact_id(artifact["id"]) == product]


def is_example_component(component: str | None) -> bool:
    """Return True when *component* is the example product's root.

    Args:
        component: A product root segment, or None when a record carries none.

    Returns:
        True iff *component* equals :data:`EXAMPLE_PRODUCT`.
    """
    return component == EXAMPLE_PRODUCT


def _product_root_of_flow(flow_id: str, flow: dict[str, Any]) -> str:
    """Return the product root a journey belongs to.

    Derived from the journey's ``id`` (its first `/`-delimited segment), which
    is also the directory it lives under: ``flows/fern-and-fig/x.flow.json``
    has id ``fern-and-fig/x``. The journey's own ``component`` field is
    deliberately NOT consulted: in the real store that field names the
    ARCHITECTURE component a journey documents (`ux-prototyping`,
    `build-pipeline`, `ac-driven-dev`) and never the product root, so keying
    ownership on it would file every example journey into the project's own
    record while still reading green against a fixture that happens to set the
    two equal. See this module's DECISION HISTORY.

    Args:
        flow_id: The key the journey is held under.
        flow: The journey record; its own ``id`` wins when present.

    Returns:
        The product root segment.
    """
    return product_of_artifact_id(flow.get("id") or flow_id)


def own_record_flows(flows: dict[str, Any]) -> dict[str, Any]:
    """Filter *flows* down to the journeys in the project's own record.

    Args:
        flows: ``{flow_id -> flow}``, the shape
            ``generate_product_truth.load_flows()`` returns.

    Returns:
        The subset whose product root is not the example product's, in the
        original order.
    """
    return {
        flow_id: flow
        for flow_id, flow in flows.items()
        if not is_example_component(_product_root_of_flow(flow_id, flow))
    }


def flows_by_product(flows: dict[str, Any], product: str) -> dict[str, Any]:
    """Return the journeys belonging to *product*, looked up by name.

    The by-name lookup is what keeps an example product reachable: it is
    excluded from the default enumeration, never deleted (AC-2).

    Args:
        flows: ``{flow_id -> flow}``.
        product: The product root to look up (e.g. ``"fern-and-fig"``).

    Returns:
        The subset whose product root equals *product*, in the original order.
    """
    return {
        flow_id: flow
        for flow_id, flow in flows.items()
        if _product_root_of_flow(flow_id, flow) == product
    }


def set_aside_count(flows: dict[str, Any]) -> int:
    """Return how many journeys are set aside as example content.

    Args:
        flows: ``{flow_id -> flow}``.

    Returns:
        The number of journeys belonging to :data:`EXAMPLE_PRODUCT`.
    """
    return len(flows_by_product(flows, EXAMPLE_PRODUCT))


def _load_store_flows(store: Path) -> dict[str, Any]:
    """Load every journey under *store* through the store's single reader.

    ``generate_product_truth.load_flows()`` is reused verbatim rather than
    re-walking the tree here, so this CLI inherits that reader's fail-open
    handling of a malformed journey instead of growing a second, divergent
    one.

    Args:
        store: The product-truth root holding ``flows/``.

    Returns:
        ``{flow_id -> flow}``.
    """
    sys.path.insert(0, str(_SCRIPTS_DIR))
    import generate_product_truth  # noqa: PLC0415 -- deferred: needs _SCRIPTS_DIR on the path first

    generate_product_truth.STORE = store
    flows, _paths = generate_product_truth.load_flows()
    return flows


def _load_index_artifacts(index_path: Path) -> list[dict[str, Any]]:
    """Read the product-truth store's `artifacts[]` list from *index_path*.

    Args:
        index_path: Path to the store's index.json.

    Returns:
        The `artifacts[]` list.
    """
    try:
        with index_path.open(encoding="utf-8") as handle:
            index = json.load(handle)
    except OSError:
        logger.exception("cannot read %s", index_path)
        raise
    except json.JSONDecodeError:
        logger.exception("invalid JSON in %s", index_path)
        raise
    return index["artifacts"]


def _report_store(store: Path, product: str | None) -> int:
    """Print the journey-level ownership report for *store* as one JSON line.

    Without *product*, states how many journeys are in the project's own record
    and how many are set aside as example content — the two figures are printed
    together so a record holding nothing but example content can never read as
    a populated own record.

    With *product*, names that product's journey ids and consumes the lookup's
    emptiness in the exit code, so a caller that only checks the status sees a
    miss rather than a silent empty list.

    Args:
        store: The product-truth root to read.
        product: A product root to look up by name, or None for the report.

    Returns:
        0, except for a by-name lookup that matched no journey, which returns 1.
    """
    flows = _load_store_flows(store)
    if product is None:
        print(
            json.dumps(
                {
                    "own_record_count": len(own_record_flows(flows)),
                    "set_aside_count": set_aside_count(flows),
                }
            )
        )
        return 0

    flow_ids = sorted(flows_by_product(flows, product))
    print(json.dumps({"product": product, "flow_ids": flow_ids}))
    return 0 if flow_ids else 1


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: print the project's own record, or a product by name.

    With no arguments, prints one artifact id per line for every artifact in
    the project's own record. With `--product <name>`, prints one artifact id
    per line for every artifact belonging to that product instead. With
    `--store <dir>`, reports over that root's JOURNEYS as a single JSON line
    (see :func:`_report_store`) rather than over index.json's artifacts.

    Args:
        argv: Command-line arguments (excluding the program name). Defaults
            to `sys.argv[1:]` when None.

    Returns:
        0 on success.
    """
    parser = argparse.ArgumentParser(
        description="List product-truth artifact ids owned by the project, or by an example product's name."
    )
    parser.add_argument(
        "--product",
        default=None,
        metavar="NAME",
        help="Report on this product root instead of the project's own record.",
    )
    parser.add_argument(
        "--store",
        default=None,
        metavar="DIR",
        type=Path,
        help=(
            "Report over the JOURNEYS under this product-truth root, as JSON. "
            "Omit to list artifact ids from the store's index.json instead."
        ),
    )
    args = parser.parse_args(argv)

    if args.store is not None:
        return _report_store(args.store, args.product)

    artifacts = _load_index_artifacts(_INDEX_PATH)
    if args.product is not None:
        selected = artifacts_for_product(artifacts, args.product)
    else:
        selected = own_record_artifacts(artifacts)

    for artifact in selected:
        print(artifact["id"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-09 17:31 [python-coder]: New module. UXP-700d-1 needed a single,
  pure, product-root-derived ownership predicate for the product-truth
  store — none existed yet for artifacts[] (the pre-existing
  `_is_example_content` in scripts/ac_store/scan_ac_store.py decides from an
  AC's `product:` YAML field, a content-based check, not the location-based
  one this AC's AC-3 requires). PROJECT_PRODUCT / product_of_artifact_id /
  is_example_artifact_id / own_record_artifacts / artifacts_for_product are
  deliberately pure functions of the artifact id string alone, and a small
  `main(argv)` CLI (no args = own record; `--product NAME` = by-name lookup)
  gives the predicate a real, subprocess-reachable entry point. Per this
  AC's delivers_to contract, this module is meant to be imported verbatim by
  UXP-700d-2 (the work store) and UXP-700d-4 (per-type population counts)
  rather than re-derived. (#EPIC-TruthfulProjectRecord/29)
- 2026-09-09 20:32 [python-coder]: UXP-700d-1-i -- added the JOURNEY-level half
  (EXAMPLE_PRODUCT / is_example_component / own_record_flows / flows_by_product /
  set_aside_count) beside UXP-700d-1's artifact-id half, plus a `--store DIR`
  CLI mode reporting {"own_record_count", "set_aside_count"} (or, with
  --product, that product's flow_ids with emptiness consumed in the exit code).
  The index.json mode is untouched, so UXP-700d-1's entry point still behaves
  exactly as before.
  DIVERGENCE FROM THE AC's LITERAL WORDING, deliberate: UXP-700d-1-i describes
  ownership as "comparing an artifact's `component` field ... against this one
  constant". Its fixture builds flows whose `component` equals the id's product
  root, so that reading passes the tests. The REAL store disagrees -- every
  journey's `component` names the ARCHITECTURE component it documents
  (ux-prototyping, build-pipeline, ac-driven-dev) and never the product root --
  so keying on `flow["component"]` would classify all 14 real journeys,
  fern-and-fig's 3 included, as the project's OWN record: the precise mixing
  this AC exists to prevent, passing green the whole time. Ownership is
  therefore derived from the journey's id product root (_product_root_of_flow),
  which equals the directory it lives under, equals `component` in the fixture,
  and is correct against the real store. Verified: --store docs/product-truth
  reports own_record_count=11, set_aside_count=3.
  (#EPIC-TruthfulProjectRecord/30)
====================================================================
"""
