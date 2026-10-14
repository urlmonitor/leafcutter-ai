"""AR-300 review finding 1 -- a MALFORMED declaration is refused by the build gate,
naming the agent and the offending entry; it is never silently dropped.

Today ``agent_ability_verdict.normalize_entries``, ``agent_spawn_declaration.declared_spawn``
and ``verify_spawn_allowlists`` DROP a malformed entry, so an agent whose header says one
thing is compiled as if it said less -- the AR-300c-1 / AR-300c-5 "none omitted" clause
broken without a word. The refusal belongs beside the existing missing-condition refusal in
``agent_ability_gate`` (same entry the build calls: ``refuse_on_ability_findings``).

AC mapping. Skills-side cases cover AR-300c-1 ("abilities named in the compiled prompt are
exactly the abilities that header declares -- none omitted": a dropped entry IS an omission).
Spawn-side cases cover AR-300c-5 (the same sentence for sub-agents). AR-300b-4 ("examined
nothing must not read as clean") is NOT the fitting AC: it speaks of the per-agent
PREPARATION delivery guarantee, not of header parsing, so it is not tagged.

Every package is serialised by the real YAML writer (``write_template``) and read back by the
gate's own frontmatter parser. Every test first builds the WELL-FORMED twin of its package and
requires exit 0 (control: the refusal below is caused by the malformed entry alone), and every
package keeps a valid skilled agent so the skills population is non-empty (an incidental
"empty population" refusal cannot satisfy the test).

RED MAP (all five fail today on the exit-code / naming assertion after the control passes):
  wrong-key skills entry   -> gate returns 0 (entry silently dropped)
  string `skills:`         -> gate refuses, but about single characters; the string is never named
  `conditonal` mode        -> gate returns 0 (an unknown mode flows through as a grant)
  non-string spawn entry   -> gate returns 0 (entry silently dropped)
  string `spawn_allowlist` -> gate refuses, but about single characters; the string is never named
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import agent_fm, planted_package  # noqa: E402
from _ar_300b_support import BODY, SKILLS, grant  # noqa: E402
from _ar_300e_support import run_gate, sfm  # noqa: E402

BAD = "zz-bad"
GOOD = "zz-good"
WORKER = "zz-worker"


def _record(stem: str, fm: dict) -> dict:
    """A registry record that agrees with a WELL-FORMED header and claims nothing for a malformed one."""
    skills = fm.get("skills")
    invoked = [dict(e) for e in skills if isinstance(e, dict) and isinstance(e.get("skill_id"), str)] \
        if isinstance(skills, list) else []
    spawn = [s for s in fm.get("spawn_allowlist") or [] if isinstance(s, str)] \
        if isinstance(fm.get("spawn_allowlist"), list) else []
    return {"id": stem, "template_path": f"templates/agents/{stem}.md", "role": f"{stem} role", "tier": "phase",
            "is_ticket_phase": False, "spawn_allowlist": spawn, "skills_used": [], "skills_invoked": invoked}


def _package(base: Path, bad_fm: dict) -> Path:
    templates = {
        GOOD: (agent_fm(GOOD, grant("zz-alpha")), BODY),
        BAD: (bad_fm, BODY),
        WORKER: (sfm(WORKER, tools="Bash, Read"), BODY),
    }
    records = [_record(stem, fm) for stem, (fm, _b) in templates.items()]
    return planted_package(base, templates, SKILLS, registry_agents=records)


def _lines(text: str, *needles: str) -> list[str]:
    return [ln for ln in text.splitlines() if all(n in ln for n in needles)]


def _refusal(tmp_path: Path, capsys, good_fm: dict, bad_fm: dict, entry_text: str) -> None:
    """Control: the well-formed twin passes (exit 0). Then the malformed package must be refused
    (exit 1) by a line naming BOTH the agent and the offending entry text."""
    rc, out = run_gate(_package(tmp_path / "good", good_fm), capsys)
    assert rc == 0, f"control failed: the well-formed twin was refused: {out[-600:]}"
    rc, out = run_gate(_package(tmp_path / "bad", bad_fm), capsys)
    assert rc == 1, f"a malformed declaration was not refused (silently dropped?): exit {rc}"
    assert _lines(out, BAD, entry_text), f"no line names agent {BAD!r} and the malformed entry {entry_text!r}: {out[-900:]}"


def test_ac300c1_skills_entry_with_wrong_key_is_refused_by_name(tmp_path, capsys):
    # covers: AR-300c-1
    # angle: failure
    """AR-300c-1: ``{skill: zz-beta, mode: always}`` (key ``skill``, not ``skill_id``) is refused,
    naming the agent and the entry. Wrong versions caught: dropping the entry (today), or refusing
    with no mention of which entry."""
    ok = agent_fm(BAD, [{"skill_id": "zz-beta", "mode": "always"}])
    bad = agent_fm(BAD, [{"skill": "zz-beta", "mode": "always"}])
    _refusal(tmp_path, capsys, ok, bad, "zz-beta")


def test_ac300c1_skills_declared_as_a_string_is_refused_as_a_whole(tmp_path, capsys):
    # covers: AR-300c-1
    # angle: failure
    """AR-300c-1: ``skills: zz-beta`` (a string, not a list) is refused naming the whole value.
    Today it is iterated character by character, producing nonsense findings about 'z' and '-'.
    Wrong version caught: any refusal that does not quote the declared value."""
    ok = agent_fm(BAD, [{"skill_id": "zz-beta", "mode": "always"}])
    bad = agent_fm(BAD, "zz-beta")
    _refusal(tmp_path, capsys, ok, bad, "zz-beta")


def test_ac300c1_mode_that_is_neither_always_nor_conditional_is_refused(tmp_path, capsys):
    # covers: AR-300c-1
    # angle: boundary
    """AR-300c-1: ``mode: conditonal`` (typo) is refused naming the agent and the bad mode;
    the control's ``conditional`` + condition passes, so only the spelling differs. Wrong version
    caught: an unknown mode flowing through as a grant (today), or a gate that treats every
    non-``always`` mode as acceptable."""
    ok = agent_fm(BAD, [{"skill_id": "zz-beta", "mode": "conditional", "condition": "when a ticket needs it"}])
    bad = agent_fm(BAD, [{"skill_id": "zz-beta", "mode": "conditonal", "condition": "when a ticket needs it"}])
    _refusal(tmp_path, capsys, ok, bad, "conditonal")


def test_ac300c5_spawn_entry_that_is_not_a_string_is_refused_by_name(tmp_path, capsys):
    # covers: AR-300c-5
    # angle: failure
    """AR-300c-5: ``spawn_allowlist: [{id: zz-worker}]`` is refused naming the agent and the entry.
    Wrong version caught: the entry filtered out (today), leaving the agent with an empty
    permission and the build green."""
    ok = sfm(BAD, spawn=[WORKER])
    bad = sfm(BAD, spawn=[{"id": WORKER}])
    _refusal(tmp_path, capsys, ok, bad, WORKER)


def test_ac300c5_spawn_allowlist_declared_as_a_string_is_refused_as_a_whole(tmp_path, capsys):
    # covers: AR-300c-5
    # angle: failure
    """AR-300c-5: ``spawn_allowlist: zz-worker`` (a string) is refused naming the whole value.
    Today it is iterated per character and refused about sub-agents 'z', '-', ...; the declared
    value is never named. Wrong version caught: a refusal that is right by accident."""
    ok = sfm(BAD, spawn=[WORKER])
    bad = sfm(BAD, spawn=WORKER)
    bad["spawn_allowlist"] = WORKER
    _refusal(tmp_path, capsys, ok, bad, WORKER)
