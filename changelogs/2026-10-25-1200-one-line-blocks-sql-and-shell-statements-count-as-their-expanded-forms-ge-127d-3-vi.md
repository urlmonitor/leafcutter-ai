---
title: "One-line blocks, SQL and shell statements count as their expanded forms, and joining them costs nothing in the repayment (GE-127d-3-vi)"
date: "2026-10-25"
time: "12:00"
type: manual
components: 
  - commit_guardian
summary: "check-file-size closes the three statement-joining gaps left after GE-127d-3-v. A JavaScript or TypeScript block written on one line (`if (x) { a(); b(); }`) now measures what it measures with its braces and statements on their own lines; object literals still stay one line. SQL statements and shell commands joined with `;` (and shell `then`/`do`/`else` bodies) count once each. A joined statement is keyed with the indentation it would have on its own line, so joining or splitting `if x: y` or a one-line block adds 0 lines to the two-for-one repayment."
description: "GE-127d-3-vi. Every lexer now returns statement breaks as (offset, indent step) pairs, and spans.counted_keys moves a split-off piece's indentation by one language unit per step (four spaces in Python, two elsewhere, named in the _file_size_measure registry). Python: a compound header's body is one level deeper. JavaScript family: a brace pair directly holding a `;`-separated statement is a block, so code after its `{` on the same line splits one level deeper and its `}` splits back; object literals and destructuring (commas, no `;`) and empty blocks are untouched, and type literals whose members end in `;` split like their one-member-per-line form. SQL (sql_lex): code after a `;` outside strings, quoted identifiers and comments splits, inside a lexable dollar-quoted body too. Shell (shell_lex): code after `;` or `;;` splits (a `;` before `then`/`do` keeps the header on its line; before `fi`/`done`/`esac`/`else`/`elif` it steps back a level), and code after `then`/`do`/`else` in command position splits one level deeper; `&&`/`||` lists, quotes and substitutions stay one statement, and a lone splitting `;` is cut from the key. The generated MEASUREMENT RULE now names SQL and shell; README.md, commit_guardian.json and docs/reference/source-file-length-measurement.md carry it. The TypeScript-compiler oracle applies the same block rule to the compiler's tokens; both oracles agree with the measure on every tracked file (3347 .py, 205 JS/TS, 0 disagreements). Measured against main's measure: 50 of 3558 tracked covered files measure higher (all JS/TS one-line blocks), none crosses its limit. GE-127d-3-v's SQL/shell arm and two of its test cases now defer to GE-127d-3-vi. Tests: unit_tests/commit_guardian/test_ge_127d_3_vi.py."
breaking: false
---

## Entry
