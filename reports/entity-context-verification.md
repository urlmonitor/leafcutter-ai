# DK-300 implementation and verification

Date: 2026-10-03. Branch: `design/kernel-entity-context` in the isolated
`worktrees/kernel-entity-context` checkout, based on `6ce0b21e`.

The requested agent pipeline is implemented. BA and IT PO used the repository's
Claude agent prompts to author behavioral criteria and technical contracts. The
test writer wrote the tests before runtime implementation; Python coders implemented
the recognition and kernel integration. The independent evaluator returned defects
for correction and reran the feature suite. No Anthropic run was used.

Implementation and independent verification are complete. The remaining baseline
failures and observed timing limitation are recorded below.

The subsequent graph-routing phase adds five AC records (37 DK-300 records in
total) and is documented in [the graph-selection evaluation](entity-graph-selection-evaluation.md).
Its final independent checks passed 148 entity/bridge cases and 64 focused cases
after the last wording change. The counts below retain their original phase scope.

## What changed

Fresh runs recognize repository entities before intent, using a prepared local
index. Glossary terms, document types, entry kinds, native artifact kinds, Python
symbols and native artifact IDs supply compact meanings with provenance. The
recognizer performs no repository body search, network request or model call.
Intent keeps the original goal, caller claims and later clarifications separate.
Routed capabilities can use canonical references for later evidence retrieval.

Default bounds are 16,000 goal characters, 12,000 original caller characters,
64 lookups, 16 identities, 300 characters per meaning/signature, an 8,000-character
compact projection and two seconds for recognition. Receiver limits include the
exact serialized state and questions. Missing/stale indexes have explicit outcomes
and never cause an intake rebuild or lexical fallback. Human and host resumes reuse
the checkpoint. Historical lexical enrichment remains for existing checkpoints.

Permission filtering precedes matching, fingerprints, coverage and projections.
Native whole-store validation is conservative: when current permissions deny a
validation dependency, that owner kind is withheld with partial coverage. Native
decision and flow sources require explicit research selection or a canonical hint
and do not expand ordinary automatic research.

## Traceability

- [DK-300 acceptance hierarchy](../docs/acceptance-criteria/decision-kernel/DK-300-entity-context/DK-300.yaml):
  32 records, including 26 leaf criteria, 59 original named test specifications and
  71 exact test links after independent regressions and the live AC repair. All leaf test and implementation
  references resolve. Implementation work status is done; readiness is not human approval.
- [Concept](../docs/analysis/2026-10-03-kernel-entity-context-concept.md)
  and [operating guide](../docs/how-to/supply-and-evaluate-kernel-context.md).
- [Forming flow](../docs/product-truth/flows/leafcutter/decision-forming.flow.json)
  and [lifecycle](../docs/product-truth/flows/leafcutter/decision-lifecycle.flow.json):
  version 4, built realization, draft readiness. The product-truth generator owns
  derived statuses, index entries and AC reverse links.

## Evidence

| Check | Result | Evidence |
|---|---|---|
| Independent feature suite, strict AC enforcement | 78 passed | [XML](entity-context-independent-final.xml) |
| Isolated labeled recognition corpus | 18/18; precision and recall 1.0 in all six tested families | [JSON](entity-context-independent-corpus-final.json) |
| Synthetic paired live intent | 3/3 expected labels in each arm; six Jev calls total; zero recognition calls | [JSON](entity-synthetic-intent-live.json) |
| Fixture cleanup isolation | 14 passed, including subsequent Git safety regression | [XML](entity-context-cleanup-fixed.xml) |
| Whole-kernel baseline before implementation | 1,543 passed, 425 subtests, seven skipped, five failures | [Baseline](entity-context-baseline-2026-10-03.json) |
| Final whole-kernel regression | 1,621 passed, 437 subtests, seven skipped; exactly the same five baseline failures, no new failures | [XML](entity-context-kernel-verified.xml), [baseline comparison](entity-context-regression-comparison.json) |
| Final real-repository recognition and two-second gates | 9,891 indexed entities, all six families current; late-AC and qualified-symbol gates 2/2 passed (1.714 s / 1.605 s); one separate mixed question returned partial at 2.014 s, followed by five passing repeats | [Build](entity-independent-build-final.json), [gate XML](entity-independent-performance-final.xml), [all three probes](entity-independent-real.json), [repeats](entity-independent-timing-repeat.json) |
| Source/style checks | Ruff clean across 53 changed Python files; kernel error-policy Ruff clean; mypy clean across 33 changed production modules; documentation/complexity checks clean | Coder handoff and supervisor checks |
| AC schema and documentation frontmatter | 32 ACs and four documents valid | Repository validators |
| Product-truth derivation and validation | Generated fields current; 25 flows, 229 resolved AC pointers, zero unresolved; 92 existing warnings | Repository generator and validator |
| Adjacent vocabulary/native compatibility | 16 passed, four skipped | [Vocabulary XML](entity-context-vocabulary.xml), [deployment retry](entity-context-vocabulary-clean-source.xml) |

The live experiment used only newly authored fictional glossary data and caller
claims. Both lexical and entity arms returned the same expected labels; this is a
small integration check, not evidence of improved model accuracy. No actual
repository content was sent. [Audited outgoing payloads](synthetic-intent-outgoing.json).

The broad kernel run overlapped the last type annotations and equivalent error-policy
cleanup. The coder reran 21 affected tests and the evaluator reran all 78 feature
tests on the final source afterward; both passed. At that verification point the 24
changed DK-200 YAML records differed only in generator-owned reverse links.

During PR preparation on 2026-10-04, the proof check found three legacy fresh-run
leaves and their parent still claiming old lexical wiring. DK-200a-1, DK-200a-1-i,
DK-200a-2 and DK-200a-4 now explicitly describe their retained ordering, explicit-route,
snapshot and handoff invariants under EntityContext. Their existing current service
tests carry matching coverage tags, with additional one-pass and unchanged-goal
assertions. Historical reports and direct-gather behavior were not relabelled as
proof of the new contract.

The subsequent strict migration rerun passed 33 tests across fresh-run wiring,
explicit routing, native/host handoffs, human/host continuation and intent-goal
preservation. All 71 kernel AC records passed schema validation, the affected
tests passed Ruff, and product-truth generation remained current. The earlier
behavior-preserving file splits passed 156 focused tests and an assertion/code
preservation comparison. These are additional checks, not a new whole-suite claim.

The timing follow-up was read-only: no source or cache change occurred during that
follow-up. Four further instrumented mixed-question runs completed in 1.521-1.781 s.
Resolved-path permission validation accounted for most of the time; the evidence
does not establish the cause of the isolated miss. The miss is retained as an
observed, supported partial-context outcome. The subsequent live AC repair below
required a new source freeze and explicit index build.
[Phase timings](entity-core-timing-profile.json).

## Correction loop

The evaluator reported cold-index deadline exhaustion, omitted native AC validation
dependencies, absent-root freshness, a configured glossary outside standard paths,
extra lookup from punctuation, artifact-prefix misresolution, missing Flow/Ticket
unknown states, caller-window expansion after redaction, and denied-file coverage
leaks. Coders repaired these and the independent feature tests passed afterward.
See the [independent evaluation](entity-independent-evaluation.md) for reproductions,
severity and red-run evidence. The test writer's [handoff](entity-context-test-writer-handoff.yaml)
records the original failing tests before implementation.

The broad kernel run also exposed automatic research source drift and a test mock
leak. Source selection now distinguishes explicitly selected indexed stores from
automatic sources. The test fixture now initializes its unittest async runner so
cleanup actually releases its Git mock. Fixture corrections preserved the original
security and continuation assertions; they are described in the evaluator report.

## Limits and environment notes

- Five baseline failures remain: one analysis-folder candidate-cap case and four
  missing `host.query_build` entries in a pre-existing test fixture. The complete
  kernel suite is not entirely green; its failure set is unchanged by this work.
- An actual Windows symlink could not be created (OS error 1314). The deterministic
  resolved-path escape test passed; no real OS symlink pass is claimed.
- One mixed-question probe exhausted the two-second recognition deadline and
  returned explicit partial context. Five independent repeats and four instrumented
  repeats succeeded, but consistent completion within two seconds is not guaranteed
  by this sample. Filesystem caches were not flushed for the real-repository probes.
- The original Leafcutter question recognized only ambiguous `run` symbols; bare
  `kernel` and `leafcutter` did not have declared glossary meanings. The feature does
  not invent aliases, and these checks do not prove that original wording now
  classifies or answers correctly.
- Freshness uses conservative filesystem metadata and stored hashes, not adversarial
  restoration of every metadata field. Index preparation is explicit and must be
  repeated after indexed sources change.
- A compatibility test that copies the checkout encountered four test-created
  temporary directories owned by the sandbox account. The isolated retry excluded
  exactly those scratch directories from the copy and passed. Cleanup was denied by
  filesystem ownership; these untracked directories are not deliverable source.
- The original implementation verification preceded the user's separate PR and
  merge request on 2026-10-04.

## Approved live AC demonstration and correction

After explicit user approval to send repository evidence to Jev and truncated
trace context to Langfuse, the actual question "What is GE-114-4 about? Explain it
in plain language." exposed a downstream integration gap: recognition correctly
produced the canonical AC reference, but retrieval treated `#/criteria` as a
Markdown heading and returned no evidence. The failed trace and envelope are
preserved in the [live demonstration report](entity-ac-live-demo/demo.md).

DK-300d-3 now links three additional test functions covering the real
index/recognizer/service path, invalid-pointer discrimination and exact nested
YAML/JSON value selection. Six parameterized cases failed before the repair.
Explicit retrieval now reuses the native structured selector, preserves the
canonical pointer, and retains current permission and excerpt bounds. Invalid
selectors cannot fall back to the entire record.

Independent verification passed 56 focused tests plus three subtests and all 84
entity-context tests. All six new cases rejected a fragment-dropping mutation;
restored production passed again. The coder's broader entity/retrieval/knowledge
run passed 267 tests plus 50 subtests. Ruff, documentation/complexity, AC schema
(32 records), and product-truth derivation checks passed. Mypy passed with absent
YAML stubs ignored. One concurrent collection race was recorded and resolved by
a sequential rerun. [Independent review](entity-native-pointer-independent-review.md),
[broader XML](entity-native-pointer-core-broad.xml).

The refreshed index contains 9,893 entities with all six families current. The
same live question then completed successfully in `run-7599d5bd6e4041c9`:
one AC meaning, one lookup, 1.659 seconds and zero model calls for recognition;
Jev selected evidence intent; research retrieved the exact 399-character criteria
field, returned source-verified evidence, and marked the need satisfied. The
whole run made five Jev calls and zero host operations. No Anthropic calls occurred.

The bounded recognition step does not eliminate broad downstream research:
documentation retrieval still scanned 482 files and reported candidate caps. The
single AC excerpt is complete, while the overall bundle retains search truncation
notes. This successful integration run does not establish causal intent improvement
or universal query coverage. [Observed steps and both traces](entity-ac-live-demo/demo.md).
