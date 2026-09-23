---
title: "KI-BP-20260910-1240 — build.py writes CRLF on Windows and then cannot see that it did, so every deployed script silently diverges from its template and a plain re-run never repairs it"
description: "KI-BP-20260910-1240 — build.py writes CRLF on Windows and then cannot see that it did, so every deployed script silently diverges from its template and a plain re-run never repairs it"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-20260910-1240 — build.py writes CRLF on Windows and then cannot see that it did, so every deployed script silently diverges from its template and a plain re-run never repairs it

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../../build-pipeline.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** partially resolved — the shared writer `_write()` is fixed (BP-1000a-7), which clears the commit-blocking hook-parity case; ~20 other text-mode writers remain (see Fix direction)
- **Occurrences:** 1 (found 2026-09-10 while landing EPIC-TruthfulProjectRecord)
- **First seen:** 2026-09-10 · **Last seen:** 2026-09-14 — two more text-mode writers seen producing CRLF: `docs/product-truth/scripts/generate_product_truth.py` `_write_text()` (regenerated journeys land CRLF in the working tree; git normalises on add, so the churn is invisible until a byte-level check reads them), and an unidentified step in the `unit_tests/portability` run that rewrote `templates/scripts/commit_guardian/_authored_change.py` with CRLF-only changes
- **Where:** `scripts/build_phases.py` `_write()` · every `check-hook-parity` / `check-output-drift` consumer

**Symptom.** On Windows, `check-hook-parity` blocks the commit reporting that every script under `.leafcutter/scripts/commit_guardian/` and `scripts/commit_guardian/` diverges from its canonical template in `templates/scripts/commit_guardian/`. Running `python scripts/build.py` — the remedy the hook names — reports `580 files unchanged` and repairs nothing. The commit stays blocked, and no number of re-runs moves it.

**Why the build cannot see it.** `_write()` writes with `Path.write_text(content, encoding="utf-8")`. That opens in text mode with `newline=None`, so Python translates every `\n` to `os.linesep` — `\r\n` on Windows. The canonical templates are LF-only, so every deployed file lands byte-different from its source. The build's own compare-before-write guard then reads the deployed file back with `read_text()`, which applies universal-newline translation on the way in and hands back LF. The comparison is LF-vs-LF, matches, and the file is skipped as up to date. The corruption and the blindness to it are the same line:

```python
>>> p.write_text("a\nb\n", encoding="utf-8"); p.read_bytes()
b'a\r\nb\r\n'
>>> p.read_text(encoding="utf-8")
'a\nb\n'          # the CRLF is invisible from here
```

**Why it is worse than a cosmetic diff.** Three consequences compound. (1) The repair the hook advertises is a no-op, so the contributor is told to run a command that cannot work. (2) `--force` does NOT repair it either, despite appearances. A forced run reaches the compare-before-write guard, whose text-mode read normalises the CRLF file to LF, compares equal, and skips the write. (This entry originally claimed `--force` was the working repair; that was wrong. The repairs observed while filing it came from byte-copying templates over the deployed copies by hand, and from `--force` refreshing `.build_manifest.json`, which is a different defect.) (3) `.build_manifest.json` records the hash of what the build believes it wrote; when the build skips a file it never refreshes that entry, so `check-output-drift` later reports the file as hand-edited. A contributor following the error messages is walked toward editing hashes inside a build-integrity manifest to make a drift check pass — which is exactly the action that should never be taken, arrived at by following the tool's own advice.

**Detection.**

```bash
python -c "import pathlib,tempfile; p=pathlib.Path(tempfile.mkdtemp())/'t'; p.write_text('a\nb\n',encoding='utf-8'); print(p.read_bytes())"
# b'a\r\nb\r\n' on Windows, b'a\nb\n' on Linux
python scripts/build.py --target-dir .        # reports "unchanged", repairs nothing
python scripts/build.py --target-dir . --force # also reports "unchanged": the guard compares decoded text
```

Any `check-hook-parity` failure that survives a plain `build.py` re-run on Windows is this.

**Fix direction.** *Landed for the shared writer (BP-1000a-7, 2026-09-13):* `_write()` in `scripts/build_phases.py` now encodes once, compares `read_bytes()` against those bytes, and writes with `write_bytes()`, so the guard and the writer act on the same value with no newline translation. Every commit-guardian script, config and manifest is deployed through it, so the hook-parity failure that blocked commits is gone: after the fix a deployed `run_hook.py` holds zero CRLFs and is byte-identical to its template. *Still open:* the build has roughly twenty other text-mode writers with the identical defect that do not route through `_write()` — among them `generate_agent_cards.py` (every tracked `docs/agents/cards/*.card.md`), `build.py`'s `LEAFCUTTER_VERSION` write, the CLAUDE.md glossary and roadmap-phase injections (`build_glossary.py`, `build_roadmap_phase.py`), and the scaffold writers (`build_ac_store_scaffold.py`, `build_architecture_scaffold.py`, `build_config_scaffolds.py`, `build_precommit.py`). On Windows these leave every freshly built checkout showing dozens of tracked files as modified, purely by line endings. The right fix is one shared byte-exact writer that every phase calls, not twenty local patches — which is why it was scoped out of the quick-fix rather than folded in.

**Pattern:** the writer and the change-detector disagree about what a file's content IS, so the component's self-check validates a normalised view of its own output rather than the output. **Related:** `GE-120` (green means it was checked — here the build reports "unchanged" about a file it corrupted), and `docs/reference/false-green-mechanisms.md`.

---
