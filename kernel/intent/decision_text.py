"""
MODULE: kernel.intent.decision_text
GOAL: The readable "Decision" section of report.md for a decision_report output: the choice, who
    approved it and when, the rationale, the precedent used and the key evidence.
BUSINESS CONTEXT: report.md of a resolved decision showed only the raw JSON output block (round 8
    defect c); a person reading the report to see what was decided, by whom and on what had to dig
    through criterion assessments. The section answers those questions first, in words, without
    model-written text: every line is a template over recorded facts.
ARCHITECTURE: Pure template functions over the report payload, the run's decision records and the
    evidence map (no IO, no scheduler imports). `ReportContext` carries the two lookups the
    payload alone lacks (approver and time live on the Decision, evidence text on the evidence).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from kernel.contracts.decision import Decision
from kernel.contracts.enums import DecisionStatus
from kernel.contracts.evidence import Evidence

MAX_EVIDENCE = 5
EXCERPT_CHARS = 160


@dataclass(frozen=True)
class ReportContext:
    """What a report needs besides its payload: the run's decisions and evidence by id."""

    decisions: list[Decision] = field(default_factory=list)
    evidence: Mapping[str, Evidence] = field(default_factory=dict)


def _decision_for(payload: Mapping[str, Any], context: ReportContext) -> Decision | None:
    """Return the resolved Decision record the report is about (None when there is none)."""
    chosen = payload.get("selected_option_id")
    return next((d for d in context.decisions if d.status is DecisionStatus.RESOLVED
                 and d.selected_option_id == chosen), None)


def _when(decision: Decision) -> str:
    """Return the approval time as a short UTC text."""
    return decision.approved_at.strftime("%Y-%m-%d %H:%M UTC") if decision.approved_at else ""


def _precedent_lines(decision: Decision | None, context: ReportContext) -> list[str]:
    """Return one line per precedent the decision used (record path, approver, date)."""
    lines = []
    for precedent_id in decision.precedent_ids if decision else []:
        item = next((e for e in context.evidence.values()
                     if e.source.locator.endswith(f"{precedent_id}.yaml")), None)
        label = item.source.title if item and item.source.title else f"Precedent {precedent_id}"
        where = f" ({item.source.locator})" if item else ""
        lines.append(f"- {label}{where}")
    return lines or ["- None."]


def _key_evidence(payload: Mapping[str, Any], context: ReportContext) -> list[str]:
    """Return the most relevant supporting evidence as `locator: excerpt` bullets."""
    items = [context.evidence[i] for i in payload.get("supporting_evidence_ids", [])
             if i in context.evidence]
    items.sort(key=lambda e: -(e.provenance.relevance or 0.0))
    lines = []
    for item in items[:MAX_EVIDENCE]:
        text = " ".join((item.excerpt or "").split())
        cut = f"{text[:EXCERPT_CHARS]}..." if len(text) > EXCERPT_CHARS else text
        lines.append(f"- {item.source.locator}: {cut}")
    return lines or ["- No evidence is cited."]


def decision_lines(payload: Mapping[str, Any], context: ReportContext) -> list[str]:
    """Return the "Decision" section for a decision_report payload."""
    decision = _decision_for(payload, context)
    status = str(payload.get("status", ""))
    lines = ["## Decision", ""]
    if payload.get("selected_option_id"):
        lines.append(f"- Choice: {payload.get('recommendation') or ''} "
                     f"(`{payload['selected_option_id']}`)")
    else:
        lines.append(f"- No option was chosen (status: {status}).")
    approver = decision.approved_by if decision and decision.approved_by else None
    approval = str(payload.get("approval_status", ""))
    lines.append(f"- Approval: {approval}" + (f" by {approver}" if approver else "")
                 + (f" on {_when(decision)}" if decision and decision.approved_at else ""))
    rationale = payload.get("rationale") or {}
    if rationale.get("text"):
        lines.append(f"- Rationale: {rationale['text']}")
    lines += ["", "Precedent used:", "", *_precedent_lines(decision, context), "",
              "Key evidence:", "", *_key_evidence(payload, context), ""]
    open_questions = [str(q) for q in payload.get("open_questions") or []]
    if open_questions:
        lines += ["Open questions:", "", *[f"- {q}" for q in open_questions], ""]
    return lines


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: A decision report gets a readable section (choice, approver and
#   time, rationale, precedent used, key evidence) ahead of the raw JSON block; every line is a
#   template over recorded facts, never model text. (#KernelDecisionStore)
# ====================================================================
