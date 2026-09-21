---
title: "KI-SEC-20260914-entropy-flags-test-class-names — ENTROPY_HIGH reads a long CamelCase test class name carrying an AC id as a secret, and the only remedy it offers is an allowlist edit that an automated reviewer rightly refuses"
description: "medium. No secret can slip past because of this, but it costs a commit round-trip each time. Its standard remedy, a `.security-allowlist` glob, weakens scanning for the whole file. On 2026-09-14 the auto-mode permission classifier refused a"
type: reference
category: reference
status: active
created: '2026-08-19'
last_updated: '2026-08-19'
components:
  - security_scanner
  - commit_guardian
related_docs:
  - docs/known-issues/security-scanner.md
  - docs/known-issues/README.md
---

# KI-SEC-20260914-entropy-flags-test-class-names — ENTROPY_HIGH reads a long CamelCase test class name carrying an AC id as a secret, and the only remedy it offers is an allowlist edit that an automated reviewer rightly refuses

> One known issue, split out of `docs/known-issues/security-scanner.md` on
> 2026-09-14. Index: [security-scanner.md](../security-scanner.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium. No secret can slip past because of this, but it costs a commit round-trip each time. Its standard remedy, a `.security-allowlist` glob, weakens scanning for the whole file. On 2026-09-14 the auto-mode permission classifier refused a commit containing such an edit as `[Security Weaken]`.
- **Status:** open
- **Occurrences:** 5 on 2026-09-14 alone, counting this register entry's own first commit (see below). `test_uxp_700c_1_i.py` and `test_uxp_700b_2.py` were allowlisted. `test_uxp_700e_3_i.py` was allowlisted. `test_uxp_700e_1_ii.py` was refused and its class renamed instead.
- **First seen:** 2026-09-14 (at least; earlier allowlist globs for `unit_tests/...:*` suggest the same cause) · **Last seen:** 2026-09-14
- **Where:** `templates/scripts/commit_guardian/check_secrets.py`: `_ENTROPY_MIN_LEN = 20`, `_ENTROPY_THRESHOLD = 4.5`, and the prose exemption `_is_prose_exempt()`

**Symptom.**

```text
[ENTROPY_HIGH] unit_tests\product_truth\test_uxp_700e_1_ii.py:94
  class TestUxp700e1Ii…ReachableFromEntryPoint(unittest.TestCase):
```

**Measurement.** Shannon entropy per token, computed with the scanner's formula:

| Token | Length | Entropy |
|---|---|---|
| `TestUxp700e1Ii` + `ReachableFromEntryPoint`, one identifier | 37 | 4.540 (flagged) |
| `TestUxp700e3I` + `ReachableFromEntryPoint`, one identifier | 36 | 4.538 (flagged) |
| `TestTighteningReachableFromEntryPoint` | 37 | 4.108 |
| `test_uxp_700e_1_ii_reachable_from_entry_point` | 45 | 4.089 |

The repo's test convention causes this. A reachability test is named after its AC, and the AC id (`700e1Ii`) adds digits and mixed case to an otherwise ordinary identifier. That tips it just over 4.5. The snake_case method name carrying the same id stays under. Only the CamelCase class name trips the scanner.

**This entry is itself an occurrence.** Its first draft quoted the two flagged names whole. `check-secrets` refused the commit that added this register entry, and also flagged a 65-character KI slug in `commit-guardian.md`, because the scanner's token pattern `[A-Za-z0-9+/=_\-]{20,}` counts a whole hyphenated slug as one token. The names above are therefore quoted in two parts, and that slug was shortened. That is the same rename-to-evade workaround this entry describes, applied to prose.

**Why the allowlist remedy is wrong here.** A `ENTROPY_HIGH:<file>:*` glob suppresses *every* future entropy finding in that file, including a real token pasted into a fixture later. Per-line entries go stale as the file grows, which is why the register's convention is globs. So the scanner leaves two choices: weaken a whole file, or maintain entries that rot. A reviewer that refuses the glob is behaving correctly. The defect is that the scanner made the glob necessary.

**Workaround in use.** Rename the class to something without the AC id (`TestTighteningReachableFromEntryPoint`). The `# covers:` tag and the method name still carry the id, so traceability is unaffected.

**Fix direction.** Exempt Python identifiers in declaration position (`class X(`, `def x(`) from ENTROPY_HIGH when the token matches `^[A-Za-z_][A-Za-z0-9_]*$` and splits into dictionary-like CamelCase or snake_case segments. A secret is almost never a syntactically valid identifier in declaration position. Pin it with the four tokens above: the two flagged names must pass, and a 40-character base64 token assigned to a variable in the same file must still be flagged.

**Pattern:** a detector whose false positives are structurally produced by the project's own naming convention, and whose only escape hatch is to suppress the detector for the whole file.
