---
title: "Web App CI Gate — Pull Request to Merge Decision Sequence"
description: "L3 sequence diagram of the web-app CI gate: a pull request that changes leafcutter-web/ triggers the blocking 'Web app build and type-check (blocking)' check, whose pass/fail result is reported on the pull request and gates the merge decision — showing both the failing (build/type error) and passing (clean build) paths."
type: architecture
diagram_type: sequence
flight_level: L3-Component
status: active
created: 2026-08-12
last_updated: 2026-08-12
components:
  - build_pipeline
parent: docs/architecture/diagrams/c2-006-feature-to-merged-pr.md
related_docs:
  - docs/architecture/diagrams/c2-006-feature-to-merged-pr.md
related_code:
  - .github/workflows/ci.yml
source_ticket: tickets/00_inbox/epics/EPIC-ChangesToTheWebAppCantReachUsersBroken/05_TICKET-20260721-BP-1400a-3.md
tags:
  - web-app
  - ci-gate
  - build-typecheck
  - branch-protection
  - merge-gate
---

# Web App CI Gate — Pull Request to Merge Decision Sequence

This diagram documents the **web-app CI gate**: the flow from a pull request that
changes the web app (`leafcutter-web/`), through the automated build/type-check
check running in CI, to the pass/fail result being reported on the pull request
and gating the merge decision.

Three participants take part in the flow:

1. **The pull request** — a PR that changes one or more files under
   `leafcutter-web/`.
2. **The CI system running the check** — GitHub Actions running the
   `web-app-build` job, whose stable check name is
   **`Web app build and type-check (blocking)`**. The job runs `npm ci` then
   `npx next build` in `leafcutter-web/`; because `next build` runs the
   TypeScript compiler (`tsc`), a type error fails the build and therefore the
   check.
3. **The merge gate** — branch protection / required-status-checks, which
   consults the reported check result to decide whether the pull request may
   merge.

> **Stable check-name contract.** The check label
> **`Web app build and type-check (blocking)`** is the exact, stable
> `ci.yml` job name that the branch-protection required-status-checks wiring
> (BP-1400a-4) depends on. This diagram uses that same label — a divergent
> label would silently decouple the gate from the check.

> **Blocking, not advisory.** The `web-app-build` job sets **no**
> `continue-on-error`, so a build failure or any type error exits non-zero and
> reports a failing (blocking) result — in contrast to the informational
> `typecheck` (mypy) job, which is advisory.

---

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Contributor
    participant PR as Pull Request<br/>(changes leafcutter-web/)
    participant CI as CI System<br/>(GitHub Actions — "Web app build and type-check (blocking)")
    participant Gate as Merge Gate<br/>(branch protection / required status checks)

    Dev->>PR: Open / update a PR touching leafcutter-web/
    PR->>CI: Trigger the "Web app build and type-check (blocking)" check
    Note over CI: web-app-build job:<br/>npm ci → npx next build<br/>(next build runs tsc, so a type error fails the build)

    alt Build or type error (failing path)
        CI-->>PR: Report FAILING (non-passing, blocking) result
        PR->>Gate: Failing required check reported on the PR
        Gate-->>PR: Merge blocked — pull request is NOT mergeable
    else Clean build and type-check (passing path)
        CI-->>PR: Report PASSING result
        PR->>Gate: Passing required check reported on the PR
        Gate-->>PR: Merge NOT blocked by this check
    end
```

Parent: [Feature to Merged PR — End-to-End Sequence Diagram](../diagrams/c2-006-feature-to-merged-pr.md)

---

## Flow walk-through

1. **A pull request changes the web app.** A contributor opens or updates a
   pull request that touches one or more files under `leafcutter-web/`.

2. **The CI system runs the blocking check.** GitHub Actions runs the
   `web-app-build` job — the **`Web app build and type-check (blocking)`**
   check — which installs dependencies with `npm ci` and builds the web app with
   `npx next build`. Because `next build` invokes the TypeScript compiler, the
   build and the type-check happen in the same step.

3. **The result is reported on the pull request.**
   - **Failing path** — if the build fails or any type error is reported, the
     job exits non-zero and the check reports a **failing (non-passing,
     blocking)** result on the pull request.
   - **Passing path** — only when the web app builds and type-checks with no
     errors does the check report a **passing** result.

4. **The merge gate consults the reported result.** The merge gate (branch
   protection / required status checks) reads the reported result: a failing
   result blocks the merge (the pull request is not mergeable), while a passing
   result means the merge is not blocked by this check.

> This diagram is documentation-only. It depicts exactly the behaviour
> specified by BP-1400a-1 (the blocking build/type-check check) and BP-1400a-4
> (the required-status-checks wiring). It does not assert any retry,
> notification, or other behaviour beyond that shared pull-request-to-merge
> flow.

## Cross-References

- [Feature to Merged PR — End-to-End Sequence Diagram](../diagrams/c2-006-feature-to-merged-pr.md) —
  the parent flow whose merge step this web-app CI check gates.
- [`.github/workflows/ci.yml`](../../../.github/workflows/ci.yml) — the CI
  configuration that defines the `web-app-build` job
  (`Web app build and type-check (blocking)`).
