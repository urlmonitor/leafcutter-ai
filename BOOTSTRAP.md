# BOOTSTRAP.md — Portable Dev Workflow Adoption Guide (in-package)

> This is the in-package version of the adoption guide.
> The project-root copy at `BOOTSTRAP.md` is installed by `build.py` during setup.
> Both files cover the same ground — this one lives inside the package for reference.

---

See the repo-root `BOOTSTRAP.md` for the full step-by-step guide.

For AI-assisted setup (automated config detection + build), see `SETUP.md` in this directory.

## Quick Reference

1. Prerequisites: Python ≥ 3.11, Poetry, pre-commit, git repo with ≥ 1 commit
2. Copy portable package: `.claude/`, `scripts/commit_guardian/`, `scripts/doc_compliance/`, `tickets/templates/`, `.agents/`
3. Edit `scripts/commit_guardian/commit_guardian.json`
4. Edit `.claude/skills_config.json`
5. Edit `scripts/doc_compliance/doc_compliance.json` (see `scripts/doc_compliance/BOOTSTRAP_GUIDE.md`)
6. Run `python leafcutter/scripts/build.py --target-dir .` — this generates `CLAUDE.md` from `templates/CLAUDE.md.template` with your `skills_config.json` values injected. Fill in any remaining `<!-- TODO: fill in ... -->` sections.
7. Run `python leafcutter/scripts/build.py` — this generates `.pre-commit-config.yaml`
   at the project root (merging package hooks with any project-specific hooks you add manually).
   Re-run after editing `commit_guardian.json → hooks_manifest` to propagate changes.
7a. (Optional) Seed architecture-doc convention scaffolds into `docs/architecture/`:
    ```bash
    python leafcutter/scripts/build.py --seed-docs
    ```
    This copies five starter files (README, FRONTMATTER, L1 stub, ADR README, ADR template)
    into `docs/architecture/` using missing-only semantics — existing files are never
    overwritten. Skip this step if you already have a populated `docs/architecture/`.
    See `SETUP.md §Architecture Doc Scaffolds` for details.
8. `pre-commit install && pre-commit install --hook-type post-commit`
9. Smoke test: `/build-feature` on a trivial ticket

For AI-assisted setup:
- Ask your AI assistant to "set up the dev workflow" and point it to `SETUP.md`
- The AI reads `SETUP.md`, auto-detects values, generates `skills_config.json`, and runs `build.py`

## Extending the Package Post-Adoption

After initial setup, use `workflow-architect` to extend the package — do not edit
package files directly. The agent knows the full package surface and dispatches the
right skill for each extension type:

- **Add a new hook**: Ask `workflow-architect` to create a hook. It uses the `create-hook`
  skill to add the script, register it in `commit_guardian.json`, and compile via `build.py`.
- **Promote an agent**: Ask `workflow-architect` to add an agent to the package. It uses
  `add-agent-to-package` to write the template, register in `agent_registry.json`, and
  update `docs/agents/README.md`.
- **Promote a skill**: Ask `workflow-architect` to add a skill to the package. It uses
  `add-skill-to-package` to copy the skill directory to `templates/skills/`.
- **Audit what's missing**: Ask `workflow-architect` to run a package audit. It uses the
  `package-audit` skill to run `scripts/package_audit.py` and present a gap report.

See [ADR-020](docs/architecture/adrs/ADR-020-leafcutter-package-boundary.md)
for the boundary classification rules (portable vs project-specific).
