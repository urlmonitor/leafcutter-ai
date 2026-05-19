# Brainstorm: Leafcutter Self-Hosting Structure

**Date:** 2025-05-19
**Status:** Brainstorm (not a decision)

## The Core Confusion

The root directory is simultaneously:
- The leafcutter package's home repository
- A "target project" that build.py writes into
- The development environment for working on leafcutter itself

This means `docs/vision.md` is a build output (the template default), `tickets/` holds template lifecycle scaffolding, and `.claude/agents/` contains compiled agents that are also the tools you use to develop leafcutter. A newcomer cloning the repo cannot tell what is source and what is output.

---

## Option A: Single Repo, Leafcutter Eats Itself

Leafcutter's own build targets the root. Root-level `docs/`, `tickets/`, agents, skills are all leafcutter's own development artifacts.

| Pros | Cons |
|------|------|
| Zero extra repos or tooling | Build outputs and source templates live in the same tree -- hard to reason about what is generated vs hand-written |
| "Dogfooding" surfaces real UX issues immediately | `docs/vision.md` at root is a template placeholder, not actual leafcutter vision -- confusing until manually overwritten |
| Single clone to get everything | `git status` mixes template source changes with compiled output changes; .gitignore only partially helps |
| CI runs build.py and tests in one place | Recursive dependency: changing a template changes the tool you used to change the template |

## Option B: Two Separate Repos

`leafcutter-ai` becomes its own repo. Consumer projects (including a `leafcutter-dev` repo) install it as a submodule or copy.

| Pros | Cons |
|------|------|
| Clean package boundary: leafcutter repo has only source, no compiled output | Two repos to maintain, PR across, keep in sync |
| Consumer experience is realistic: you clone a project, add leafcutter, run build | Developing leafcutter requires switching between repos constantly |
| No confusion about what is source vs output | Submodule pain (nested git, version pinning, contributor onboarding friction) |
| Tests run against a real "install into blank project" scenario | Overhead is disproportionate for a solo/small-team project at this stage |

## Option C: Single Repo, Separate Config Targets

One repo, but leafcutter's own development artifacts live under `leafcutter-ai/` (its own `docs/`, `tickets/`, agents). The root-level directories remain build outputs for testing/demo purposes. `paths.json` and `skills_config.json` inside `leafcutter-ai/` point inward via `docs_root`, `tickets_inbox_path`, etc.

| Pros | Cons |
|------|------|
| Source vs output is unambiguous: `leafcutter-ai/docs/` = leafcutter's own docs; `docs/` = compiled demo output | Two sets of `docs/`, `tickets/` -- cognitive load for "which one do I edit?" |
| `leafcutter-ai/` already has its own `docs/`, `tickets/`, `CLAUDE.md` -- this is partially true today | `paths.json` currently assumes paths are relative to target root, not package root; needs refactoring |
| Single clone, single repo | Build.py would need a `--self` or `--target=leafcutter-ai` mode to install agents/skills for leafcutter dev |
| Newcomers can `rm -rf docs/ tickets/ .claude/agents/` and rebuild cleanly | Root-level outputs become "example project" artifacts that nobody maintains |

## Option D: Templates Are the Source of Truth (No Compilation)

Skip compilation entirely. Agents, skills, and hooks reference templates directly at runtime via symlinks or path resolution. Build.py becomes optional (only needed when installing into a consumer project).

| Pros | Cons |
|------|------|
| Eliminates the "what is generated" question entirely for development | Claude Code expects files at `.claude/agents/`, `.claude/skills/` -- symlinks may not work on Windows/WSL |
| No build drift, no manifest, no staleness | Templates contain `{{config.*}}` placeholders that need resolution -- raw templates are not valid prompts |
| Simplest mental model for contributors | Breaks the entire config-injection architecture that makes leafcutter portable across projects |

---

## Recommendation: Option C (Single Repo, Separate Config Targets)

**Reasoning:**

1. Option C is 80% done already. `leafcutter-ai/` has its own `docs/`, `tickets/`, and `CLAUDE.md`. The remaining work is teaching build.py to target `leafcutter-ai/` for self-hosting and cleaning up root-level artifacts.

2. It preserves the single-repo simplicity that matters at this stage while making the boundary explicit. The rule becomes: "edit inside `leafcutter-ai/` for leafcutter development; root-level directories are build outputs you can nuke and rebuild."

3. It gives consumers a realistic preview: the root IS what their project will look like after installing leafcutter.

4. Option D is elegant but incompatible with `{{config.*}}` injection. Option B adds real overhead for marginal clarity. Option A is the status quo and the status quo is confusing.

---

## Migration Path

1. **Add a `--self` flag to build.py** that sets `target_root` to the leafcutter-ai directory itself, using `leafcutter-ai/config/skills_config.default.json` as config. This compiles agents/skills into `leafcutter-ai/.claude/agents/` etc. for leafcutter development.

2. **Move leafcutter's own vision, roadmap, glossary into `leafcutter-ai/docs/`** (most already exist there). Root-level `docs/vision.md` becomes the template output only.

3. **Update root `.gitignore`** to explicitly mark root-level `docs/`, `tickets/`, `.claude/agents/`, `.claude/skills/` as generated. Add a `GENERATED.md` or comment in each explaining "this is a build output; edit the template in `leafcutter-ai/templates/`."

4. **Update CLAUDE.md at root** to direct contributors to `leafcutter-ai/CLAUDE.md` for package development and explain that root-level artifacts are compiled outputs.

5. **Add a `make dev` or `build-self.sh`** one-liner that runs `build.py --self` so leafcutter developers get their own agents/skills installed.

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| `paths.json` assumes target-root-relative paths; `--self` mode needs package-root-relative paths | Medium | `--self` flag can compute an offset or override `paths.json` entries |
| Contributors edit root-level docs instead of `leafcutter-ai/docs/` | Low | `.gitignore` + header comments in generated files + CLAUDE.md instructions |
| CI may need to run build twice (once for testing consumer output, once for self-hosting) | Low | Make `--self` a separate CI step; consumer build is the default |
| Windows/WSL path handling for nested target directories | Low | Already handled by `Path.resolve()` in build.py |
| Existing tickets at root may need manual migration to `leafcutter-ai/tickets/` | Low | One-time move; update any cross-references |
