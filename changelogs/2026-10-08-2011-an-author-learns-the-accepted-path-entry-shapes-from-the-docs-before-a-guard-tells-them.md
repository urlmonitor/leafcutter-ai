---
title: "An author learns the accepted path-entry shapes from the docs, before a guard tells them (GE-118e)"
date: "2026-10-08"
time: "20:11"
type: manual
components:
  - commit_guardian
  - documentation_system
summary: "The frontmatter reference and the hooks guide now state the one rule for related_docs, related_code and architecture_diagrams, with examples that are executed against the guard and refusals quoted from its real output."
description: "GE-118d settled which frontmatter path entries the guard accepts; nothing an adopter reads said so. The hooks guide described check-doc-frontmatter as checking only path existence of related_docs and related_code, and linked to a reference file that does not exist. templates/docs/architecture/FRONTMATTER.md gains a Path Entry Shapes section stating the rule once for all three fields, adds architecture_diagrams to the field tables where it was missing, and names the bare string as the form for new documents while the single-key mapping stays accepted on equal terms, with no deprecation. templates/scripts/commit_guardian/README.md replaces the old description rather than adding to it, fixes the dead link to point at docs/architecture/FRONTMATTER.md, and adds a short examples subsection. Every example is a fenced yaml accepted or yaml refused block, and every refusal is followed by the line the guard actually prints. Four tests cover it, and the main one executes the documents rather than grepping them: it extracts each example, builds a temp project, runs check_doc_frontmatter.py over it, and asserts the documented verdict and the quoted refusal text. Mutation-checked: replacing one quoted refusal with a paraphrase fails the test with 'quotes a message the guard does not emit'."
breaking: false
---

## Entry

### Changed

- `templates/docs/architecture/FRONTMATTER.md` — new **Path Entry Shapes**
  section; `architecture_diagrams` added beside `related_docs` and
  `related_code` in both field tables.
- `templates/scripts/commit_guardian/README.md` — the `check_doc_frontmatter.py`
  row now states the shape rule in place of "path existence of `related_docs` /
  `related_code`"; its reference link is corrected; a **Path entry shapes**
  subsection carries the examples.

### Added

- `unit_tests/commit_guardian/test_ge_118e.py`, `_ge_118e_fixtures.py` — four
  tests. The examples are run through the guard. The accepted-shape set is read
  from the resolver rather than restated. The path fields are read from the
  guard's own source. The superseded sentence and the dangling link are checked
  directly.

### Not changed

- The guard itself still tells a refused author to consult `docs/FRONTMATTER.md`,
  which does not exist (`KI-BO-031`). That is code, not this documentation, and
  is left for its own criterion.
