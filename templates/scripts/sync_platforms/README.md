---
title: "sync_platforms"
type: "reference"
status: "active"
created: "2026-06-03"
last_updated: "2026-06-03"
components:
  - "sync_platforms"
---

# sync_platforms

Bidirectional synchronization of agents and skills across active AI platform
directories (Claude, Gemini, Cursor, Copilot, Cline).

## Purpose

When a leafcutter project uses more than one AI platform, agents and skills can
drift out of sync as they are edited in one platform directory but not copied to
the others. `sync_platforms.py` closes that gap by propagating the most recently
modified version of each file across all active platform directories.

If the script detects that it is running inside the leafcutter source repository
(by testing for the presence of a `templates/` tree), it also performs a one-way
sync from `templates/agents/` and `templates/skills/` into every active platform
directory, keeping the canonical source templates dominant.

## Usage

```bash
python scripts/sync_platforms/sync_platforms.py
```

The script resolves the project root automatically as three directories above its
own location (`__file__.parent.parent.parent`). No arguments are required.

### Prerequisites

- A `skills_config.json` file must exist in one of the platform directories
  (e.g. `.claude/skills_config.json`). The script searches all known platform
  directories and falls back to a recursive project-wide search.
- `skills_config.json` must declare at least one active platform under the
  `"platforms"` key:
  ```json
  {
    "platforms": {
      "claude": true,
      "antigravity": false
    }
  }
  ```

## Key Design Decisions

**mtime-based newer-file detection.** Files are copied from source to target only
when the source modification time (`st_mtime`) is strictly greater than the target
modification time or the target does not yet exist. This avoids unnecessary writes
and preserves local edits made directly in a platform directory.

**Supported platform directories.** The script maps platform names to their
canonical directory names:

| Platform name | Directory |
|---|---|
| `claude` | `.claude/` |
| `antigravity` | `.gemini/` |
| `cursor` | `.cursor/` |
| `copilot` | `.github/` |
| `cline` | `.cline/` |

**Source-repo detection.** The presence of a `templates/` directory at the
project root is used as a heuristic to identify the leafcutter source
repository. When detected, template sources are given precedence via a
one-way sync from `templates/agents/` and `templates/skills/` into the
platform directories — this prevents local edits inside a platform directory
from overwriting the canonical template when the build has run.

**No deletion semantics.** The sync only copies files; it never deletes files
from a target directory. Files that exist in a target but not in the source are
left in place.

## Further Reading

For deeper context on the synchronization workflows, including the architectural
decision to use mtime as the consistency signal and the scope of platforms
supported, see
[docs/workflows/sync_platforms.md](../../docs/workflows/sync_platforms.md).
