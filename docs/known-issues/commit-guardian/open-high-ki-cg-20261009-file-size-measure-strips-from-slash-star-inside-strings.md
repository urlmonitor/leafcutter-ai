---
title: "KI-CG-20261009-file-size-measure-strips-from-slash-star-inside-strings — check-file-size's line measure treats any `/*` as a block-comment opener, including one inside a string, glob or line comment, and drops every line up to the next `*/`"
description: "high — _file_size_ratchet.py's shared measure (count_content_lines → _strip_unmeasured_regions) removes block comments with one language-blind regex, /\\*.*?\\*/ with DOTALL, applied to every checked extension. A `/*` inside a JS string, a path glob such as scripts/commit_guardian/*.py, a `//` or `#` comment, or a Python string opens a false span that runs to the next `*/` anywhere later in the file (often the `*/` inside a `**/` glob). On origin/main fd9a5b4a4, 16 covered files lose 870 lines this way; finalize-feature.js alone measures 1622 where the string-aware count is 1986 (364 lines uncounted), and tests/knowledge/test_native_decision.py measures 332 against a 400 limit when it is really 459. Absolute limits are under-enforced, and a ratchet delta is wrong whenever an edit adds, removes or moves a `/*` or the `*/` that closes the false span."
type: reference
category: reference
status: active
created: '2026-10-09'
last_updated: '2026-10-09'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20261009-file-size-measure-strips-from-slash-star-inside-strings — `check-file-size`'s line measure treats any `/*` as a block-comment opener, including one inside a string, glob or line comment, and drops every line up to the next `*/`

- **Severity:** high. This is silent wrong behaviour in a blocking gate. The measured length
  the gate compares and quotes in its refusals can be hundreds of lines short, and nothing
  reports it. A file over its limit can read as compliant. An edit that only touches a glob
  string can change the measured length by tens of lines in either direction, so the growth
  ratchet can refuse a shrink or wave through a growth.
- **Status:** open, no AC. It affects the GE-127a-1 crossing refusal and the GE-127b-1 growth
  ratchet, and also `count_added_measured_lines` (GE-127f-2), which uses the same transform.
- **Occurrences:** 1 (reported by an agent on PR #1082, 2026-10-09, for
  `templates/workflows-js/finalize-feature.js`).
- **First seen:** 2026-10-09 · **Last seen:** 2026-10-09
- **Where:** `templates/scripts/commit_guardian/_file_size_ratchet.py` (the deployed copy is
  under `.leafcutter/scripts/commit_guardian/`). `_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/\r?\n?",
  re.DOTALL)` (`:78`) is applied by `_strip_unmeasured_regions` (`:173-197`). That function is
  called by `count_content_lines` (`:200-221`) and `count_added_measured_lines` (`:224`). The
  regex runs on the whole file text whatever the extension. There is no per-language branch,
  and no tracking of strings, template literals, regex literals or line comments.

## Correction to the report

The report said the trigger is a `/*` inside a JS string literal. That is one trigger, but the
defect is wider. The regex knows nothing about any language, so any `/*` opens a span:

- inside a JS or TS string or template literal (`"docs/acceptance-criteria/**.yaml"`);
- inside a `//` line comment. The 364-line loss in `finalize-feature.js` starts in a `//`
  comment at `:1124`, not in a string;
- inside a Python string or `#` comment, and in `.sh` files. Neither language has `/* */`
  comments, so **every** match in a `.py` or `.sh` file is false.

The span closes at the next `*/` anywhere later in the file. A `**/` glob is a common closer
(`'tickets/**/*.md'`, `"**/*.py"`). A lone `/*` with no later `*/` is harmless only until
someone adds one, for example `fast-lane-ship.js:1611` (`changelogs/*.md`).

The two triple-quote regexes in the same function (`:76-77`) are just as language-blind. They
strip `"""…"""` / `'''…'''` from `.js`, `.ts` and `.sh` files too. That was not measured here.

## Repro (2026-10-09, worktree at origin/main `fd9a5b4a4`)

Scripts: `test-logs/ki-size-tmp/repro.py` and `test-logs/ki-size-tmp/scan.py` under the
workspace parent (untracked). Both load `_file_size_ratchet.py` from the worktree's
`templates/` source copy and call the module's own `count_content_lines` and
`_strip_unmeasured_regions`.

Tiny file, eight lines, one real block comment:

```js
const a = 1;
const glob = `scripts/commit_guardian/*.py`;
const b = 2;
const c = 3;
const d = 4;
const e = 5;
/* a real comment */
const f = 6;
```

| | lines |
|---|---|
| total | 8 |
| actual non-comment lines | 7 |
| `count_content_lines` | **2** |
| a minimal string-aware stripper | 7 |
| same file with the glob line **deleted** (7 lines) | `count_content_lines` = **6** |

The stripped text reads ``const glob = `scripts/commit_guardianconst f = 6;``. Everything from
the glob's `/*` to the real comment's `*/` was discarded. Deleting one line raises the measured
length from 2 to 6, so a shrink reads as growth.

`templates/workflows-js/finalize-feature.js` at origin/main:

| | lines |
|---|---|
| raw | 2146 |
| `count_content_lines` (what the gate uses) | **1622** |
| string-aware count (real `/* */` and the module's other rules unchanged) | 1986 |
| **uncounted because of the false span** | **364** |

The false span opens at `:1124` (`// non-git-tracked deployed copies (e.g.
scripts/commit_guardian/*.py deployed`) and swallows 364 newlines, up to the `*/` inside
`'tickets/**/*.md'` near `:1488`. Deleting that one comment line changes the measured length
from 1622 to **1643** (+21 for a −1 line edit), because the next `/*` then pairs with a
different `*/`. The `.js` limit is 1000, so the file is over by either count. The ratchet
still runs on a number that is 364 short.

## Effect

- **Absolute limits are under-enforced.** `tests/knowledge/test_native_decision.py` measures
  **332** against the `.py` limit of 400, but **459** once the false span is not stripped. A `**/*.py`
  glob at `:52` pairs with the `**/` in `'**/*.py'` at `:179`, which drops 127 lines. The gate
  treats the file as compliant and lets it grow until the measured figure crosses 400.
- **Most ratchet deltas stay about right, but not all.** Both sides of a before/after
  comparison use the same wrong measure. If an edit does not touch a false span's opener or
  closer, the swallowed lines cancel and the shrink or growth delta is roughly valid. If an
  edit adds, removes or moves a `/*` or the closing `*/`, the delta swings by up to the span's
  length. Example: −1 line read as +21 above. Lines added *inside* a false span are not counted
  as growth at all.
- **Refusal text is wrong.** A refusal quotes the measured length and the published rule
  (`commit_guardian.json` `file_size._comment`: "content inside C-style block comments"). The
  rule describes a comment detector. The implementation is a delimiter regex, so a reader
  cannot reproduce the quoted figure by applying the stated rule.

## Affected files on origin/main

Found by `scan.py` over every tracked file with a checked extension. A span is counted as false
if the file is `.py` or `.sh`, or if its `/*` is not the first token on its line (genuine JSX
`{/* … */}` comments are excluded). 39 files contain at least one false span. In 16 of them
the span crosses a newline, so it changes the measured length. **870 lines in total** are
uncounted:

| uncounted | measured | limit | file |
|---|---|---|---|
| 364 | 1622 | 1000 | `templates/workflows-js/finalize-feature.js` |
| 179 | 57 | 400 | `unit_tests/build_guards/test_doc_index_frontmatter.py` |
| 127 | 332 | 400 | `tests/knowledge/test_native_decision.py` (really over the limit) |
| 113 | 2959 | 1000 | `templates/workflows-js/plan-feature.js` (two spans; first opens at `:455`, `**.yaml`) |
| 18 | 75 | 400 | `leafcutter-web/components/flows/flow-contracts.tsx` |
| 13 | 422 | 400 | `templates/scripts/commit_guardian/check_doc_frontmatter.py` |
| 13 | 9 | 400 | `leafcutter-web/vitest.config.ts` |
| 10 | 722 | 400 | `scripts/knowledge_query.py` |
| 8 | 383 | 400 | `templates/scripts/commit_guardian/doc_validators.py` |
| 6 | 184 | 400 | `unit_tests/suite_performance/test_tq_600a_9_ii.py` |
| 6 | 501 | 400 | `leafcutter-web/lib/data/types.ts` |
| 5 | 297 | 400 | `templates/scripts/commit_guardian/check_documentation.py` |
| 3 | 283 | 400 | `templates/scripts/glossary_detector.py` |
| 2 | 157 | 400 | `templates/doc-compliance/bootstrap.py` |
| 2 | 309 | 400 | `scripts/build_phases_knowledge.py` |
| 1 | 179 | 400 | `templates/scripts/commit_guardian/check_sql_complexity.py` |

In `templates/workflows-js/`, `git grep -nE "[^[:space:]{]/\*"` finds mid-line `/*` in three
files: `finalize-feature.js` (`:1124`, `:1146`, `:1488`, `:1489`), `plan-feature.js` (`:455`,
`:2097`) and `fast-lane-ship.js` (`:1611`, dormant because no `*/` follows it). The other 23
files with false spans lose no lines today, because each span opens and closes on one line.
They lose in-line text only. Any of them starts losing lines once a `*/` appears further down.

## Detection

Run the module's own function on a file, and compare the result with `wc -l` minus the real
comment and docstring lines. Or run `test-logs/ki-size-tmp/scan.py <worktree-root>`, which
lists each false span with the line it opens on. A measured length far below what a reader
counts, or a ratchet verdict that moves when only a glob string changed, is this defect.

## Workaround

None inside the gate. When a file-size refusal or pass looks wrong, check whether the file has
a mid-line `/*` before you trust the number. Do not "fix" a file by adding a `/*` to shorten
its measured length.

## Fix direction

Make stripping depend on the language and stop using bare delimiter regexes:

- **JS / MJS / TS / TSX:** use a small string-aware tokenizer that steps over `'…'`, `"…"`,
  template literals (including nested `${…}`), regex literals and `//` line comments, and
  removes only real `/* … */`. Alternatively, reuse an existing JS lexer, for example by
  running the repo's own Node toolchain to strip comments, if a Python dependency is not
  wanted. The repro's 30-line `string_aware_count` handles every case above apart from regex
  literals and nested template expressions.
- **SQL:** `/* */` is real there. It needs the same string-awareness for `'…'` literals.
- **Python:** no block comments at all. Strip docstrings with the `tokenize` module (`STRING`
  tokens in docstring position), not with a triple-quote regex.
- **Shell:** strip neither.

Keep the GE-127d-2 invariant: one transform, applied to both the previous and the current
content. `describe_measurement_rule()` is generated by probing, so it will follow the change.
The hand-written `file_size._comment` in `commit_guardian.json` and the README rule text will
not, and must be updated. Expect measured lengths of the 16 files above to rise, and
`test_native_decision.py` to start reading as over its limit (grandfathered by the ratchet,
since both sides change together).

**Pattern:** a measurement that recognises syntax by delimiter regex and not by tokenizing.
Its error is largest exactly where the text is about syntax: path globs, comment-stripping
code, and tests of comment strippers.
