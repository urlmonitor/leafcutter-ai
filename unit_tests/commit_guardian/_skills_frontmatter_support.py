"""Shared assertion for the AR-300c-2 grant location: a skill is granted only in the
frontmatter ``skills:`` list of {skill_id, mode, condition}; ``skills_used`` is retired."""

from __future__ import annotations

import unittest

import yaml


def assert_grant_in_frontmatter(case: unittest.TestCase, content: str, filename: str, skill_id: str) -> None:
    parts = content.split("---", 2)
    case.assertGreaterEqual(len(parts), 3, msg=f"No frontmatter found in {filename}")
    fm = yaml.safe_load(parts[1])
    case.assertIsInstance(fm, dict)
    case.assertNotIn("skills_used", fm, msg=f"retired 'skills_used' key still in {filename}")
    skills = fm.get("skills")
    case.assertIsInstance(skills, list, msg=f"'skills' must be a list in {filename} frontmatter")
    entries = [e for e in skills if isinstance(e, dict) and e.get("skill_id") == skill_id]
    case.assertEqual(len(entries), 1, msg=f"'{skill_id}' must be declared exactly once in 'skills' of {filename}")
    case.assertIn("mode", entries[0])
    if entries[0]["mode"] == "conditional":
        case.assertTrue(str(entries[0].get("condition") or "").strip())
