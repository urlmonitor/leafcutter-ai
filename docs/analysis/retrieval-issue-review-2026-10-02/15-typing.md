---
title: 15. Informational Python typing failures
description: Historical analysis and saved observations for 15. Informational Python
  typing failures.
type: explanation
status: draft
created: '2026-10-02'
last_updated: '2026-10-05'
components:
- knowledge_management
- decision_kernel
---
# 15. Informational Python typing failures

Analysis only, 2026-10-02. Inspected commit: `887c66d3896ba7727ce41b743887210a3883c6ce`. No runtime, workflow, AC or environment changes; no provider/database calls. The recommendation is a staged boundary repair, preceded by a reproducible baseline. A failing informational check is unresolved debt, not evidence that the latest feature introduced every diagnostic.

## Evidence and scope

The saved PR #1005 receipt identifies head `593f4c468a5e4ee5e08deedd72a61ac657ebc493`, merged as the inspected commit. Their trees have no diff. Its saved `optional-mypy.log` contains **175 errors in 42 imported files**, with no errors in either changed runtime file (`kernel/intent/roots.py`, `kernel/scheduler/nodes_route.py`) or either changed test. The actual selected roots were only `tests/kernel/intent/test_typed_research_binding.py` and `tests/knowledge/test_native_changelog_entry.py`. Zero diagnostics does not establish complete checking of their untyped bodies.

Receipts: `C:/Users/Hendrik/Code/leafcutter/_backups/typed-research-binding-release-20261002T1720Z/{optional-mypy.log,pr1005-merged.json}`. The earlier retrieval backup's `optional-ci-review-3fdc.json` records **254 errors/49 files** for PR #998 head `3fdc5286d181d1042de05b5ba9d0b88f85c9db02`. Different selected/imported scopes mean the difference is neither a remediation count nor a regression count.

Current [CI](../../../.github/workflows/ci.yml) lines 655-700 is explicitly informational (`continue-on-error: true`), uses Python 3.13 and invokes `mypy --ignore-missing-imports --explicit-package-bases --no-error-summary`. Selection includes changed Python files under `scripts/`, `tests/`, `unit_tests/`; **`knowledge/`, `kernel/`, `integrations/` are absent as direct roots**. Imports happen to expose some of them. Direct pushes skip the check. The earlier shallow-fetch/pathspec failures are already corrected here; they are historical causes of unreliable signal, not current fixes to repeat.

`requirements-dev.txt` leaves `mypy>=1.8` unpinned. The saved PR #998 installation log proves mypy 2.4.0/Python 3.13.15; PR #1005's step log proves Python 3.13.15 but does not itself contain the installed mypy version. The existing local virtual environment currently has mypy 2.3.1/Python 3.14.2. A read-only parser probe of current `test_native_mock_data.py` reproduces ten invalid `# type: unit`/`integration` comments locally. This is separate parser/annotation debt, absent from the 175-error log, not proof that a particular version change caused it. A cache-disabled full-check attempt stopped before checking because the Windows `NUL` cache path was unsuitable; no fresh full baseline or parity run is claimed.

## Actual findings, causes and owners

The current error-code distribution is 73 `attr-defined`, 35 `union-attr`, 27 `arg-type`, and 40 other errors. These are diagnostic categories, not 175 independent runtime bugs.

| Boundary and owner | Verified example and cause | Repair direction / risk |
|---|---|---|
| Configuration: knowledge composition | `config.py:102-117` accepts `KnowledgeConfig | dict` but reads model attributes without normalization; `environment.py:105-151` repeats that contract. `resolve_neo4j` promises `list[str]` after assembling optional values; splatting an arbitrary-length list into `Neo4jBackend` produces multiple-argument diagnostics. | Normalize once at the public boundary; internal helpers consume `KnowledgeConfig`. Preserve advertised dictionary callers or explicitly audit them. Return an exact three-string tuple or named credential structure. Invalid inputs must still fail before I/O. |
| Backend/model boundaries: knowledge core and adapter owners | `service.py:39-72`, `query_admission.py:32`, `query_execution.py:35-71` call methods on `object`; `domain_schema.py:55-104` accesses entity/snapshot fields on `object`. | Use existing `Entity`/`ProjectionSnapshot` models and small structural backend/catalog/observer/cancellation contracts. Keep database-driver types inside adapters. Do not replace every `object` with one oversized interface. |
| Control-flow typing: knowledge policy | `errors.py::invalid` and `not_ready` always raise but declare `-> None`; therefore `semantic.py:63-80` cannot narrow the optional provider. `deadlines.py:8` infers `ContextVar[None]`, although callers set a float. | Accurate `Never`/`NoReturn`, `ContextVar[float | None]`, explicit collection/value annotations. Low runtime risk; prove the helpers retain their exception behavior. |
| Result contracts: query execution and kernel integration | `execute_query` returns `QueryRows` with `truncated`, but advertises `list`; its consumers read `.truncated`. `knowledge_execution.py:363-364` dereferences optional `result.answer` after a separate boolean helper. Followups pass optional `source_sha` and dictionary budgets to typed model constructors. | Preserve truncation and provenance metadata in the return type. Carry/narrow the actual answer object; validate revision and construct `RetrievalBudget` explicitly. These touch incomplete-result and budget behavior: high validation priority. Current source already guards some invariants indirectly, so diagnostics alone do not establish crashes. |
| CLI/resource lifecycle: standalone CLI and composition | Older PR #998 logs show 27 errors in `__main__.py` and 19 in `cli_catalog.py`; current signatures still use `args: object`. `KnowledgeRetriever` defines `capabilities`/`retrieve`, while both CLI paths call `close`. | Convert parsed arguments into command-specific typed settings. Separate owned, closable resources from caller-owned retrieval ports; do not require every injected fake/client to own a connection. These errors fell outside PR #1005's roots, not demonstrably away. |
| Payload serialization: native mapping/kernel contracts | `native_properties.py` infers homogeneous dictionaries for mixed scalar/list metadata; `kernel/contracts/verbatim.py:12-14` has recursive alias resolution errors. | Use precise JSON/property value aliases or named structures. Verify recursive validation and exact source whitespace round trips before changing opaque payload typing. |

## Options and recommended batches

1. **Boundary-first repairs plus fixed baseline (recommended).** Small reviewable changes, stable diagnostics, and tests around runtime-sensitive seams. Costs several batches; avoids making type cleanup a retrieval redesign.
2. **Whole retrieval slice made strict at once.** Consistent contracts sooner, but many coupled adapters, CLI paths and test doubles change together. High review/regression cost; defer until the baseline and smaller contracts exist.
3. **Baseline ratchet before cleanup.** Reject newly introduced diagnostic identities while retaining a visible, owned backlog. Fast protection against growth, but comparison needs identical roots/environment and stable identities; an error-count threshold can hide substitutions. It is temporary accounting, not a substitute for repairing the contracts.

Recommended sequence:

1. **Measurement batch:** choose and pin the supported Python/mypy pair; record dependency versions, commit, flags, roots, imported scope, exit classification and full diagnostics. Add explicit retrieval/runtime roots in a separate scoped baseline. Preserve the historical changed-files receipt. Reconcile reserved type-comment metadata with its real readers; keep test traceability intact.
2. **Small type-only batch:** correct never-returning helpers, deadline context, explicit optional returns and local collections. Measure which dependent errors disappear; do not promise a count in advance.
3. **Config/CLI batch:** normalized `KnowledgeConfig`, fixed credential shape, command-specific CLI types and explicit lifecycle ownership. Include missing/invalid settings and disabled-backend paths without external services.
4. **Protocols/result batch:** type backend/catalog/observer seams, `QueryRows`, optional assessment/revision handling and model construction. Retain exact truncation, timeout, cancellation, scope, budget and failure semantics. Prioritize these runtime risks over remaining presentation-map annotations.
5. **Serialization batch:** native property shapes, recursive JSON aliases and adapter callback types, with lossless real serialization checks. Then reassess stricter checks incrementally.

Never fix this by blanket `Any`, blanket ignores, deleting metadata/tests, suppressing diagnostics, or shrinking a consumer contract until it type-checks.

## Quality obligations and validation

No direct AC requiring zero Python mypy errors or promoting this Python job was found in the inspected AC store. Do not equate web TypeScript gate ACs with Python policy. Relevant verified records are:

- `KM-400e-3`: active / approved / **done**; existing kernel capability consumption, bounded followups and no backend sessions/credentials in state. Preserve this contract during protocol work.
- `KM-500b-3`: active / approved / **done**; typed query input, durable verified catalog and governed activation. Config/type work must not weaken it.
- `BP-1200b-1`: active / approved / **done** in the store; demands a blocking full-suite job and explicitly distinguishes informational typing. Current CI disables that full-suite job by owner request, so its stored status is not evidence that such a run currently occurs.
- `BP-1100g-1`: active / approved / **done**; teaches test angles. `TQ-500c-1`: active / draft / **todo**; granular discrimination outcomes, not completed enforcement.

The read research/coder/test-writer prompts require evidence rather than guessed cause, consumer enumeration before contract changes, real producer-to-consumer seam checks, and genuine RED evidence before behavior repairs. `CLAUDE.md` requires behavioral gate tests and forbids claiming readiness from source-string presence. The Python rule requests typed arguments/returns, but currently declares `globs: *.sql`; `INF-200a-6` (active / reviewed / **todo**) records that convention-deployment gap. It does not establish strict mypy enforcement.

For each batch, compare base and candidate using **the same pinned toolchain and roots**, separating parser/configuration failure from type diagnostics. Annotation-only changes use the existing failing static case as RED evidence and existing runtime checks as parity evidence; do not invent a failing runtime test for correct behavior. Behavior changes need a reproducible failing test first, then the exact case green with unchanged relevant tests. Use real CLI parsing, real model serialization, and real producer outputs into consumers with only external boundaries faked. Negative controls must expose a wrong revision, omitted truncation flag, absent optional answer/provider or malformed config; no providers or database are needed for these unit/seam proofs.

Promote the optional gate only after supported roots and toolchain are explicit, fresh-checkout checks are reproducible, the enforced slice is clean (or a separately specified ratchet is reliable), and injected type errors actually fail the job and merge condition. Demonstrate changed-file selection, imported errors, empty selection and tool failure separately. Give the eventual required check a stable name and verify branch protection consumes its result. Gate promotion is a separate reviewed policy change, not an automatic consequence of fewer errors.
