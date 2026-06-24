# IT-PO learnings — the TRACKED-IN-GIT deployment-gap axis (BP-900f) + READ-source vs WRITE-output split

Captured 2026-06-24 during BP-900f / BP-1000a-5 / BP-1200a-1-iii technical
enrichment, component: build-pipeline. S9 capture-learning skill was absent in
this repo (route-learning/capture-learning not installed), so persisted directly
as a memory file per the existing feedback_itpo_*.md convention.

## A FOURTH deployment-gap axis: source is TRACKED-IN-GIT (BP-900f)

The build-pipeline deployment-completeness family had three axes
(feedback_ba_bp1000_source_template_parity.md). BP-900f adds a fourth — keep all
distinct, never duplicate:
- BP-1000 (a-d): byte-equality of scripts present in BOTH scripts/ AND templates/.
- BP-900b: build.py PREFLIGHT — template script refs vs the deployable manifest.
- BP-900e: registry/template-ref promised script has a deploy-source copy AT ALL.
- BP-900f (NEW): each deployable script's source actually lives in VERSION CONTROL
  (git-tracked), not merely present in the working tree. The orthogonal "on-disk
  but untracked" trap. Fresh-clone reproducible. The gitignored scripts/feedback/
  (commit 83737a44) is the live regression that motivated it, but the guard is
  general (no per-directory allowlist).

The mechanical primitive for BP-900f is a `git ls-files`-based tracked/untracked
classifier over the deployable-script source set (NOT filesystem presence). The
BA already pinned this correctly in BP-900f-1's it_requirements; verify it says
"from the git index" and "resolve paths relative to repo root".

## READ-source-of-truth (tracked templates mirror) vs WRITE-output (gitignored) — the recurring split

Three ACs this run all turn on the SAME structural distinction, and conflating
them is the trap:
- The build's READ source-of-truth for feedback should be the TRACKED
  templates/scripts/feedback/ mirror (mirroring templates/scripts/commit_guardian/,
  scanned by _manifest_commit_guardian_scripts). BP-1000a-5 relocates it there;
  repoint _manifest_feedback_scripts (build.py) + feedback_src/build_feedback
  (build_phases.py).
- The build's WRITE output (deployed scripts/feedback/ in a target / self-build)
  stays a GITIGNORED build output per ADR-001/ADR-004. The relocation must NOT
  commit build outputs into source control and must NOT change where the build
  writes. BP-1200a-1-iii (Approach 1 per ADR-016) bridges the gitignored deployed
  output to tests via the install_shims shim_map — that is a DIFFERENT directory
  with a different lifecycle.
Standing it_requirement to stamp on every such AC: "READ source = tracked
templates mirror; WRITE/deployed output stays gitignored; do not commit outputs;
build.py round-trip parity per ADR-001/013."

## Whole cluster is single-agent python-coder — no llm-expert split

All behavioral leaves here edit scripts/build.py, scripts/build_phases.py,
scripts/build_propagation_audit.py + pytest. No template/SKILL/agent-prose
surface, no SQL, no UI. So unlike the generator/supervisor-boundary or
sign-off-gate features (which split python-coder + llm-expert), this cluster has
NO multi-agent boundary -> NO split. The BA's uniform python-coder stamp was
correct; the IT-PO job was almost entirely it_requirements + a doc_link status
fix (ADR-016 planned->exists, now authored) + contract-shape tightening.

## L0/L1 composites stay unenriched (recurs)

BP-900f is an L1 — correctly carries assigned_agent: null. Do NOT assign an agent
to it even when the user lists it among the batch. Only L2/L3 leaves get
assigned_agent + it_requirements (matches the GE-111 learning).

## Edit tool may be unavailable in the it-po context — use Write on full files

This run the Edit tool was not enabled; enrichment was applied by Write-ing the
full AC file (after Read). Preserve every BA field verbatim (especially criteria)
and record the change in a structured amended_by {reason: it-po-technical-
enrichment, ...} entry. AC folders here are UNTRACKED (??), so git diff shows
nothing — verify via grep/Read of the changed line ranges instead.
