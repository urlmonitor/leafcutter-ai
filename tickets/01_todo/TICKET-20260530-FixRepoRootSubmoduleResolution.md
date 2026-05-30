---
title: "Fix _resolve_repo_root() to handle .git-as-file (submodule) topology"
status: done
components:
  - build_pipeline
created: 2026-05-30
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/release/compute_next_version.py
  - unit_tests/release/test_compute_next_version_repo_root.py
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  sql-query: not_needed
  frontend-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  change-scope-reviewer: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  pr-reviewer: needed
  user-surface-smoker: not_needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
user_facing_surface: null
---

# Fix _resolve_repo_root() to handle .git-as-file (submodule) topology

## Actor / Goal

In order for `compute_next_version.py` to produce the correct version when
leafcutter is installed into a consumer project as a submodule, we need to
fix `_resolve_repo_root()` so it recognises `.git` as a file (the submodule
pointer) and not only as a directory, preventing it from silently resolving
to the consumer repo root instead of the leafcutter package root.

## Context

When leafcutter is cloned as a submodule at `<consumer>/leafcutter/`, the
script lives at:

```
<consumer>/leafcutter/scripts/release/compute_next_version.py
```

The current implementation (lines 29–44) checks:

```python
p2 = resolved_self.parents[2]   # <consumer>/leafcutter/
if (p2 / ".git").is_dir():
    return p2
return resolved_self.parents[3] # <consumer>/
```

In a git submodule, `<consumer>/leafcutter/.git` is a **file** (the submodule
pointer), not a directory. `is_dir()` returns False, so the function falls
through to `parents[3]` — the consumer project root — which does have a `.git`
directory. The wrong root is returned silently.

Consequences of the wrong root:

- `_find_last_version_tag()` runs `git tag -l 'v*'` in the consumer repo.
  Consumer repos typically have no `v*` tags, so `last_tag` falls back to
  `"v0.0.0"`.
- `_resolve_changelogs_dir()` looks for `changelogs/` under the consumer
  root and finds unrelated consumer changelogs. Because `last_tag` is None,
  every `.md` file in that directory is considered, producing an incorrect
  bump based on consumer change history.
- The final version is always `v0.1.0` (or some other wrong value), regardless
  of the actual leafcutter release history.
- `build.py` calls this at line ~524 (`computed_version = _compute_version_str(package_root)`),
  so every consumer build receives a wrong version string embedded in the package.

The fix has two candidate forms (see Implementation Tasks). The preferred approach
is to replace `is_dir()` with an `exists()` check (covers both file and directory
forms of `.git`) at `parents[2]`. The alternative — using `git rev-parse
--show-toplevel` with `cwd=Path(__file__).parent` — is more robust across
unusual topologies but introduces a subprocess dependency for a startup path.

This bug was introduced when the consumer-project layout support was added to
`_resolve_repo_root()`. The fix is a one-line change at line 42.

Related ticket: `TICKET-20260528-FixComputeNextVersionBugs.md` (fixes different
bugs in `_compute_bump()` and `_changelog_entries_since()`; no overlap).

## Acceptance Criteria

```gherkin
Given the script is located at <consumer>/leafcutter/scripts/release/compute_next_version.py
  And <consumer>/leafcutter/.git is a file (submodule pointer)
  And <consumer>/leafcutter/ contains the leafcutter v* git history
When _resolve_repo_root() is called
Then it returns <consumer>/leafcutter/ (not <consumer>/)

Given a standalone development workspace where the script is at <repo_root>/scripts/release/compute_next_version.py
  And <repo_root>/.git is a directory
When _resolve_repo_root() is called
Then it returns <repo_root> (existing behaviour preserved)

Given a consumer project with no v* tags in the consumer repo
  And leafcutter is installed as a submodule with its own v* tags
When compute_next_version.py is run from the consumer project
Then the script reads tags from the leafcutter submodule repo (not the consumer repo)
  And returns the correct leafcutter version (not v0.1.0 or v0.0.0)

Given the repo root resolved by _resolve_repo_root() is the correct leafcutter root
When _find_last_version_tag() is called
Then it discovers existing leafcutter v* tags
  And does not fall back to v0.0.0 baseline
```

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### python-coder

- [ ] In `_resolve_repo_root()` (line 42 of `scripts/release/compute_next_version.py`),
  change:
  ```python
  if (p2 / ".git").is_dir():
  ```
  to:
  ```python
  if (p2 / ".git").exists():
  ```
  `Path.exists()` returns True whether `.git` is a directory (normal clone) or a
  file (submodule pointer / git worktree). This is the minimal correct fix.

- [ ] Add a clarifying comment on the changed line to document why `exists()` is
  used instead of `is_dir()`:
  ```python
  # .git may be a directory (normal clone) or a file (submodule / worktree link)
  if (p2 / ".git").exists():
  ```

- [ ] Update the docstring of `_resolve_repo_root()` (lines 30–39) to document the
  third supported topology: submodule installation where `.git` is a file:
  ```
  3. Consumer project submodule environment:
     __file__ = <consumer>/leafcutter/scripts/release/compute_next_version.py
     parents[2] = <consumer>/leafcutter/  — .git is a *file* (submodule pointer)
     .git exists() == True, so parents[2] is returned correctly
  ```

- [ ] Update the `# DECISION HISTORY` block at the bottom of the module with a
  dated entry (2026-05-30) describing the submodule topology bug and the
  `is_dir()` → `exists()` fix.

### test-writer

- [ ] Create `unit_tests/release/test_compute_next_version_repo_root.py` with:

  - `test_resolve_repo_root_git_as_directory`:
    Create a temp directory tree simulating a standalone dev workspace:
    `<tmpdir>/scripts/release/compute_next_version.py` (or mock `__file__`),
    `<tmpdir>/.git/` as a real directory.
    Monkeypatch `Path(__file__).resolve()` to point into the tree.
    Assert `_resolve_repo_root()` returns `<tmpdir>`.

  - `test_resolve_repo_root_git_as_file_submodule`:
    Create a temp directory tree simulating a submodule consumer environment:
    `<tmpdir>/leafcutter/scripts/release/compute_next_version.py` (mocked),
    `<tmpdir>/leafcutter/.git` as a plain **file** (write any content).
    `<tmpdir>/.git/` as a real directory (consumer root, should NOT be returned).
    Assert `_resolve_repo_root()` returns `<tmpdir>/leafcutter/` (not `<tmpdir>/`).

  - `test_resolve_repo_root_no_git_at_p2_falls_back_to_p3`:
    Create a tree where `parents[2]` has no `.git` at all but `parents[3]` has
    a `.git` directory. Assert `_resolve_repo_root()` returns `parents[3]`.
    (Regression guard for the existing fallback path.)

  - `test_find_last_version_tag_uses_correct_repo_root`:
    Monkeypatch `_resolve_repo_root` to return a temp dir, mock `subprocess.run`
    to return `b"v0.2.5\n"` only when `cwd` equals that temp dir. Assert
    `_find_last_version_tag()` returns `"v0.2.5"`.

## Risk & Safety

- Touches money? No.
- Touches data? No — `compute_next_version.py` is a read-only scanning script
  unless invoked with `--tag`. This fix only affects the root-resolution path.
- Reversibility? Fully reversible. `Path.exists()` is strictly broader than
  `Path.is_dir()` — it accepts both forms. Reverting restores the prior behaviour.
- Shared contracts? `_resolve_repo_root()` is a private helper called only within
  this module. No external callers. The return type (`Path`) is unchanged.
- Edge cases: `Path.exists()` follows symlinks. If `.git` is a symlink (unusual
  but valid in some CI setups), it will resolve correctly as long as the symlink
  target exists. This is the correct behaviour.
- Build pipeline impact: `build.py` calls `_compute_version_str()` on every
  consumer build (line ~524). After this fix, that call will resolve to the
  correct leafcutter root and produce the correct version, eliminating the
  silent `v0.1.0` regression every consumer currently experiences.
