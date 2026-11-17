# DK-300d-3 native-pointer regression review

Date: 2026-10-03. Classification: `production_drift`. Reviewer: independent test-writer; no production edits or commits.

The real index and recognizer emitted `path.yaml#/criteria`, but later retrieval interpreted `/criteria` as a Markdown heading. The added service regression feeds that actual generated reference through evidence intent, research planning and real retrieval. It requires explicit-locator evidence containing only the criterion value; unrelated lexical evidence cannot satisfy it. Initial meanings still exclude the criterion body.

## Traceability and source review

Added three exact test-function links and their technical/test specifications to `DK-300d-3.yaml`. Criteria, readiness and implementation status were preserved. Added the actual repaired modules to `implemented_by`:

- `kernel/capabilities/retrieval/locators.py`
- `knowledge/adapters/source_excerpt.py`

The pointer branch reads only after existing scope, source, deny-glob and file-size admission. It selects a YAML/JSON value, then applies the existing excerpt bound to that value. Evidence retains the canonical pointer. Missing, malformed, ambiguous and scalar-descendant selectors produce a limitation; they cannot fall back to the entire record. The shared selector handles nested sequence indices and escaped mapping keys. No blocking finding remained for this repair.

## Strict red baseline

All commands used `C:/Users/Hendrik/Code/leafcutter/.venv/Scripts/python.exe` from the task worktree and `AC_ENFORCE_STRICT=1`.

```powershell
$env:AC_ENFORCE_STRICT='1'
& C:/Users/Hendrik/Code/leafcutter/.venv/Scripts/python.exe -m pytest tests/kernel/entity_context/test_native_pointer_retrieval.py -q --tb=short -p no:cacheprovider --junitxml=reports/entity-native-pointer-red.xml
```

Before production edits: **6 failed, 0 errors, 0 skipped**, 20.10 seconds. All were behavioral assertion failures:

- Service path: no explicit-locator criterion evidence, despite consumption of the real recognizer's pointer.
- Missing, scalar-descendant and malformed-pointer cases: their valid controls failed with `no heading matches '/criteria'`.
- JSON and YAML nested-value cases: no evidence because the pointer was interpreted as a heading.

## Independent verification after source freeze

| Scope | Result | Report |
|---|---|---|
| New six; existing retrieval locators and sections; knowledge source boundaries | 56 passed, 3 subtests passed; 8.63 s | `entity-native-pointer-independent-green.xml` |
| Complete `tests/kernel/entity_context` | 84 passed; 28.60 s | `entity-context-after-pointer-independent.xml` |
| New six after mutation process exited | 6 passed; 2.28 s | `entity-native-pointer-restored-green.xml` |

Focused command:

```powershell
& C:/Users/Hendrik/Code/leafcutter/.venv/Scripts/python.exe -m pytest tests/kernel/entity_context/test_native_pointer_retrieval.py tests/kernel/retrieval/test_retrieval_locators.py tests/kernel/retrieval/test_retrieval_sections.py tests/knowledge/test_source_boundaries.py -q --tb=short -p no:cacheprovider --basetemp=reports/tmp-pointer-independent-focused --junitxml=reports/entity-native-pointer-independent-green.xml
```

Full suite command:

```powershell
& C:/Users/Hendrik/Code/leafcutter/.venv/Scripts/python.exe -m pytest tests/kernel/entity_context -q --tb=short -p no:cacheprovider --basetemp=reports/tmp-pointer-independent-entity-final --junitxml=reports/entity-context-after-pointer-independent.xml
```

The first full-suite launch ran concurrently with focused tests and hit a collection-only `FileNotFoundError` on a disappearing `leafcutter-entity-owners-*` temporary directory. Separate basetemp directories did not prevent the repository-discovery race. A sequential rerun passed all 84 cases. No assertions or discovery rules were weakened.

## Mutation discrimination

In a separate Python process, `unittest.mock.patch.object` replaced the real imported `locators.parse_locator` with a wrapper returning `(path, 'file', '')` for every pointer. Production files remained unchanged. The same six-case file ran with strict enforcement and wrote `entity-native-pointer-fragment-drop-mutant.xml`.

| Test case | Mutation result |
|---|---|
| Service native AC | Failed: whole-record excerpt differed from the exact criterion value |
| Invalid `/missing` | Failed: unselected record contents were disclosed |
| Invalid `/criteria/child` | Failed: unselected record contents were disclosed |
| Invalid `/criteria~2` | Failed: unselected record contents were disclosed |
| Nested JSON value | Failed: sibling and root fields appeared instead of the exact selected value |
| Nested YAML value | Failed: sibling and root fields appeared instead of the exact selected value |

Result: **6 failed, 0 errors, 0 skipped**, 19.96 seconds. Two pytest plugin assertion-rewrite warnings arose from importing the patched runtime before pytest; no test collection or execution was lost. After the mutation process exited, the unmodified production implementation passed all six again.

The original failed live trace was untouched. The real-index refresh, live rerun and final user report remain owned by the root agent.
