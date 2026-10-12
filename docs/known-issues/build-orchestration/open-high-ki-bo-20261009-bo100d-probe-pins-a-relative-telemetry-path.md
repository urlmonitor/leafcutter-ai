---
title: "KI-BO-20261009-bo100d-probe-pins-a-relative-telemetry-path — ten approved BO-100d ACs pin the pre-drive sink probe to the relative path debugging/logs/agent_telemetry.jsonl, so once INF-500d-4 moves the telemetry stream to a declared absolute root the probe tests a file nobody writes to"
description: "high, latent — BO-100d and nine of its descendants (all readiness approved, work_status todo) name the telemetry sink by the workspace-relative string debugging/logs/agent_telemetry.jsonl, and their pre-drive probe appends to it from the worktree. INF-500d-4 (PR #1107) moves every log in debugging/logs/ to one absolute root fixed at build time in config/knowledge_sink.json. After that lands, a probe built as written passes against a worktree-local file while the real stream may be unwritable: a false green. Fix direction from INF-500d-4's IT PO: probe the declared operational_telemetry_stream through INF-500d-4-iii's location query and fail as blocked when the declaration is missing. Changing the criteria is the BO owner's call."
type: reference
category: reference
status: active
created: '2026-10-09'
last_updated: '2026-10-09'
components:
  - build_orchestration
  - agent_telemetry
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/acceptance-criteria/build-orchestration/BO-100-smart-sequencing/BO-100d.yaml
  - docs/acceptance-criteria/build-orchestration/BO-100-smart-sequencing/BO-100d-1a.yaml
  - docs/acceptance-criteria/infrastructure/INF-500-operational-observability/INF-500d-4.yaml
---

# KI-BO-20261009-bo100d-probe-pins-a-relative-telemetry-path — ten approved BO-100d ACs pin the pre-drive sink probe to the relative path `debugging/logs/agent_telemetry.jsonl`, so once INF-500d-4 moves the telemetry stream to a declared absolute root the probe tests a file nobody writes to

- **Severity:** high (silent wrong behaviour), latent. Nothing is wrong yet. The BO-100d probe
  helper is not built, and today the telemetry writer also resolves to the relative path (see
  Cause). The defect becomes live when two things are both true: INF-500d-4's writers default to
  the declared absolute root, and a probe is built to the BO-100d criteria as they stand. From
  then on the pre-drive gate passes against a worktree-local file while the stream the drive
  actually writes to may be unwritable. That is a false green on a gate whose only job is to
  prevent silent telemetry loss.
- **Status:** open. Needs a criteria change on the ten ACs by the build-orchestration owner. This
  entry does not edit them, and no implementer may silently re-point their probe (INF-500d-4
  it_requirements, "BO-100d RECONCILIATION"). The order in which BO-100d-1a and INF-500d-4 land is
  undecided, and stays a hazard until it is decided.
- **Occurrences:** 1 (2026-10-09, found during INF-500d-4's IT PO enrichment, PR #1107). Found by
  review, not by a failing drive.
- **First seen:** 2026-10-09 · **Last seen:** 2026-10-09
- **Where:** verified on origin/main `ed83d9f77`, all under
  `docs/acceptance-criteria/build-orchestration/BO-100-smart-sequencing/`. All ten are
  `readiness: approved`, `work_status: todo`.

  | AC | Lines naming `debugging/logs/agent_telemetry.jsonl` |
  |---|---|
  | `BO-100d.yaml` | :56 (`notes` only; `criteria` does not name it and `it_requirements` is `[]`) |
  | `BO-100d-1.yaml` | :15, :21 (`criteria`) |
  | `BO-100d-1-i.yaml` | :16 (`criteria`) |
  | `BO-100d-1-ii.yaml` | :16, :22 (`criteria`); :34 (`it_requirements`) |
  | `BO-100d-1a.yaml` | :15, :21 (`criteria`); :47 (`delivers_to` contract, including `sink_path`) |
  | `BO-100d-1b.yaml` | :15, :21 (`criteria`); :38 (`it_requirements`); :44 (`expects_from` contract) |
  | `BO-100d-2.yaml` | :15 (`criteria`) |
  | `BO-100d-2-i.yaml` | :15, :18 (`criteria`); :34 (`it_requirements`) |
  | `BO-100d-2a.yaml` | :15 (`criteria`); :33 (`it_requirements`); :39 (`expects_from` contract) |
  | `BO-100d-2b.yaml` | :15 (`criteria`) |

  Existing probe sites that append to the same relative path on origin/main (prose, not the
  BO-100d-1a helper, which does not exist yet; no `sink_unreachable` or pre-drive gate is found
  in `scripts/` or `templates/workflows-js/`):
  `templates/skills/building-epics/SKILL.md:41` (§1.0, warn-not-halt),
  `templates/agents/epic-supervisor.md:243` (check 7, deprecated agent), and the repository
  `CLAUDE.md:551-556` ("Feedback sink reachable").

## Symptom

None observed yet. The predicted symptom: after INF-500d-4 lands, a drive starts inside a
per-drive worktree, the pre-drive probe appends one line to
`<worktree>/debugging/logs/agent_telemetry.jsonl`, succeeds, and lets the drive dispatch. The
drive's telemetry writers then append to the declared absolute `operational_telemetry_stream`
under `operational_log_root`. If that location is unwritable, every event is lost and the gate
reported the sink reachable. This is the same failure BO-100d was written to prevent (23
`submit-failed` events in one drive with zero telemetry captured), now behind a green gate.

## Cause

The ten ACs specify the sink by a **path string resolved from the current directory**, not by
**the location the writers use**. Today those two happen to agree. INF-500d-4 records, verified
2026-10-09, that `emit_event.py`'s anchor search never finds the deployed
`.leafcutter/config/knowledge_sink.json`, so it falls back to the same bare relative
`debugging/logs/agent_telemetry.jsonl`.

INF-500d-4 (PR #1107, being approved) breaks that coincidence on purpose. It moves every log in
`debugging/logs/` to one absolute root fixed at build time and recorded in the deployed
`config/knowledge_sink.json` under `operational_log_root` and `operational_telemetry_stream`
(INF-500d-4 it_requirements bullet 3; INF-500d-4-iii it_requirements bullet 1). Writers default
to that root (INF-500d-4-iv). Inside a worktree the relative string then names a file no writer
uses. A probe of it proves only that the worktree is writable.

## Fix direction

From INF-500d-4's IT PO (INF-500d-4.yaml it_requirements, bullet 8, "BO-100d RECONCILIATION"):

1. The probe appends to the **declared absolute** `operational_telemetry_stream`, obtained through
   INF-500d-4-iii's side-effect-free location query. INF-500d-4-iii's second `delivers_to`
   contract offers that query to the BO-100d-1a shared pre-drive probe helper, "pending its
   owner's criteria change". The probe must not restate a path.
2. A missing or unreadable declaration makes the probe **fail as blocked**, with "rebuild" as the
   remediation. It must not fall back to the relative path.
3. The operator message names the **absolute** path.

Changing the criteria, it_requirements and contracts of the ten ACs is the build-orchestration
owner's call. Until it is made, decide the landing order. If BO-100d-1a is built first as
written, it must be reworked when INF-500d-4-iv lands. If INF-500d-4-iv lands first, any probe
already in use (the prose probes listed under Where) goes vacuous on the same day.

The workspace-relative `--log debugging/logs/agent_telemetry.jsonl` overrides elsewhere in
`building-epics/SKILL.md` are a separate surface, owned by INF-500d-4-vi, and are not part of
this entry.

## Related

- **INF-500d-4** — the durable-log-root feature. Its doc_links entry for BO-100d-1a flags this as
  a contradiction risk, and its it_requirements bullet 8 carries the fix direction above.
- **INF-500d-4-iii** — the build-time declaration and the location query the probe should use.
- **PR #1107** — IT PO enrichment of INF-500d-4 (+6 L3s), open at filing.
- **INF-500d-4-iv** — the writer change that makes the divergence live.
- **KI-BO-012** — the fast lane emits no telemetry. Separate defect, same stream.

**Pattern:** a reachability gate specified by the path string it probes rather than by the
location the writers resolve. It stays correct only while every writer happens to resolve the same
string the same way. When one of them moves, the gate keeps passing and stops testing anything.
