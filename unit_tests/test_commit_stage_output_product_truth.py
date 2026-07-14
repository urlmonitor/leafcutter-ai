"""Behavioral tests for commitStageOutputProductTruth() in the E2 plan-feature.js.

Track 1.2 introduced a product-truth sibling of commitStageOutput() with two
non-negotiable invariants this file exercises against the REAL runtime function
(extracted + driven in isolation via the E2 runner, no string-scan):

  1. NO-MAIN-COMMIT GUARD (fail-closed): when the authoring branch is `main`, the
     function returns status:error and NEVER dispatches the commit agent.
  2. SURGICAL STAGING (both directions): the PT commit instructions stage ONLY the
     reported artifact/derived paths + docs/product-truth/index.json, forbid a
     wholesale `git add docs/product-truth`, and forbid staging
     docs/acceptance-criteria/. Conversely the AC commit (commitStageOutput) never
     reaches into docs/product-truth.

Commit subjects are asserted to be `plan-feature(MOCK-DATA|MOCKUP|FLOW): <component>`.
"""
from __future__ import annotations

import json
import textwrap
import unittest

from _plan_feature_e2_runner import run_isolated_e2


def _drive_pt_commit(
    reported_paths: list[str],
    stage: str,
    component: str,
    branch_output: str,
) -> dict:
    """Run commitStageOutputProductTruth() in isolation and capture result + prompts.

    branch_output is what the 'branch-check' status-checker returns (e.g. 'main'
    or 'ac-authoring/x'). Returns {res, commitPrompts, branchChecks}.
    """
    driver = textwrap.dedent(f"""
        const commitPrompts = [];
        let branchChecks = 0;
        const agent = async (prompt, opts) => {{
            const label = (opts && opts.label) || '';
            if (label === 'branch-check') {{
                branchChecks++;
                return {{ output: {json.dumps(branch_output)}, exit_code: 0 }};
            }}
            if (label === 'commit-stage-output-product-truth') {{
                commitPrompts.push(prompt);
                return {{ status: 'ok', message: 'committed successfully' }};
            }}
            return {{ status: 'ok' }};
        }};
        commitStageOutputProductTruth(
            {json.dumps(reported_paths)},
            {json.dumps(stage)},
            {json.dumps(component)},
            'run-xyz',
            'docs/product-truth',
            '/wt'
        )
            .then(res => {{ process.stdout.write(JSON.stringify({{ res, commitPrompts, branchChecks }})); }})
            .catch(err => {{ process.stderr.write(String(err)); process.exit(1); }});
    """)
    stdout = run_isolated_e2(["commitStageOutputProductTruth", "stageDisplayName"], driver)
    return json.loads(stdout)


def _drive_ac_commit(branch_output: str = "ac-authoring/x") -> dict:
    """Run commitStageOutput() in isolation, capture the AC commit prompt."""
    driver = textwrap.dedent(f"""
        const commitPrompts = [];
        const agent = async (prompt, opts) => {{
            const label = (opts && opts.label) || '';
            if (label === 'branch-check') {{
                return {{ output: {json.dumps(branch_output)}, exit_code: 0 }};
            }}
            if (label === 'commit-stage-output') {{
                commitPrompts.push(prompt);
                return {{ status: 'ok', message: 'committed successfully' }};
            }}
            return {{ status: 'ok' }};
        }};
        commitStageOutput(
            ['ACD-1'], 'ba', 'ux-prototyping', false, 'run-xyz', 'docs/acceptance-criteria', '/wt'
        )
            .then(res => {{ process.stdout.write(JSON.stringify({{ res, commitPrompts }})); }})
            .catch(err => {{ process.stderr.write(String(err)); process.exit(1); }});
    """)
    stdout = run_isolated_e2(["commitStageOutput", "stageDisplayName"], driver)
    return json.loads(stdout)


class TestPtCommitMainRefusal(unittest.TestCase):
    """The no-main-commit guard must fail-closed for PT commits."""

    def test_main_branch_refused_and_no_commit_dispatched(self) -> None:
        out = _drive_pt_commit(
            ["docs/product-truth/mock-data/plant.mock.json"], "mockdata", "ux-prototyping", "main"
        )
        self.assertEqual(out["res"]["status"], "error")
        self.assertIn("refusing to commit product-truth files to main", out["res"]["message"])
        self.assertEqual(
            out["commitPrompts"], [], msg="commit agent must NOT be dispatched on main"
        )

    def test_empty_branch_name_fails_closed(self) -> None:
        out = _drive_pt_commit(
            ["docs/product-truth/mock-data/plant.mock.json"], "mockdata", "ux-prototyping", ""
        )
        self.assertEqual(out["res"]["status"], "error")
        self.assertIn("cannot confirm authoring branch is not main", out["res"]["message"])
        self.assertEqual(out["commitPrompts"], [])


class TestPtCommitSurgicalStaging(unittest.TestCase):
    """PT commits stage only the reported paths + index.json, never wholesale."""

    def test_reported_paths_and_index_are_staged(self) -> None:
        paths = [
            "docs/product-truth/mock-data/plant.mock.json",
            "docs/product-truth/flows/x/y.flow.json",
        ]
        out = _drive_pt_commit(paths, "flow", "ux-prototyping", "ac-authoring/x")
        self.assertEqual(out["res"]["status"], "ok")
        self.assertEqual(len(out["commitPrompts"]), 1)
        prompt = out["commitPrompts"][0]
        for p in paths:
            self.assertIn(p, prompt)
        self.assertIn("docs/product-truth/index.json", prompt)

    def test_wholesale_add_is_forbidden(self) -> None:
        out = _drive_pt_commit(
            ["docs/product-truth/flows/x/y.flow.json"], "flow", "ux-prototyping", "ac-authoring/x"
        )
        prompt = out["commitPrompts"][0]
        # The instructions must forbid a blanket add of the store.
        self.assertIn("NEVER run", prompt)
        self.assertIn("git", prompt)
        self.assertIn("add docs/product-truth", prompt)

    def test_ac_store_excluded_from_pt_commit(self) -> None:
        out = _drive_pt_commit(
            ["docs/product-truth/flows/x/y.flow.json"], "flow", "ux-prototyping", "ac-authoring/x"
        )
        prompt = out["commitPrompts"][0]
        self.assertIn("docs/acceptance-criteria/", prompt)
        self.assertIn("SEPARATE commit surface", prompt)

    def test_subject_uses_pt_display_name(self) -> None:
        for stage, subject in (
            ("mockdata", "plan-feature(MOCK-DATA): ux-prototyping"),
            ("mockup", "plan-feature(MOCKUP): ux-prototyping"),
            ("flow", "plan-feature(FLOW): ux-prototyping"),
        ):
            out = _drive_pt_commit(
                ["docs/product-truth/x.json"], stage, "ux-prototyping", "ac-authoring/x"
            )
            self.assertIn(subject, out["commitPrompts"][0], msg=f"stage={stage}")


class TestAcCommitExcludesProductTruth(unittest.TestCase):
    """The AC commit (other direction) never reaches into docs/product-truth."""

    def test_ac_commit_scopes_to_ac_store_only(self) -> None:
        out = _drive_ac_commit()
        self.assertEqual(len(out["commitPrompts"]), 1)
        prompt = out["commitPrompts"][0]
        self.assertIn("docs/acceptance-criteria", prompt)
        self.assertNotIn("docs/product-truth", prompt)


if __name__ == "__main__":
    unittest.main()
