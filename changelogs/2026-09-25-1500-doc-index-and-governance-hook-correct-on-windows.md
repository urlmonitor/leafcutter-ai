---
title: "The doc index and the AC governance hook now behave the same on Windows as on Linux"
date: "2026-09-25"
time: "15:00"
type: manual
components:
  - knowledge_management
  - documentation_system
  - ac_store
  - commit_guardian
summary: "Three Windows-only defects, one bug class. generate_doc_index.py wrote docs/INDEX.md links with backslashes on Windows (KM-300a-1). The check-ac-governance hook looked up an AC file's HEAD version with a backslash path, so it treated existing AC files as new and skipped its HEAD comparison (ACS-400e-4). Once that lookup worked, it decoded git's UTF-8 output as cp1252, which made non-ASCII protected fields look modified and falsely blocked commits (ACS-400e-5). All three are fixed with tests that fail on the unfixed code. The work also adds a planned AC tree, KM-300, for a doc index that is correct and byte-identical on every OS."
description: "DOC INDEX (KM-300a-1). scripts/generate_doc_index.py interpolated str(Path.relative_to(repo_root)) into the Markdown links at both rendering sites: the single-file sections (Glossary etc.) and the directory tables. On Windows that stringifies with backslashes, so every regeneration there, including the pre-commit auto-regeneration, produced links like [docs\\architecture\\x.md](docs\\architecture\\x.md). Those links do not resolve on GitHub, and INDEX.md flip-flopped against POSIX-generated versions between commits. Both sites now use .as_posix(). Regenerating on Windows went from 179 backslash links to 0. The file is already over its size limit, so the change is net-zero in length. The three tests include a simulated-Windows path-flavour case, so they fail on POSIX CI too, and a fix to only one of the two sites stays red. AC GOVERNANCE HOOK (ACS-400e-4, ACS-400e-5). templates/scripts/commit_guardian/check_ac_governance.py passed a backslash repo-relative path to `git show HEAD:<path>`. Git's rev:path syntax needs forward slashes, so the lookup failed, and every existing AC file edited on Windows was treated as brand new. That skipped the immutable-field and amended_by checks, and editing docs/acceptance-criteria/index.yaml (which has no origin_agent) was blocked outright. Fixing the lookup exposed a second defect: subprocess.run(text=True) with no encoding decoded git's UTF-8 output with the locale codec (cp1252), so an em dash in a criteria field became mojibake and the unchanged field looked modified. All three subprocess calls in the hook now pass encoding=\"utf-8\". Both fixes ship together because the first alone would have turned silent skips into false blocks. Each has a real-git, real-subprocess test with a mutation proof. PLANNED, NOT BUILT. KM-300 (knowledge-management) records the rest of the doc-index contract as approved, high-priority ACs. KM-300a-2: link targets are relative to docs/. Today every link starts with docs/ inside docs/INDEX.md, so on GitHub it resolves to docs/docs/... and is broken even with forward slashes. KM-300b-1/b-2/b-3: same order, LF/UTF-8, and a byte-identical map across OSes. Windows currently sorts case-insensitively and writes CRLF. KM-300c: a commit-time guard against machine-specific or unresolvable links, which must ship after KM-300a-1 and KM-300a-2 respectively."
commits:
  - a1dfb37e
  - a8eec05f
  - 9e9cfbec
  - 4e9beaaa
  - "11095536"
breaking: false
---

## Entry

Three Windows-only bugs from the same cause: `str(Path)` gives backslashes
on Windows, and the code used that string where only forward slashes work.

### Doc index links (KM-300a-1)

`scripts/generate_doc_index.py` wrote `docs/INDEX.md` links with backslashes
whenever it ran on Windows, including when the pre-commit hook regenerated it.
Those links break on GitHub, and the file flipped back and forth against
Linux-generated versions. Both link sites now use `.as_posix()`.

### AC governance hook (ACS-400e-4, ACS-400e-5)

`check_ac_governance.py` looked up an AC file's committed version with a
backslash path, which git rejects. So on Windows every edited AC file counted as
new: its protected-field checks were skipped, and editing `index.yaml` was
blocked outright. Fixing that exposed a second bug: git's UTF-8 output was
decoded as cp1252, so an em dash made an unchanged field look modified and
falsely blocked the commit. Both are fixed together; shipping only the first
would have traded silent skips for false blocks.

### Planned: KM-300

The rest of the doc-index contract is recorded as approved, high-priority ACs
under `knowledge-management/KM-300-docs-same-everywhere/`. The most visible one
is **KM-300a-2**. The map lives in `docs/` but its links start with `docs/`, so
on GitHub they resolve to `docs/docs/...` and are still broken. KM-300b covers
the remaining cross-OS differences (sort order and CRLF). KM-300c adds a
commit-time guard, which must land after the fixes it depends on.
