---
title: Doc index links use forward slashes on every platform
date: "2026-09-25"
time: "13:00"
type: manual
components: 
  - documentation_system
  - precommit_hooks
summary: docs/INDEX.md is no longer rewritten with backslash paths when a docs change is committed on Windows. Every link in the index on main had been broken this way and is repaired.
description: "scripts/generate_doc_index.py interpolated Path.relative_to() straight into the Markdown, so on Windows every link rendered with backslash separators. The transform-doc-index pre-commit hook calls the same generator on any commit that stages a docs/*.md file, so every docs commit made on Windows rewrote the whole index; it reached main in e3a9b34b (183 of 183 links). Both link-emitting sites now use .as_posix(), and docs/INDEX.md is regenerated with the fixed generator (a separator-only change). A new test, unit_tests/commit_guardian/test_generate_doc_index_posix_paths.py, reproduces the bug on POSIX as well as Windows by substituting PureWindowsPath, and drives the real hook entry point."
breaking: false
---

## Entry

`docs/INDEX.md` on `main` had every link written with Windows backslash separators
instead of forward slashes, so none of them resolved outside Windows.

The cause was the doc-index generator interpolating a `Path` object into the
Markdown. The `transform-doc-index` pre-commit hook runs that generator on any
commit that stages a docs file, so the corruption was not a one-off: every docs
commit made on Windows rewrote the whole index. It had been reverted by hand at
least four times before reaching `main`.

Both places the generator emits a path now use `.as_posix()`, and the index is
regenerated. Branches committed on Windows since the corruption began carry a
broken index too; when they merge `main`, take `main`'s copy of `docs/INDEX.md`.
