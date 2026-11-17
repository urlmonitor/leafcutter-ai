# Independent DK-300 evaluation

Status: focused acceptance, recognition corpus and the two-case repository gate
passed. One additional repository probe reached the deadline; it is retained below
as a timing limitation. No new full-kernel regression failures were reported.

The evaluator ran the production index, recognizer, scheduler tests and provider
projections independently. The initial strict entity run was 61 passed / 4 failed;
unfinished AC failures were not masked. All 26 leaf ACs have tests, and all 59
original named test specifications resolve to real test functions. The final
independent run, with `AC_ENFORCE_STRICT=1`, passed all 78 cases in 22.05 seconds
with zero failures, skips or errors (`entity-context-independent-final.xml`).
This includes 13 independently added regression cases. A separate recognition
run passed 18/18 cases; all six families had precision and recall 1.0 on that
small labeled corpus (`entity-context-independent-corpus-final.json`).

## Findings sent back to the supervisor and coders

| Finding | Severity | Reproduction and evidence |
|---|---|---|
| Default full repository recognition exhausted its two-second limit before scanning any goal | P1 | `entity-independent-performance-red.xml`; both late AC and qualified symbol gates failed. Original/long/known probes took about 2.003 seconds and returned unavailable. |
| Owner snapshot excluded permitted Python validation dependencies, dropping all AC cards | P1 | Real native reader read 4,619 ACs, while first CLI index reported artifact coverage partial. Coder traced excluded declared-file dependencies to the snapshot's hardcoded directory filter. |
| A configured root absent at build time could appear without invalidating the index | P2 | `entity-independent-regression-red.xml`; new `newpkg/added.py` stayed current and was reported unknown. |
| A configured glossary outside docs/config/tickets was silently ignored | P2 | Same red report; `custom/glossary.md` was permitted and configured but produced no matches. |
| Trailing punctuation created a second unknown lookup for a known qualified symbol | P2 | Initial corpus was 17/18; `pkg/alpha.py::TaskInput.perform.` consumed two lookups. |
| Existing artifact prefixes were emitted for a longer unknown or malformed reference | P2 | `entity-independent-owner-red.xml`; AC and ADR prefix cards accompanied the explicitly different ID. |
| Explicit missing Flow and Ticket references had no owner-specific unresolved state | P2 | Same owner red report; typed Flow/Ticket cases returned no matches. |
| Secret redaction shrink expanded the admitted original caller-text window | P2 | `entity-independent-caller-red.xml`; three newest 4,000-character records should exclude older Zephyr, but it was recognized. |
| A denied Python parse error changed narrow-run coverage/status | P1 | `entity-independent-denied-red.xml`; scoped fingerprint remained stable but global family coverage leaked hidden parse state. |
| A denied AC validation error changed the permitted AC projection | P1 | `entity-independent-native-red.xml`; broad rebuild after corrupting a denied record changed narrow cards and coverage. |

Service test fixture defects were also corrected through the supervisor: an
unsupported OPTIONS request shape, iterating decision-map keys, a fake-provider
rule that never overrode the existing rule, and missing unittest async cleanup.
These corrections preserved the intended security and continuation assertions.
The focused suite verifies the source, matching and permission repairs. The final
explicit CLI build independently produced 9,891 entries with all six families
current and no build limitations (`entity-independent-build-final.json`). The
late-AC and qualified-symbol repository gate passed; the remaining timing caveat
is recorded below instead of being hidden by that passing result.

## Independently verified additional behavior

- Denied content edits leave the narrow fingerprint and retained card snapshots unchanged.
- A one-character meaning limit preserves the complete canonical symbol identity.
- A deadline expiring during resolution starts no further lookup, reports two omitted
  candidates, and preserves `scan_complete=true` after a completed scan.
- Original tests cover Unicode casefold offsets, unchanged 16,000-character goals,
  provider envelope budgets, current data-policy withholding, checkpoint reuse,
  separate later evidence, and negative-control eval failures.
- Newly indexed native Decision and Flow sources are excluded from automatic
  body research. Explicit source selection or resolved entity locators can fetch
  their bodies later, subject to the current read policy. Both planning and direct
  retrieval are checked. This test was added after the supervisor found the
  existing lookalike-precedent regression; it is not claimed as a prior red test.
- An actual Windows symlink could not be created (OS error 1314). The deterministic
  resolved-path escape test ran; this report does not claim an actual OS symlink test passed.

## Live comparison

Automatic approval review rejected the first live comparison because it would send
repository-derived context to Jev without sufficiently specific authorization.
No call occurred from that attempt. A safer experiment was prepared and approved:
only newly authored fictional glossary data and claims, with a fictional repository
label, were sent. No real repository contents, identities, source hashes, user
history or local paths were included.

The synthetic live comparison passed all three expected labels in both arms:
evidence, change, and insufficient_context. It made six actual Jev calls; initial
recognition made zero calls. See `entity-synthetic-intent-live.json` and the audited
six payloads in `synthetic-intent-outgoing.json`. This establishes a small live
integration check, not statistical improvement or real-repository answer quality.

## Final repository probes

The evaluator rebuilt the default index after indexed source and document edits
stopped. There was no environment configuration override. Recognition was then
measured after the supervisor's full regression exited. Each request reads the
index; operating-system filesystem caches were not flushed. Explicit preparation
took several minutes and is outside intake; intake did not rebuild the cache.

| Probe | Result | Wall time |
|---|---|---|
| Original 68-character Leafcutter question | Full scan, three ambiguous `run` symbol cards, one lookup | 1.689 s |
| 1,000 words with `DK-300a-1` near the end | Full scan, exactly the requested AC card, one lookup | 1.685 s |
| Mixed glossary, qualified symbol and AC question | Partial, scan deadline exhausted, no cards | 2.014 s |

All retained the goal verbatim and made zero recognition-stage Jev calls. The
original question did not obtain invented meanings for `leafcutter` or bare
`kernel`: only the ambiguous `run` symbol was recognized. This is honest bounded
recognition, not evidence that the original question now classifies or answers
correctly. The full unmodified results are in `entity-independent-real.json`.

The isolated two-case deadline gate passed in 4.21 seconds: late AC case 1.714 s,
qualified-symbol case 1.605 s (`entity-independent-performance-final.xml`). Five
sequential repeats of the exact mixed question then completed in
1.599/1.549/1.508/1.538/1.512 s, each returning the expected four cards with four
lookups and no model calls (`entity-independent-timing-repeat.json`). These
repeats do not erase the observed deadline miss. The partial result obeyed the
deadline contract; consistent full recognition within two seconds is not a
guarantee established by this experiment.

## Final gates and limits

Completed independently: final strict entity suite (78/78), standalone recognition
corpus (18/18), synthetic live paired intent smoke test (3/3 pairs, six calls),
explicit full-repository build, and two-case default recognition gate (2/2).
The evaluator replaced the previously coder-written real-repository report with
its own final run, including the partial result above.

The supervisor-owned full kernel run had 1,621 passed, 437 passed subtests,
seven skipped and five failures, exactly the recorded baseline failures with no
new failures. See `entity-context-kernel-verified.xml` and the parsed
`entity-context-regression-comparison.json`. These are one analysis-folder
candidate-limit failure and four missing `host.query_build` test-fixture entries.
The full run overlapped final annotation/error-policy edits; affected tests and
the independent 78-case suite were rerun on the final sources. The older
`entity-context-kernel-final.xml` is an intermediate ten-failure run, not the final
regression evidence.

Remaining limitations: small recognition corpus; no real-repository live intent
quality comparison; actual OS symlink creation unavailable; and one observed
default deadline miss. No Anthropic provider was used. The first rejected live
experiment was replaced with an approved synthetic experiment, so no approval
request remains pending.
