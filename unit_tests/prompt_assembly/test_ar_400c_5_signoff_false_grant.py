"""AR-400c-5 -- a specialist that declares ``signoff: false`` but is granted the
``signoff`` ability stops the build (TDD red phase: the check does not exist yet).

Doors. Both are exercised on a COPIED minimal package slice (real config + real agent
templates, built by ``make_clean_package``; ``probe-planner`` is planted into it):

* validator door: ``registry_validator.validate_agent_registry`` in-process (returned
  error list) plus the real CLI ``python <pkg>/scripts/registry_validator.py`` (exit code
  and printed ``ERROR:`` line, never ``[WARNING]``).
* build door: ``build._validate_all(config, pkg, False, False)`` -- the exact function
  ``build.py main()`` calls to decide whether to abort (returns 1 == abort). build.py's
  only call into the registry is ``validate_agent_registry`` through this function, so
  driving it is the build's decision point without paying ~60s for a real
  ``build.py --target-dir`` spawn per scenario (repo rule: no extra build.py spawns; this
  slice is not a package-mutating deploy test, so no ``shared_layout_mutator`` marker is
  needed -- nothing here runs build.py).

Fixtures: template frontmatter bytes come from ``yaml.safe_dump``; registry records are
deep copies of a real record (``product-owner``) written with ``json.dumps``.
"""

from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent
_SUP = _HERE.parent / "agents" / "_ar_200b_2_support.py"
_spec = importlib.util.spec_from_file_location("_ar_200b_2_support", _SUP)
assert _spec is not None and _spec.loader is not None, f"cannot load {_SUP}"
S = importlib.util.module_from_spec(_spec)
sys.modules["_ar_200b_2_support"] = S
_spec.loader.exec_module(S)

_ABSENT = object()
_NAME = "probe-planner"


def _is_finding(err: str, agent: str = _NAME) -> bool:
    """An error of THIS kind: names the agent, the grant and the declaration."""
    return agent in err and "signoff: false" in err and "signoff" in err.replace("signoff: false", "")


def _findings(errors: list[str], agent: str = _NAME) -> list[str]:
    return [e for e in errors if _is_finding(e, agent)]


def _read_registry(root: Path) -> dict:
    return json.loads((root / "config" / "agent_registry.json").read_text(encoding="utf-8"))


def _write_registry(root: Path, data: dict) -> None:
    (root / "config" / "agent_registry.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def _plant(root: Path, name: str = _NAME, *, signoff=_ABSENT, grants=("signoff",),
           tier: str = "utility", template_extra: dict | None = None,
           registry_grants=None) -> None:
    """Plant (or replace) one specialist: template via yaml.safe_dump, registry record
    cloned from the real ``product-owner`` record. ``registry_grants`` overrides the
    registry copy's ``skills_invoked`` independently of the template's own declaration."""
    fm: dict = {"name": name, "description": f"{name} planted specialist",
                "tools": "Bash, Read, Skill", "model": "sonnet", "produces": "analysis"}
    fm["skills"] = [{"skill_id": g, "mode": "always"} for g in grants]
    if signoff is not _ABSENT:
        fm["signoff"] = signoff
    fm.update(template_extra or {})
    path = root / "templates" / "agents" / f"{name}.md"
    path.write_text("---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\nbody\n", encoding="utf-8")
    data = _read_registry(root)
    template = next(a for a in data["agents"] if a["id"] == "product-owner")
    rec = copy.deepcopy(template)
    rec.update({"id": name, "name": name, "tier": tier, "template_path": f"templates/agents/{name}.md"})
    shown = list(grants) if registry_grants is None else list(registry_grants)
    rec["skills_invoked"] = [{"skill_id": g, "mode": "always"} for g in shown]
    data["agents"] = [a for a in data["agents"] if a["id"] != name] + [rec]
    _write_registry(root, data)


def _set_tier(root: Path, name: str, tier: str) -> None:
    data = _read_registry(root)
    for rec in data["agents"]:
        if rec["id"] == name:
            rec["tier"] = tier
    _write_registry(root, data)


def _clean_pkg(base: str) -> Path:
    """A copied slice with product-owner's real violation repaired in the COPY only (so
    the slice models the post-AR-400c-2 tree) and no probe-planner yet."""
    root = S.make_clean_package(Path(base) / "pkg")
    tpl = root / "templates" / "agents" / "product-owner.md"
    tpl.write_text(tpl.read_text(encoding="utf-8").replace("signoff: false", "signoff: true"),
                   encoding="utf-8")
    return root


def _validator_door(root: Path) -> list[str]:
    errors, _out = S.run_validate(root)
    return errors


def _build_door(root: Path) -> tuple[int, str]:
    sys.path.insert(0, str(S.REPO_ROOT))
    import build

    buf = io.StringIO()
    with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        config = build.load_config(None, Path(tmp))
        rc = build._validate_all(config, root, False, False)
    return rc, buf.getvalue()


def _no_finding_anywhere(tc: unittest.TestCase, root: Path, agent: str = _NAME) -> None:
    errors = _validator_door(root)
    tc.assertEqual(_findings(errors, agent), [], errors)
    rc, out = _build_door(root)
    tc.assertEqual(rc, 0, out)
    tc.assertEqual([ln for ln in out.splitlines() if _is_finding(ln, agent)], [])
    cli = S.run_registry_cli(root)
    tc.assertEqual(cli.returncode, 0, cli.stdout + cli.stderr)


class TestSignoffFalseGrant(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = _clean_pkg(self._tmp.name)

    def test_signoff_grant_on_signoff_false_specialist_fails_both_doors(self):
        # covers: AR-400c-5
        # angle: criterion
        """Probe-planner (`signoff: false`, grants signoff) fails the validator (in-process
        returned error + CLI exit 1, printed as ERROR not [WARNING]) and the build gate
        (returns 1). The registry copy deliberately shows NO signoff grant, so a rule that
        reads the registry instead of the frontmatter finds nothing and goes red. Control:
        the same slice before planting is clean."""
        _no_finding_anywhere(self, self.root)  # control: clean slice has no finding, exits 0
        _plant(self.root, signoff=False, grants=("signoff",), registry_grants=())
        errors = _validator_door(self.root)
        hits = _findings(errors)
        self.assertEqual(len(hits), 1, f"expected exactly one finding naming {_NAME}: {errors}")
        self.assertFalse(hits[0].startswith("[WARNING]"), hits[0])
        cli = S.run_registry_cli(self.root)
        self.assertEqual(cli.returncode, 1, cli.stdout + cli.stderr)
        printed = [ln for ln in cli.stdout.splitlines() if _is_finding(ln)]
        self.assertEqual(len(printed), 1, cli.stdout)
        self.assertTrue(printed[0].startswith("ERROR:"), printed[0])
        self.assertNotIn("[WARNING]", printed[0])
        rc, out = _build_door(self.root)
        self.assertEqual(rc, 1, f"build gate did not abort: {out}")
        self.assertTrue([ln for ln in out.splitlines() if _is_finding(ln)], out)
        self.assertFalse([ln for ln in out.splitlines() if _is_finding(ln) and "[WARNING]" in ln], out)

    def test_removing_grant_or_flipping_flag_clears_the_finding(self):
        # covers: AR-400c-5
        # angle: discrimination
        """Wrong versions caught: a rule that fires on every `signoff: false` specialist, or
        on every signoff grant, regardless of the pairing. Each negative control is paired
        with a positive assertion that the SAME agent produces the finding in the paired
        state, so none can pass because the check is absent."""
        _plant(self.root, signoff=False, grants=("signoff",))
        self.assertEqual(len(_findings(_validator_door(self.root))), 1, "positive case must fail")
        self.assertEqual(_build_door(self.root)[0], 1, "positive case must abort the build")
        # (a) drop only the signoff grant (keep another ability and `signoff: false`)
        _plant(self.root, signoff=False, grants=("knowledge-query",))
        _no_finding_anywhere(self, self.root)
        # restore the pairing: the finding is back
        _plant(self.root, signoff=False, grants=("signoff",))
        self.assertEqual(len(_findings(_validator_door(self.root))), 1, "restored pairing must fail")
        # (b) flip only the declaration to `signoff: true`
        _plant(self.root, signoff=True, grants=("signoff",))
        _no_finding_anywhere(self, self.root)

    def test_absent_flag_and_other_grants_are_not_findings(self):
        # covers: AR-400c-5
        # angle: boundary
        """Wrong version caught: firing on 'signoff is not True' instead of 'signoff is
        False'. Two near-misses (explicit false granting only knowledge-query; no
        `signoff:` key granting signoff, the real sql-* population) beside the one true
        positive: exactly ONE finding in total, naming only probe-planner."""
        _plant(self.root, "probe-other", signoff=False, grants=("knowledge-query",))
        _plant(self.root, "probe-silent", signoff=_ABSENT, grants=("signoff",))
        _plant(self.root, "probe-yes", signoff=True, grants=("signoff",))
        for agent in ("probe-other", "probe-silent", "probe-yes"):
            self.assertEqual(_findings(_validator_door(self.root), agent), [], agent)
        _no_finding_anywhere(self, self.root, "probe-silent")
        _plant(self.root, _NAME, signoff=False, grants=("signoff",))  # positive control
        errors = _validator_door(self.root)
        self.assertEqual(len(_findings(errors)), 1, errors)
        self.assertEqual([e for e in errors if re.search(r"probe-(other|silent|yes)", e)
                          and "signoff: false" in e], [], errors)

    def test_supervisor_tier_is_exempt_and_other_tiers_are_not(self):
        # covers: AR-400c-5
        # angle: discrimination
        """One planted probe-planner, only its registry tier changes. Wrong versions
        caught: an exemption keyed on agent names (probe-planner is neither
        epic-supervisor nor ticket-supervisor, yet tier supervisor must exempt it), and a
        tier read from somewhere other than the registry entry (a template-declared
        `tier: supervisor` must NOT exempt a utility-tier registry entry)."""
        _plant(self.root, signoff=False, grants=("signoff",), tier="supervisor")
        _no_finding_anywhere(self, self.root)
        _set_tier(self.root, _NAME, "utility")
        self.assertEqual(len(_findings(_validator_door(self.root))), 1, "utility tier must fail")
        self.assertEqual(_build_door(self.root)[0], 1)
        _plant(self.root, signoff=False, grants=("signoff",), tier="utility",
               template_extra={"tier": "supervisor"})
        self.assertEqual(len(_findings(_validator_door(self.root))), 1,
                         "a tier declared in the template must not exempt")


def test_real_tree_has_no_signoff_false_signoff_grant():
    # covers: AR-400c-5
    # angle: real_artifact
    """The validator over the checked-out package returns zero findings of this kind, and
    every explicit-`signoff: false` + signoff-grant template (derived at run time from the
    real templates) has registry tier 'supervisor'. Expected red until AR-400c-2 removes
    product-owner's grant."""
    from agent_ability_verdict import normalize_entries
    from template_compiler import parse_frontmatter

    root = S.REPO_ROOT
    registry = {a["template_path"]: a for a in _read_registry(root)["agents"] if a.get("template_path")}
    population, examined = [], 0
    for path in sorted((root / "templates" / "agents").glob("*.md")):
        fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        if not fm.get("name"):
            continue
        examined += 1
        granted = {e["skill_id"] for e in normalize_entries(fm.get("skills"))}
        if fm.get("signoff") is False and "signoff" in granted:
            rec = registry.get(f"templates/agents/{path.name}")
            population.append((fm["name"], rec.get("tier") if rec else None))
    assert examined > 0, "derived zero agents"
    assert population, "derived an empty explicit-false + grant population (epic-supervisor expected)"
    non_supervisor = [p for p in population if p[1] != "supervisor"]
    assert not non_supervisor, f"explicit `signoff: false` + signoff grant on non-supervisor tier: {non_supervisor}"
    errors, _out = S.run_validate(root)
    assert [e for e in errors if "signoff: false" in e and "signoff" in e] == [], errors


if __name__ == "__main__":
    unittest.main()
