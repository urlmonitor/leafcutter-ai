---
title: "Reference: Generated files_touched from declared_files"
description: "Lookup reference for how the ticket generator builds files_touched: from the declared_files list when a record declares its files (TKT-600a-3), or labelled derived, not declared, for a legacy record (TKT-600a-3-i). The field itself is defined in ac-schema.md."
type: reference
status: active
created: 2026-10-12
last_updated: 2026-10-12
components:
  - ac_store
  - ac_driven_dev
related_docs:
  - docs/reference/ac-schema.md
  - docs/reference/ac-readiness-and-assignment-gates.md
  - docs/architecture/adrs/ADR-026-ac-driven-build-v2-phased-migration.md
  - config/ac_store_schema.json
  - scripts/ac_store/declared_files.py
  - scripts/ac_store/_gtfa_declared_surface.py
---

# Generated `files_touched` from `declared_files`

> **Parent document:** [ac-schema.md](ac-schema.md)

The `declared_files` field (entry shape, markers, path rules, the "no declared files"
state, refusals and reports) is defined in
[ac-schema.md, The `declared_files` Field](ac-schema.md#the-declared_files-field) and
nowhere else. This page covers only what the ticket generator does with it.

---

## Generated `files_touched` for a record that declares its files (TKT-600a-3)

When an AC declares its files, the ticket generator
(`scripts/ac_store/generate_ticket_from_ac.py`) takes `files_touched` from the
declared-files seam (`scripts/ac_store/declared_files.py`, ACD-1600c-4) and from
nothing else. The generator never parses `declared_files` itself.

- **Exact list, declared order.** `files_touched` is the seam's paths exactly as
  declared: no prose harvesting, no `doc_links`, no `reference_file_path`, and no
  sort or de-duplication. Regenerating from the same record gives a byte-identical list.
- **Existence filter does not apply.** A path declared `to_be_created` is emitted
  although absent on disk. The on-disk filter and bare-directory rejection
  (TKT-600a-1) apply only to the derived surface of a record in the 'no declared
  files' state, which keeps the old derivation, visibly marked (TKT-600a-3-i).
- **Frontmatter stays flat.** `files_touched` remains a flat list of repo-relative
  path strings, so `ticket_frontmatter_guard`, the epic-supervisor file-overlap gate
  and change-scope-reviewer read it unchanged. No new frontmatter key is added.
- **Marker and provenance live in the body.** The ticket carries a `## Files Touched`
  section with one line per path, marking a `to_be_created` path as a file the work
  creates.
- **`--verify` report.** One line per path, naming the marker and the declared-files
  list of the record as its source. The count-only line
  `files_touched has N path(s) from doc_links` is not emitted for a declaring record.


---

## Generated `files_touched` for a legacy record ('derived, not declared') (TKT-600a-3-i)

A record in the "no declared files" state keeps the previous derivation (TKT-600a-1
selection rules, unchanged: `doc_links` entries, `it_requirements.reference_file_path`,
and path-like prose bullets). The result is labelled, never presented as declared.

- **Ticket body.** `## Files Touched` opens with the sentence "Files touched were derived
  from documentation links and technical requirements rather than declared (record
  `<id>`)", then one line per path: ``- `path` — derived from <source>``. The word
  "declared" is never applied to a derived path.
- **Source per path** is one of `doc_links (<relationship>)`, `doc_links`,
  `it_requirements reference_file_path` or `it_requirements prose bullet`.
- **`--verify` report.** An INFO line "files_touched surface for `<id>` is derived, not
  declared (...)" plus one INFO line per path naming its source. Never a PASS. An empty
  derived list is a WARN ("coder has no file-scope signal").
- **No refusal.** The generator does not refuse such a record; the only gate that holds it
  is the implementation-readiness gate ([hold reasons](ac-readiness-and-assignment-gates.md#hold-reasons)).
- **Frontmatter** `files_touched` is the same flat list of path strings as before.

Implementation: `scripts/ac_store/_gtfa_declared_surface.py` (`declared_paths`,
`surface_section`, `report_lines`).

---

## See Also

- [ac-schema.md](ac-schema.md#the-declared_files-field) - the definition of `declared_files`.
- [ac-readiness-and-assignment-gates.md](ac-readiness-and-assignment-gates.md) - hold reasons built on the field.
- [ADR-026](../architecture/adrs/ADR-026-ac-driven-build-v2-phased-migration.md) - warn-before-required rollout and the `schema_version` < 2 exemption.
- `scripts/ac_store/declared_files.py` - the seam implementation.
- [KI-ACS-002](../known-issues/ac-store/open-high-ki-acs-002.md) - the problem the generated surface closes.
