---
title: "Reference: How Example Content Is Kept Apart From the Project's Own Record"
description: "The rule that decides which product an artifact or acceptance criterion belongs to (the product root, never the content), every surface that honours the separation and what each returns for example content, why the example content must keep existing, and how to add a new example artifact or a new example product."
type: reference
status: active
created: 2026-09-25
last_updated: 2026-09-25
components:
  - ux_prototyping
  - documentation_system
related_docs:
  - docs/architecture/adrs/ADR-022-mockups-are-the-real-app-in-mock-mode.md
  - docs/architecture/adrs/ADR-044-example-content-self-declares-its-product.md
  - docs/acceptance-criteria/ux-prototyping/UXP-550-atlas-mock-mode/UXP-593.yaml
  - docs/how-to/authoring-product-truth-artifacts.md
  - docs/how-to/product-truth-schema-reference.md
  - docs/reference/ac-schema.md
  - docs/architecture/components/ux-prototyping.md
related_code:
  - docs/product-truth/scripts/product_ownership.py
  - scripts/ac_store/scan_ac_store.py
  - docs/product-truth/scripts/validate_product_truth.py
  - scripts/seed_example_product.py
---

# How Example Content Is Kept Apart From the Project's Own Record

One example product, **fern-and-fig**, ships inside the product-truth store and the
acceptance-criteria store so the tooling has something to demonstrate against. This
document states the rule that decides which product an artifact or criterion belongs
to, lists every surface that honours that rule and what each one returns for example
content, states why the example content must keep existing, and states how to add to
it.

---

## The ownership rule

An artifact or acceptance criterion belongs to a product because of **where it lives
or what it points to — never because of anything written inside it.**

For the product-truth store (`docs/product-truth/{flows,mock-data,mockups}/`), the
rule is literal: an artifact's id is shaped `<product>/<name>`
(e.g. `fern-and-fig/customer-buys-a-plant`, `leafcutter/ac-lifecycle`), and the
**product root is the id's first `/`-delimited segment**. `leafcutter` is the
project's own root; every other root (today only `fern-and-fig`) is an example
product. This is decided by a single pure function,
`product_ownership.product_of_artifact_id`, from the id string alone — it never
reads the artifact's title, summary, tags, or any other field, which is what makes
ownership immune to content edits: editing a title cannot move an artifact between
products.

**The acceptance-criteria store has no product-root directory.** ACs are organised
by component and topic (`UXP-210-buy-a-plant`, `UXP-220-track-an-order`), not by
product, so "the product root it lives under" has no direct meaning for a
criterion. An example criterion instead carries an `example_product` key naming
its product's root slug directly on the record — but that declaration is not
itself the authority. It is checked against the product root of every
`doc_links` entry on the same AC whose `relationship` is `implemented-by-step`
(the entries that describe the product-truth artifact the criterion is about; any
other relationship, such as `context` or `related`, is a citation and is never
consulted for ownership). The root still decides; the declaration is what a
reader holding only the AC file can go by, and the declaration is what gets
checked, never the reverse. See
[ADR-044](../architecture/adrs/ADR-044-example-content-self-declares-its-product.md)
§§1-3 and §6 for the full rule, and the "Ownership predicate" section of the
[product-truth schema reference](../how-to/product-truth-schema-reference.md) for
the `product_ownership.py` symbol table.

---

## Surfaces that honour the separation

| Surface | Mechanism | What it returns for example content |
|---|---|---|
| **The project's own record** — `docs/product-truth/index.json`'s `artifacts[]` | `product_ownership.own_record_artifacts()` / the no-argument CLI (`python docs/product-truth/scripts/product_ownership.py`) | None, by default. Still fully returned when asked for by name: `product_ownership.artifacts_for_product(artifacts, "fern-and-fig")` / `--product fern-and-fig` on the same CLI. |
| **The store of work** — the AC-store ready-leaf scan | `scripts/ac_store/scan_ac_store.py`'s `_is_example_content()` filter, applied before the ready/blocked classification | None, in either the ready set or the blocked set — an example criterion never becomes dispatchable work, even after a blocker clears. The scan's JSON output states how many criteria it excluded via `set_aside_count`, so the exclusion is visible rather than silent. Each set-aside criterion remains individually loadable and still describes fern-and-fig — set-aside is not deletion. |
| **The reading surfaces** — anyone or anything that loads one artifact or one AC on its own, with no knowledge of where it came from | Presence of the `example_product` key on the record itself (ADR-044 §1-3, §8) | The record's own content states the product it belongs to and that the product is an example (`example_product: fern-and-fig`); a project-owned record carries no such key at all. `docs/product-truth/scripts/validate_product_truth.py`'s commit-time `[example]` check cross-checks every declaration against the product root (§6 above) and reports a mismatch, an undeclared example item, or an item that declares the project's own root, naming both values. The Atlas UI is meant to read the same presence test and label the item accordingly — this is the consumer named in `UXP-700d-3`'s `delivers_to` contract to `frontend-coder` — but that labelling had not yet landed as of this writing; check the Atlas frontend for the current state before relying on a UI label. |

---

## The example content is required to keep existing

Separation is never achieved by deletion. Two decisions in this project depend on
fern-and-fig continuing to exist and remaining referenceable by name:

- [ADR-022 — Mockups Are the Real Application in Mock Mode](../architecture/adrs/ADR-022-mockups-are-the-real-app-in-mock-mode.md)
  depends on the example content continuing to exist: it is what demonstrates the
  mockup-is-the-real-app-in-mock-mode model, and every one of the store's ten
  mockups is fern-and-fig today.
- [`UXP-593`](../acceptance-criteria/ux-prototyping/UXP-550-atlas-mock-mode/UXP-593.yaml)
  — a person can review the whole Atlas in mock mode from bundled fixtures, with no
  live repo — depends on the bundled fixture content existing and staying
  resolvable; its own `covered_by` chain includes
  [`UXP-554`](../acceptance-criteria/ux-prototyping/UXP-550-atlas-mock-mode/UXP-554.yaml),
  which names this same dependency directly.

Do not read the exclusions in the section above as a plan to remove fern-and-fig
from the record. `own_record_artifacts()`, the ready-leaf scan, and the reading
surfaces all keep the example content in place; they only stop it from being
returned, dispatched, or mistaken for the project's own work by default.

---

## Adding to the example content

### Adding a new example artifact to fern-and-fig (a flow, mockup, or mock-data record)

Follow [How to author a Flow, Mockup, or Mock Data artifact by hand](../how-to/authoring-product-truth-artifacts.md)
Part 3, and set `example_product: fern-and-fig` on the new artifact (never `null`
or an empty string — omit the key entirely instead, on the project's own
artifacts). Put the file under the existing `fern-and-fig/` product-root
directory for its artifact kind (`flows/fern-and-fig/`, `mockups/fern-and-fig/`,
`mock-data/fern-and-fig/`) so the id-derived product root agrees with the
declaration. `validate_product_truth.py` cross-checks the two and fails the
commit gate, naming both values, if they disagree.

### Adding a new example acceptance criterion

Author the AC under whichever component/topic directory fits its subject (ACs are
not organised by product), set `example_product: fern-and-fig` on the record, and
give it an `implemented-by-step` `doc_links` entry into the fern-and-fig
product-truth artifact it describes. That link is what lets the commit-time
checker cross-check the declaration (see "The ownership rule" above); an example
AC authored without one is not cross-checked at all — the declaration is trusted
but nothing verifies it (ADR-044 Consequences, Negative).

### Adding a new example product (a product other than fern-and-fig)

Not supported today without a code change. `product_ownership.EXAMPLE_PRODUCT` is
a single string constant (`"fern-and-fig"`), not a set, and every consumer that
decides whether a root is an example root — `validate_product_truth.py`'s
`[example]` check and `scripts/seed_example_product.py`'s product-name validation
— compares against that one constant. Introducing a second example product
requires widening `EXAMPLE_PRODUCT` to a collection and updating every place that
compares a root against it as a single value; this is a code change to the
ownership predicate itself and needs its own ticket, not a hand-edit alongside
new content. `scripts/seed_example_product.py` is a related but distinct
mechanism: it copies the package's own fern-and-fig content into a project that
installs leafcutter, and does not create a new example product inside this repo.

---

## See Also

- [How to author a Flow, Mockup, or Mock Data artifact by hand](../how-to/authoring-product-truth-artifacts.md) — the add-vs-create protocol and the `example_product` step referenced above.
- [Product-truth schema reference](../how-to/product-truth-schema-reference.md) — the "Ownership predicate" section documenting every `product_ownership.py` symbol.
- [Reference: AC Schema](ac-schema.md) — the `example_product` AC field, documented in the field table.
- [ADR-022 — Mockups Are the Real Application in Mock Mode](../architecture/adrs/ADR-022-mockups-are-the-real-app-in-mock-mode.md) — the decision this document names as depending on the example content's continued existence.
- [ADR-044 — Example Content Declares Its Example Product in One `example_product` Key](../architecture/adrs/ADR-044-example-content-self-declares-its-product.md) — the full decision behind the self-declaration and cross-check rule.
- [ux-prototyping component doc](../architecture/components/ux-prototyping.md) — the store layout the ownership rule applies to.
- `docs/product-truth/scripts/product_ownership.py` — the ownership predicate.
- `scripts/ac_store/scan_ac_store.py` — the ready-leaf scan's `_is_example_content()` filter and `set_aside_count`.
- `docs/product-truth/scripts/validate_product_truth.py` — the `[example]` commit-time cross-check.
