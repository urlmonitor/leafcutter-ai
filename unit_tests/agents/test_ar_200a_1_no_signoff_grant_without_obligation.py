"""AR-200a-1 guard: no `signoff` grant for an agent whose sign-off obligation
was removed, unless its body actually uses the skill (KI-AR-003).

Rule: among agents whose frontmatter says `signoff: false` AND whose body has
no "Sign-off (when ticket_path is provided)" section, a `signoff` grant is
valid only if the BODY (never the frontmatter) references the skill file,
i.e. contains `skills/signoff/SKILL.md` (an agent may load it just to read the
status vocabulary). A grant without that reference is reported.

The body-reference rule mirrors registry_validator's existing "declares X but
no reference found in template body" signal, made blocking for signoff
because a stale signoff grant now reaches the compiled prompt (KI-AR-003).
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml

_HELPER = Path(__file__).resolve().parent / "_ar_200b_2_support.py"
_spec = importlib.util.spec_from_file_location("_ar_200b_2_support", _HELPER)
S: Any = sys.modules.get("_ar_200b_2_support") or importlib.util.module_from_spec(_spec)
if "_ar_200b_2_support" not in sys.modules:
    sys.modules["_ar_200b_2_support"] = S
    _spec.loader.exec_module(S)

SECTION = "Sign-off (when ticket_path is provided)"
SKILL_FILE = "skills/signoff/SKILL.md"


def signoff_grant_without_obligation(template_dir: Path) -> tuple[int, list[str]]:
    """(agents examined, names holding a signoff grant with no obligation and
    no body reference to the skill file)."""
    examined, offenders = 0, []
    for path in sorted(template_dir.glob("*.md")):
        fm, body = S.parse_frontmatter(path.read_text(encoding="utf-8"))
        if not fm.get("name"):
            continue
        examined += 1
        no_obligation = fm.get("signoff") is False and SECTION not in body
        uses_skill = SKILL_FILE in body
        if no_obligation and "signoff" in S.abilities_of(fm) and not uses_skill:
            offenders.append(fm["name"])
    return examined, offenders


def _write(tdir: Path, name: str, signoff: bool, with_section: bool,
           body_ref: bool = False, fm_ref: bool = False) -> None:
    fm = {"name": name, "description": "planted", "tools": "Bash",
          "signoff": signoff, "skills": [{"skill_id": "signoff", "mode": "always"}]}
    if fm_ref:
        fm["pre_flight_reads"] = [{"source": f".claude/{SKILL_FILE}"}]
    body = "\nbody\n"
    if with_section:
        body += f"\n## {SECTION}\n\nrecord it\n"
    if body_ref:
        body += f"\nLoad `.claude/{SKILL_FILE}` to read ticket-state.\n"
    (tdir / f"{name}.md").write_text(
        "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n" + body, encoding="utf-8")


class TestNoSignoffGrantWithoutObligation(unittest.TestCase):
    def test_agent_without_signoff_obligation_declares_no_signoff_grant(self):
        # covers: AR-200a-1
        # angle: criterion
        """Whole derived population; fails on zero; names every offender."""
        examined, offenders = signoff_grant_without_obligation(S.REAL_TEMPLATES)
        print(f"examined={examined} offenders={offenders}")
        self.assertGreater(examined, 0, "derived zero agents")
        self.assertEqual(
            offenders, [],
            f"{len(offenders)} of {examined} agents have signoff: false, no "
            f"'{SECTION}' section and no body reference to {SKILL_FILE}, yet "
            f"declare a signoff grant: {offenders}",
        )

    def test_detector_flags_the_planted_violation_and_spares_the_controls(self):
        # covers: AR-200a-1
        # angle: criterion
        """Controls: signoff: true + section may hold the grant; signoff: false
        that kept the section is spared; signoff: false whose BODY references
        the skill file is spared; the path only in FRONTMATTER is reported."""
        with tempfile.TemporaryDirectory() as tmp:
            tdir = Path(tmp)
            _write(tdir, "control", True, True)
            _write(tdir, "violator", False, False)
            _write(tdir, "kept_section", False, True)
            _write(tdir, "reads_skill_in_body", False, False, body_ref=True)
            _write(tdir, "path_only_in_frontmatter", False, False, fm_ref=True)
            examined, offenders = signoff_grant_without_obligation(tdir)
            self.assertEqual(examined, 5)
            self.assertEqual(offenders, ["path_only_in_frontmatter", "violator"])


if __name__ == "__main__":
    unittest.main()
