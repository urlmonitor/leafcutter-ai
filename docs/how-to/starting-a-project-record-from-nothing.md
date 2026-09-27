---
title: "How to start a project record from nothing"
description: "For a project that has just installed the tooling and holds an empty product-truth record: what the empty record contains and where each artifact type lives, what the checker reports for an empty record versus a checked-and-sound one, and a worked walkthrough of authoring the first journey, the first example dataset and the first screen."
type: how-to
status: active
created: 2026-09-25
last_updated: 2026-09-25
components:
  - ux_prototyping
  - documentation_system
related_docs:
  - docs/product-truth/README.md
  - docs/how-to/authoring-product-truth-artifacts.md
  - docs/how-to/product-truth-schema-reference.md
  - docs/reference/product-truth-checker-outcomes.md
  - docs/architecture/adrs/ADR-023-product-truth-flow-first-upstream-layer.md
  - docs/architecture/adrs/ADR-044-example-content-self-declares-its-product.md
  - docs/architecture/adrs/ADR-022-mockups-are-the-real-app-in-mock-mode.md
related_code:
  - scripts/build_phases_product_truth.py
  - scripts/seed_example_product.py
  - docs/product-truth/scripts/validate_product_truth.py
  - docs/product-truth/scripts/product_truth_outcome.py
---

# How to start a project record from nothing

You have just installed the tooling into a project that never used it before, and
you have never read this repository. This guide takes you from the empty record the
installer left behind to your first journey, first example dataset and first
screen — each with a worked example — and shows you how to tell "still empty" apart
from "checked and found sound" along the way.

## Prerequisites

- The tooling is already installed into your project — `docs/product-truth/`
  exists, with `index.json`, `README.md`, `flows/`, `mock-data/`, `mockups/`,
  `schemas/`, `scripts/` and `classifier/eval.jsonl` all present. If any of those
  are missing, install/build the tooling first; this guide assumes a fresh,
  installed-but-unauthored record, not a from-scratch install.
- A terminal open at your project's root, with Python available to run the
  checker.
- For the full field-by-field shape of each artifact kind (beyond the worked examples here), keep
  [the authoring how-to](authoring-product-truth-artifacts.md) and the
  [schema reference](product-truth-schema-reference.md) open alongside this guide.

---

## Steps

### Step 1 — See what the empty record contains and where each artifact type lives

Right after install, `docs/product-truth/` looks like this, and nothing under it
has been authored yet:

| Path | What it holds |
| --- | --- |
| `flows/` | **Journeys** — the path a person takes through the product, end to end. Empty: no subdirectories yet. |
| `mock-data/` | **Example data** — the records the journeys' screens are populated from. Empty. |
| `mockups/` | **Screens** — one per screen a journey passes through. Empty. |
| `index.json` | The generated manifest: `artifacts: []`, and every derived lookup (`by_component`, `by_entity`, `by_flow`, `by_ac`) present as an empty object — never missing, so you can tell "no lookup" apart from "empty lookup". |
| `classifier/eval.jsonl` | The classifier's own start-up input, seeded as a valid, zero-row file so the checker has something to open. |
| `README.md` | The introduction the installer writes into the record itself, naming these same three directories and telling you to start with a journey — the same guidance this how-to now walks you through. |
| `schemas/` | The JSON Schema each artifact kind is validated against. |
| `scripts/` | The generator (`generate_product_truth.py`) and the checker (`validate_product_truth.py`). |

`index.json` is **generated, never hand-edited** — you regenerate it after
authoring artifacts (Step 6). Everything else above is either the record's data
(the three artifact directories) or tooling the installer copied in verbatim.

### Step 2 — Read the checker's verdict on the record while it is still empty

Before authoring anything, run the checker once so you know what "empty" looks
like from its point of view:

```bash
python docs/product-truth/scripts/validate_product_truth.py
```

Its last line of stdout is a single JSON object. On a record with zero journeys,
zero example datasets and zero screens, the `outcome` field reads
`nothing-examined`, not `checked-and-sound`:

```json
{"outcome": "nothing-examined", "examined": 0, "unreadable": [], "empty_types": ["flows", "mock-data", "mockups"], "...": "..."}
```

`nothing-examined` means the run completed and found zero errors **because there
was nothing in the record for it to check** — not because it checked the record
and found it sound. The checker exits `0` either way, so this distinction only
exists because the `outcome` field states it in words; see the
[checker-outcomes reference](../reference/product-truth-checker-outcomes.md) for
the full four-value vocabulary and what each value does and does not license you
to conclude. Keep this JSON line in mind — you will run the same command again in
Step 6, once the record holds real artifacts, and compare the two.

### Step 3 — Author the first journey (a Flow)

A journey is the **only artifact that stands on its own** — screens and example
data exist to serve one, so it comes first. Create
`docs/product-truth/flows/<your-product>/<your-journey>.flow.json`, replacing
`<your-product>` with a short slug for your own product (not `fern-and-fig` —
that name is reserved for the separate example product; see Step 7) and
`<your-journey>` with a short slug for this journey:

```json
{
  "id": "your-product/customer-resets-password",
  "component": "your-component-id",
  "name": "Customer resets their password",
  "summary": "A signed-out customer who forgot their password requests a reset link, opens it, and sets a new password.",
  "kind": "user",
  "source": "mock",
  "status": "active",
  "readiness": "draft",
  "version": 1,
  "entities": ["Customer"],
  "steps": [
    {
      "id": "request-reset",
      "label": "Request a reset link",
      "human": "The customer enters their email on the sign-in screen and asks for a reset link.",
      "order": 1,
      "screen": "request-reset",
      "reads": ["Customer"]
    }
  ]
}
```

`component` is the kebab-case component id from your AC store's namespace
registry (`docs/acceptance-criteria/index.yaml`, e.g. `ux-prototyping`) — not
the underscored `components:` ids from `docs/components.json`; the two are
distinct axes and product-truth's `component` field always uses the former.
`id` is `<product>/<name>` and stays stable as the journey grows — only its
`version` and contents change. Leave `implements` off each step until you have
ACs to point it at; the business-analyst (or you, by hand) fills it in later —
see [Part 4 of the authoring how-to](authoring-product-truth-artifacts.md#part-4--never-hand-edit-derived-fields)
for the fields you must never hand-edit.

If `Customer` is not already in `entity_registry` inside `index.json`, add it
there before you regenerate (Step 6) — an entity used by an artifact but
missing from the registry is a hard failure, not a typo the checker silently
tolerates.

### Step 4 — Author the first example dataset (Mock Data)

Create `docs/product-truth/mock-data/<your-product>/<your-dataset>.mock.json`.
This is the data your journey's screens will be populated from — keep the
entity name (`Customer`) consistent with what the journey declared:

```json
{
  "id": "your-product/customers",
  "component": "your-component-id",
  "status": "active",
  "readiness": "draft",
  "version": 1,
  "entities": {
    "Customer": {
      "fields": {
        "id": "string — stable slug",
        "email": "string",
        "reset_requested_at": "string — ISO 8601 timestamp, null when no reset is pending"
      },
      "records": [
        {
          "id": "jamie-lee",
          "email": "jamie.lee@example.com",
          "reset_requested_at": null
        }
      ]
    }
  }
}
```

Do **not** set `example_product` on this dataset — that key exists only on
artifacts belonging to the separate example product (Step 7); omit it entirely
on your own project's data, never write it as `null` or `""`. There is exactly
**one** canonical dataset per entity per component — if a `Customer` dataset
already exists for your component later on, extend it rather than creating a
second one (see [the add-vs-create protocol](authoring-product-truth-artifacts.md#part-2--the-add-vs-create-protocol-mandatory)).

### Step 5 — Author the first screen (a Mockup)

Create `docs/product-truth/mockups/<your-product>/<your-screen>.mockup.json`.
Point `mock_data_ref` at the dataset from Step 4, and use the same `screen` id
your journey step referenced (`request-reset`):

```json
{
  "id": "your-product/request-reset",
  "component": "your-component-id",
  "screen": "request-reset",
  "title": "Request a password reset",
  "summary": "The sign-in screen's forgotten-password state: an email field and a submit action, populated from the Customer whose email is entered.",
  "entities": ["Customer"],
  "source": "mock",
  "renders": null,
  "status": "active",
  "readiness": "draft",
  "version": 1,
  "mock_data_ref": "your-product/customers",
  "provenance": [
    {"action": "authored", "by": "<your name>", "date": "<today's date>", "note": "First screen for the password-reset journey."}
  ]
}
```

`renders: null` is valid — it registers the screen (so the journey step's
`screen` reference resolves) without yet requiring a drawn HTML rendering. Draw
it later and point `renders` at the file when it exists.

### Step 6 — Register, regenerate and validate

1. Add the three new artifacts to `artifacts[]` in `index.json`, and to every
   derived index they belong to (`by_component`, `by_entity`, `by_flow`) — or
   regenerate it:

   ```bash
   python docs/product-truth/scripts/generate_product_truth.py
   ```

2. Run the checker again:

   ```bash
   python docs/product-truth/scripts/validate_product_truth.py
   ```

Compare its last stdout line against the Step 2 baseline. With one journey, one
dataset and one screen authored and no schema errors, `outcome` now reads
`checked-and-sound` instead of `nothing-examined`:

```json
{"outcome": "checked-and-sound", "examined": 3, "unreadable": [], "empty_types": [], "...": "..."}
```

`checked-and-sound` means every check that ran genuinely read at least one
record and found nothing wrong in it — the opposite claim from
`nothing-examined`, which meant the run had nothing to check at all. See the
[checker-outcomes reference](../reference/product-truth-checker-outcomes.md)
for the other two outcomes (`degraded`, `failed`) you may see while you are
still learning the shapes, and what each one does and does not tell you.

### Step 7 — Get a fully worked example, if you want one

Everything above used a minimal, hand-built example. If you would rather see a
**complete, previously reviewed** journey/dataset/screen set before writing your
own, the tooling ships one separately: the `fern-and-fig` example product. It is
**not** part of your project's record and does not arrive by default — a fresh
install leaves your record's `flows/`, `mock-data/` and `mockups/` genuinely
empty of it. You obtain it by asking for it, by name:

```bash
python leafcutter/scripts/seed_example_product.py --product fern-and-fig
```

This copies `fern-and-fig`'s journeys, example data and screens into your
record's three artifact directories, alongside (never replacing) anything you
have already authored. Treat it as read-only reference material, not a starting
point to edit in place — your own artifacts live under your own product slug,
never under `fern-and-fig`.

---

## Verification

```bash
python docs/product-truth/scripts/validate_product_truth.py
```

Expected: exit code `0`, and the last stdout line is a JSON object with
`"outcome": "checked-and-sound"` and `"examined"` equal to at least the number
of artifacts you authored (`3` if you followed this guide exactly once). If you
see `"outcome": "nothing-examined"` instead, the checker did not find your new
files — confirm you ran the generator (Step 6) and that your files are under
`docs/product-truth/flows/`, `mock-data/`, or `mockups/` with the `.flow.json`
/ `.mock.json` / `.mockup.json` suffix.

---

## Troubleshooting

1. **`[pointer]` or an entity-registry error on a fresh artifact.** Either an
   `implements` value points at an AC id that does not exist yet (leave
   `implements` off until it does), or an entity name (e.g. `Customer`) is
   missing from `entity_registry` in `index.json` (add it there, then
   regenerate).
2. **`outcome` stays `nothing-examined` after you authored artifacts.** The
   generator (`generate_product_truth.py`) has not run yet, so `index.json`
   still declares zero artifacts, or your files are misnamed/misplaced — see
   Verification above.
3. **You want to check whether an entity or component already has a
   dataset before creating a second one.** See
   [the add-vs-create protocol](authoring-product-truth-artifacts.md#part-2--the-add-vs-create-protocol-mandatory) —
   duplicating a canonical dataset is the exact synthetic-fixture bug this
   store exists to prevent.

---

## See Also

- [How to author a Flow, Mockup, or Mock Data artifact by hand](authoring-product-truth-artifacts.md) —
  the full field-by-field authoring guide this how-to draws its worked examples
  from, including the mandatory add-vs-create protocol and how to confirm a
  journey's freshness.
- [Product-truth schema reference](product-truth-schema-reference.md) — every
  field of every artifact kind, and the ownership predicate that decides
  project-owned versus example content.
- [What each checker outcome licenses you to conclude](../reference/product-truth-checker-outcomes.md) —
  the full `checked-and-sound` / `nothing-examined` / `degraded` / `failed`
  vocabulary referenced in Steps 2 and 6.
- [Product-Truth Store](../product-truth/README.md) — the store's operational
  README: layout, linkage, validation, and who consumes these artifacts.
- [ADR-023](../architecture/adrs/ADR-023-product-truth-flow-first-upstream-layer.md) —
  why this store exists and how it relates to the acceptance-criteria store.
- [ADR-044](../architecture/adrs/ADR-044-example-content-self-declares-its-product.md) —
  the `example_product` self-declaration rule this guide's Step 4 and Step 7
  both depend on.
- [ADR-022](../architecture/adrs/ADR-022-mockups-are-the-real-app-in-mock-mode.md) —
  why mockups are treated as the real app in mock mode, relevant once you start
  drawing screens beyond the registration stub in Step 5.
- [Documentation Index](../INDEX.md) — repo-wide documentation index.
