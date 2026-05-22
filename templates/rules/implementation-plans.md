---
trigger: glob
globs: *
---

# Implementation Plans

When we create implementation plans, we HAVE to create a thorough checklist, which includes:

1. **The files we want to change**: Including the specific change to be made.
2. **A check for updating documentation**: Ensure all related documentation is updated.
3. **A check for updating business requirements**: Ensure business requirements in the `docs` folder are updated if applicable.
4. **creating unit tests**: Ensure a step is added to create unit tests for the changes.
5. **updating architecture diagrams**: Ensure a step is added to update any relevant architecture diagrams.

**Pre-Check Requirement**:
Before providing the plan to the user, we MUST check existing documentation and architecture diagrams to have a full picture of what we are building. DO NOT skip this research phase.

**STRICT WORKFLOW ENFORCEMENT**:
- **NEVER** change code without asking the user OR having an explicit ticket assigned.
- If functionality is discovered missing during an epic, **DO NOT** spontaneously implement it. You must add new tickets for the missing features.
- This ensures all changes properly trigger documentation updates, code splitting, architecture diagrams, and unit tests as mandated by the ticket lifecycle.

<!--
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-22 [AI]: Added STRICT WORKFLOW ENFORCEMENT section to prevent untracked code changes and enforce ticket-driven development.
====================================================================
-->
