# DEPRECATED: templates/commit-guardian/

**This directory is deprecated as of EPIC-PortableInstallHardening T03 (2026-05-18).**

The canonical template location for commit-guardian scripts is now:

```
leafcutter/templates/scripts/commit_guardian/
```

All scripts from this directory have been migrated to the canonical path. The builder
(`build_phases.py`, `build_precommit.py`, `build.py`) now reads from the canonical
path first, with a fallback to this directory for backward compatibility.

**Migration action for consumer projects:**
- Re-run `python leafcutter/scripts/build.py --target-dir .` to receive
  the updated layout.
- If you have customised files in this directory, copy them to the canonical path.

This directory will be removed in a future release.
