---
title: "KI-BP-012 — The self-hosted build validates `agent_registry.json` against a path nothing ever writes to, and the deployed workflow reads a different path entirely"
description: "KI-BP-012 — The self-hosted build validates `agent_registry.json` against a path nothing ever writes to, and the deployed workflow reads a different path entirely"
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

# KI-BP-012 — The self-hosted build validates `agent_registry.json` against a path nothing ever writes to, and the deployed workflow reads a different path entirely

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/build_phases.py:1928` (`registry_path` used by the self-description
  validator), `:1863` (docstring naming the same path), `:62` (`REGISTRY_PATH`, the
  source-side constant the build reads from) · `.leafcutter/workflows/plan-feature.js:1749`
  (the deployed workflow's own registry read)

**Symptom.** A consumer install has `agent_registry.json` at neither path the codebase
actually uses — and the build's own validation cannot detect that, because the only layout
it has ever run in is the one where the check is structurally incapable of failing.

**Mechanism.** `build_phases.py:1928` computes `registry_path = target_root / "config" /
"agent_registry.json"` and validates the registry there; the docstring at `:1863` describes
the same path as holding the required registry fields. Nothing in the build ever *copies*
`config/agent_registry.json` to `target_root / "config" /`. A grep of `build_phases.py` for
the filename returns only the source-side constant, the validation read, doc comments, and
error-hint strings — no write:

```text
$ grep -n "agent_registry.json" scripts/build_phases.py
10:    agent_registry.json and passes it + the skills_root to
62:REGISTRY_PATH = PACKAGE_ROOT / "config" / "agent_registry.json"
465:    Registry injection (ticket 29): loads ``agent_registry.json`` once and passes
1863:    in ``target_root / "config" / "agent_registry.json"`` for required registry
1928:    registry_path = target_root / "config" / "agent_registry.json"
2005:                        f"  Fix hint: Add '{field}' to the agent's entry in config/agent_registry.json."
2072:            "Set self_description_enforcement='error' in config/agent_registry.json "
2124:    registry entry from ``config/agent_registry.json``, calls
2907:#   agent_registry.json once per phase call and passes agents, registry_path,
```

In the self-hosted layout this validation passes trivially, because `target_root/config/` IS
the package's own source `config/` directory — the same file `REGISTRY_PATH` reads from. The
check has therefore never been meaningful in the one place it has ever run: it validates the
source against itself.

Meanwhile the deployed `/plan-feature` workflow reads the registry from a *different*
location. `.leafcutter/workflows/plan-feature.js:1749` runs
`"cat .leafcutter/config/agent_registry.json\n"`. So `build_phases.py` expects
`<target>/config/agent_registry.json` and the deployed workflow expects
`<target>/.leafcutter/config/agent_registry.json` — and nothing in the build populates
either path in a real consumer install (see KI-BP-003's fourth occurrence: `.leafcutter/config/`
deploys only `commit_guardian` and `feedback_categories.yaml`).

**Consequence.** A consumer install has the registry at neither path. The build's own
validation cannot catch this, because in the only layout where it runs — self-hosted — it is
reading the package's source copy, not a deployed one, so it reports success regardless of
whether either deployed path is populated.

**Relationship to other entries.** Same root-cause shape as KI-BP-003 (see that entry's
fourth occurrence): `config/` is not deployed. Both are unfixed instances of the rule
`BP-900g-8-ii` already states — "the deployed-dependency closure covers the data and
configuration files a script reads, not only the modules it imports." `KI-BO-018` (in
`docs/known-issues/build-orchestration.md`) is a related but distinct failure one layer up:
`/plan-feature`'s registry read there succeeds only *incidentally*, because the process
working directory happened to be the workspace parent that holds a populated `.leafcutter/`
— the same non-portable assumption, caught in the one case where it happens to resolve.

**Fix direction.** Anchor the validator's `registry_path` and the deployed workflow's read to
the same, actually-deployed location, and make the build copy `config/agent_registry.json`
there. Until then, do not trust a passing self-hosted validation run as evidence that a
consumer install's registry is reachable by anything that runs against deployed output.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2 (the deployed layout differs
from the source you are reading), in a validates-against-itself sub-form: the only layout
the check has ever run in is the one where target and source are the same directory, so it
has never been able to fail.

---
