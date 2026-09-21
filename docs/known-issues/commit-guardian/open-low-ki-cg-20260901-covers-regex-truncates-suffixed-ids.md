---
title: "KI-CG-20260901-covers-regex-truncates-suffixed-ids — `check_ac_coverage`'s tag pattern collapses every suffixed AC id to its L0 root and cannot see `//` tags at all"
description: "KI-CG-20260901-covers-regex-truncates-suffixed-ids — `check_ac_coverage`'s tag pattern collapses every suffixed AC id to its L0 root and cannot see `//` tags at all"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260901-covers-regex-truncates-suffixed-ids — `check_ac_coverage`'s tag pattern collapses every suffixed AC id to its L0 root and cannot see `//` tags at all

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-09-01
- **Where:** `templates/scripts/commit_guardian/check_ac_coverage.py:41`

**Symptom.** The hook credits coverage to the wrong record. A test tagged
`# covers: BP-100k-6` is recorded as covering `BP-100`, so the leaf reads as uncovered while
its L0 reads as covered by a test that exercises a great-grandchild's behaviour. Both halves
are wrong, and the wrong half that *adds* coverage is the dangerous one — a missing link is
visibly missing, whereas a link on the wrong record looks like evidence.

**Evidence.** The pattern is `_COVERS_REGEX = re.compile(r"#\s*covers:\s*([A-Z]{2,6}-[0-9]{3,})")`.
`[0-9]{3,}` stops at the first non-digit, so every alpha/numeric suffix is discarded. Run
against real tag shapes on 2026-09-01:

```
'# covers: ACS-1300a-1'  -> ACS-1300
'# covers: BP-100k-6'    -> BP-100
'# covers: ACS-1300'     -> ACS-1300
'// covers: ACS-1300a-1' -> None
```

The `#` anchor also makes it blind to every `// covers:` tag, which the canonical rule accepts.
Measured scope on the same day: 3,631 tag occurrences across 396 `.py` and 8 `.ts` files, 937
distinct ids — the overwhelming majority carry a suffix this pattern truncates.

**Why it has not bitten harder.** The hook is detect-only and always exits 0
(`check_ac_coverage.py:167`), so it cannot block a merge. That bounds the blast radius to a
wrong advisory — but an advisory that names the wrong record is the failure this register
exists to catch, not a lesser form of it.

**Not a new problem — it is the fourth reader.** `TQ-100b-5` (readiness `approved`, priority
high) already owns the parity problem and enumerates the closed set of four covers-tag
recognition rules: `scripts/ac_store/test_enforcement.py:57` — `r"(?:#|//)\s*covers:\s*(\S+)"`,
the canonical one; a byte-equal duplicate in `check_done_proof.py:92-95`'s `ImportError`
fallback; `check_test_ac_tags.py:38` (detect-only, exactly three digits); and this one. Do not
fix this in isolation and do not author a fifth rule — consolidate onto the canonical pattern
under `TQ-100b-5`.

**Fix direction.** Replace the pattern with the canonical `r"(?:#|//)\s*covers:\s*(\S+)"` and
resolve the captured id against the store rather than constraining its shape in the regex. An
id's grammar is the store's business; a tag scanner's job is to capture the token and ask.

**Related.** `KI-CG-034` and `KI-CG-20260831-manifest-shadowing` are the same class one layer
out — a checker keying on a namespace that does not match the one its input actually uses.

**Pattern:** `docs/reference/false-green-mechanisms.md` → a validator whose *input parser* is
narrower than the data it validates, so it reports confidently about records that were never
the ones in front of it.

---
