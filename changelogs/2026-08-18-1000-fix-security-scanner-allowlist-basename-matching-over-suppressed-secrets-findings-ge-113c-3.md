---
title: "fix(security-scanner): allowlist basename matching over-suppressed secrets findings (GE-113c-3)"
date: "2026-08-18"
time: "10:00"
type: manual
components: 
  - commit_guardian
  - build_pipeline
summary: Fixed a security scanner bug where allowlisting one file could silently hide real secrets findings in every other file with the same name anywhere in the repo, and a second bug where a single malformed allowlist line could disable a rule — or the whole scanner — repository-wide.
description: "scan_secrets.py _is_suppressed compared the finding path's own segments against a slice of ITSELF rather than against the allowlist path, so any allowlist entry with N segments suppressed its rule for EVERY file at depth <= N. Replaced with a real segment-by-segment suffix match (a451db67f). GE-113c-3-v additionally closes a pre-existing hole in the same area: an allowlist entry whose file_path field yields zero path segments (empty, '.', './') was a vacuous suffix of every finding path, so a stray trailing colon disabled that rule repo-wide and a line of '*:' disabled the scanner entirely — measured end-to-end, a file containing an AWS key, a private-key header, a password and a high-entropy token produced 4 findings normally and 0 under '*:'. _load_allowlist now rejects zero-segment and colon-free entries at parse time with a stderr warning naming the file, 1-based line number and offending text, and _is_suppressed carries an independent guard so the invariant holds for direct callers too. Ships with a 33-entry .security-allowlist backfill: re-arming the scanner surfaced 1064 findings the broken matcher had been hiding, all triaged and confirmed to be false positives (npm lockfile sha512 integrity digests, long file-path slugs, test kwarg names, CamelCase class names) with zero credential material. Also amends GE-113c-3-i and -iii, whose criteria described ENTROPY_HIGH findings in .env files that scan_file can never produce, and decouples an unrelated BP-900g-4 test from the live AC store (01494fb4c)."
pr: 463
commits: 
  - a451db67f
  - 537e1a6b2
  - 4dceeba79
  - 01494fb4c
breaking: true
migration_steps:
  - "Audit your .security-allowlist before rebuilding. Any entry of the form RULE:a/b/c:* was previously acting as a repository-wide off switch for that rule at every path depth <= 3, because the path comparison was a no-op. After this upgrade each entry suppresses only genuine segment-suffix matches, so findings that entry was silently hiding elsewhere in your tree will start blocking commits."
  - "Re-run the scanner over your whole repository and triage what appears. Expect the bulk of it in generated artifacts full of base64 hashes — package-lock.json, yarn.lock, poetry.lock — which produce large numbers of ENTROPY_HIGH false positives. Suppress each with a narrow path-qualified glob (RULE:path/to/file:*) rather than a bare filename, which would match that basename at any depth. Read the excerpts before allowlisting: a finding the old matcher was hiding may be real."
  - "Remove any malformed allowlist line. An entry whose file_path field is empty, a single dot, or a dot-slash — for example a rule id followed by a stray trailing colon and nothing else — or a non-comment line containing no colon at all, is now rejected at load time with a warning on stderr and suppresses nothing. Previously such a line silently disabled the rule everywhere. Write an explicit asterisk as the file_path when a repository-wide suppression is genuinely intended."
---

## Entry
