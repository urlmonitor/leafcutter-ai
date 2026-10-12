# Publication of closed retrieval evidence

The [Aura baseline](../runs/published-2a8ebc87/review.html) and
[precision stage1](../../retrieval-needs-precision-2026-10-09/stage1/review.html)
are closed evaluations. Their original receipts, HTML, gold, source fingerprints
and closure records are unchanged. The baseline remains 0/3 whole-question
successes despite 3/3 selected-field retrievals; stage1 remains 10/12 finite
interpretation checks. This publication work does not renew either result.

## Historical source versions

[source-preservation.json](source-preservation.json) maps original repository
paths to exact archived source bytes and SHA256 hashes. It preserves the three
Aura helpers, three precision helpers, and two uncommitted runtime files used by
stage1. Each archive matched the closed stage1 runtime fingerprint before the
current helper or runtime source could change. The recorded source is evidence,
not an alternative executable entry point.

When verifying an old closure or runtime fingerprint, resolve an original source
path **and the consuming record's exact SHA256** through this map. A path-only
lookup is forbidden: a later run expecting revised bytes must never resolve to an
older snapshot. A missing exact match is unavailable, not an implicit fallback. All
other paths retain their original location. The original closure documents have
not been rewritten to imply that newer code produced older receipts. Runtime
files already committed at the recorded revision remain recoverable from Git.

## Current helper maintenance

The maintained `proof_support.py` now reports Git read failures explicitly and
preserves their original exception cause; it adds no retry or source fallback.
The maintained `score_support.py` extracts the same answer-fulfillment predicate
into a small helper. The selected-field and whole-question assessments stay
separate. The existing precision helper import paths remain valid.

Current helper hashes are recorded separately in
[maintained-helpers-v2.json](maintained-helpers-v2.json); the earlier publication
record is retained. The first-generation precision controller now logs only the
exception class before preserving the same failure receipt, one attempt,
continuation and cleanup. These are publication-time
helper hashes, not a replacement for either historical runtime fingerprint.
A subsequent evaluation must freeze its own complete runtime and helper versions.
No model or graph call, controller replay, or replacement of a closed score is
authorized or performed by this packaging work. Pure offline control comparisons
read the saved outcomes without rewriting them.

## Local replay databases

[local-only-artifacts.json](local-only-artifacts.json) records the original paths,
byte lengths and SHA256 hashes of 16 SQLite checkpoint databases. They are kept
unchanged locally and explicitly excluded from publication. Exported public
envelopes, accepted responses, traces and state snapshots remain reviewable.
A clone can verify the published artifacts and source archives, but cannot claim
to have resumed or verified absent local databases. Their recorded hashes remain
part of the historical closure; publication does not silently replace them.

[local-only-sidecars.json](local-only-sidecars.json) also preserves the exact
hashes and sizes of four empty WAL and four shared-memory companion files. These
eight binary replay files remain local alongside the databases; the original
closure records and saved retrieval evidence are unchanged.

Narrow Git attributes preserve the exact historical text and evaluated helper
bytes across staging and checkout. The ordinary source-quality and secret checks
remain enabled. Eighty exact entropy findings were independently classified as
58 artifact-path/hash keys and 22 unresolved related-document diagnostics; only
those fixed rule/path/line combinations are allowed through the normal scanner
policy. A subsequent review classified 62 further fixed locations: 54 stage1
artifact-path/hash entries, four local database paths and four exact database
exclusions. [scanner-classification.json](scanner-classification.json) preserves
that review evidence. Actual credential-pattern rules remain enabled.
