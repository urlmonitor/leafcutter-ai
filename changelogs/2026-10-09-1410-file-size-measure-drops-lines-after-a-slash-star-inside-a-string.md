---
title: "Known issue filed: the file-size measure drops every line after a `/*` inside a string or glob"
date: "2026-10-09"
time: "14:10"
type: manual
components: 
  - commit_guardian
summary: "Files KI-CG-20261009-file-size-measure-strips-from-slash-star-inside-strings (high). check-file-size strips block comments with a regex that ignores language, so a `/*` inside a string, path glob or line comment drops every line up to the next `*/`. On main, 16 files lose 870 lines, and one test file reads as under its limit when it is over."
description: "One content commit (e2e17a7c6), documentation only. Adds a high-severity entry to the commit-guardian known-issues register and its index row (Open 76 -> 77). _file_size_ratchet.py's shared measure removes block comments with /\\*.*?\\*/ (DOTALL) on every checked extension, so a /* in a JS string, a glob such as scripts/commit_guardian/*.py, a // or # comment, or any .py or .sh file opens a false span to the next */ in the file. Repro on origin/main fd9a5b4a4: templates/workflows-js/finalize-feature.js measures 1622 against a string-aware 1986 (364 uncounted), and tests/knowledge/test_native_decision.py measures 332 against a 400 limit when it is 459. Fix direction: language-specific, string-aware stripping (a JS tokenizer or lexer, the Python tokenize module, nothing for shell)."
commits: 
  - e2e17a7c6
breaking: false
---

## Entry

**KI-CG-20261009-file-size-measure-strips-from-slash-star-inside-strings** filed as `high`
in `docs/known-issues/commit-guardian/`, with its index row.

`check-file-size` measures length with `count_content_lines`, which removes block comments
using a regex that ignores language. A `/*` inside a JS string, a path glob, a `//` or `#`
comment, or anywhere in a `.py` or `.sh` file opens a false span. Everything up to the next
`*/` in the file is then not counted.

- `templates/workflows-js/finalize-feature.js` measures **1622**. The string-aware count is
  **1986**, so **364** lines go uncounted.
- On main, **16** covered files lose **870** lines in total.
- `tests/knowledge/test_native_decision.py` measures **332** against a limit of 400. Its real
  length is **459**.
- Ratchet deltas are mostly unaffected, because both sides use the same wrong measure. An
  edit that touches a `/*` or its closing `*/` swings the delta. Deleting one line of
  `finalize-feature.js` reads as +21.

No code changes.
