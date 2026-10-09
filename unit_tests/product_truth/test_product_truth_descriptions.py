"""
MODULE: test_product_truth_descriptions
GOAL: Pin the two description gates and the actor_kind vocabulary from kernel
    decision dec-7b1dcfd47f85cf0a: every step and branch `description` is one
    plain sentence of what happens -- within a length bound and free of code
    tokens, ids, build status and generated contract text -- and `actor_kind`
    is one of deterministic | jev | llm | human.
BUSINESS CONTEXT: The old `human` field grew into engineering narrative that
    went stale. A lint that also rejects plain English would push authors to
    game it, so the negative control (plain sentences that MUST pass) is as
    load-bearing as the positive cases.
ARCHITECTURE: Rule tests call description_problems() directly; the reachability
    tests run the REAL checker CLI over a tempdir store (_bounds_harness), and
    the real-artifact test reads every flow in the repository.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema

from ._bounds_harness import PT_SRC, SCRIPTS_DIR, contract, journey, make_store, put_journeys, run_checker

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import product_truth_descriptions as gate  # noqa: E402
from product_truth_contract_render import apply_contract_presentation  # noqa: E402

PLAIN_ENGLISH = (
    "The customer picks a plant and adds it to the cart.",
    "Jev ranks the options against the criteria and returns a recommendation.",
    "If the payment is declined, the customer sees why and can try another card.",
    "The person approves or rejects the proposal, e.g. by choosing one option.",
    "A reviewer reads the step(s) and marks each one as approved and/or rejected.",
    "The checker compares input/output pairs and reports any read-only mismatch.",
    "Atlas shows each step's status (done, in progress or not started) on the map.",
    "MockData records fill the checkout screen, and the change goes through GitHub review.",
    "The reviewer signs off at 9 a.m. after a 404 page links back to the Flows view.",
    "The customer picks a plan, e.g. Pro or Team, and sees its price.",
    "Jev scores each option, i.e. Fit against every criterion, and compares Pro vs. Team.",
    "the actor acts",
)

CODE_SHAPED = (
    ("Runs `generate` to rebuild the index.", "backtick"),
    ("The generator rewrites index.json for every flow.", "file name or extension"),
    ("The loader reads docs/product-truth and writes it back.", "file path"),
    ("The kernel opens leafcutter/decision-forming for the run.", "file path"),
    ("The checker calls impl_status on each step.", "snake_case identifier"),
    ("The drawer calls parseIoContracts on the step.", "camelCase identifier"),
    ("The kernel classifies the goal in kernel.intent first.", "dotted identifier"),
    ("The checker runs render() on each node.", "function call"),
    ("The step returns a payload like {ok} to the host.", "code punctuation"),
    ("The person runs the publish command with --run-id set.", "command-line flag"),
    ("This step realises UXP-542-1 for the author.", "ticket, AC or ADR id"),
    ("The kernel records the choice as ADR-053 says.", "ticket, AC or ADR id"),
    ("The kernel reuses dec-7b1dcfd47f85 as precedent.", "record id"),
    ("The publish command is not built yet.", "build status"),
    ("The audit is implemented in the hook.", "build status"),
    ("TODO decide who approves the change.", "build status"),
    ("The coder writes a stub for the step.", "build status"),
    ("The kernel stages the record. Then the person publishes it.", "more than one sentence"),
    ("The kernel stages the record\nand the person publishes it", "more than one line"),
    ("Pass the request.\n\nContract fields and examples (generated)\nConsumes:", "generated contract text"),
)


class TestDescriptionLengthBound(unittest.TestCase):
    def test_a_description_at_the_bound_passes_and_one_past_it_fails(self) -> None:
        # covers: UXP-700e-2-ii
        # angle: boundary
        at_bound = "a" * gate.DESCRIPTION_MAX_CHARS
        self.assertEqual(gate.description_problems(at_bound), [])
        problems = gate.description_problems(at_bound + "a")
        self.assertEqual(len(problems), 1, problems)
        self.assertIn(f"over the {gate.DESCRIPTION_MAX_CHARS}-character bound", problems[0])

    def test_an_empty_or_missing_description_fails(self) -> None:
        # covers: UXP-700e-2-ii
        # angle: failure
        for value in ("", "   ", None, 7):
            with self.subTest(value=value):
                self.assertEqual(len(gate.description_problems(value)), 1)


class TestCodeTokenLint(unittest.TestCase):
    def test_plain_english_sentences_pass(self) -> None:
        # covers: UXP-700e-2-ii
        # angle: discrimination
        for sentence in PLAIN_ENGLISH:
            with self.subTest(sentence=sentence):
                self.assertEqual(gate.description_problems(sentence), [])

    def test_each_code_shaped_token_is_rejected_with_its_reason(self) -> None:
        # covers: UXP-700e-2-ii
        # angle: criterion
        for sentence, reason in CODE_SHAPED:
            with self.subTest(sentence=sentence):
                problems = gate.description_problems(sentence)
                self.assertTrue(any(problem.startswith(reason) for problem in problems),
                                f"expected a '{reason}' problem, got {problems}")

    def test_every_description_in_the_repository_passes_both_gates(self) -> None:
        # covers: UXP-700e-2-ii
        # angle: real_artifact
        measured = 0
        for path in sorted((PT_SRC / "flows").rglob("*.flow.json")):
            flow = json.loads(path.read_text(encoding="utf-8"))
            errors: list[str] = []
            measured += gate.check_descriptions({flow["id"]: flow}, errors)
            self.assertEqual(errors, [], path.name)
        self.assertGreater(measured, 0, "the real-artifact test must measure at least one description")


class TestDescriptionGateReachesTheChecker(unittest.TestCase):
    def test_the_checker_fails_on_a_code_shaped_description_and_names_the_step(self) -> None:
        # covers: UXP-700e-2-ii
        # angle: reachability
        with tempfile.TemporaryDirectory() as tmp:
            pt = make_store(Path(tmp))
            clean = journey("p/clean")
            dirty = journey("p/dirty")
            dirty["steps"][0]["description"] = "The checker calls impl_status in validate.py."
            put_journeys(pt, [clean])
            passed = run_checker(pt, "--quiet")
            put_journeys(pt, [clean, dirty])
            failed = run_checker(pt, "--quiet")
        self.assertEqual(passed.returncode, 0, passed.stderr)
        self.assertEqual(contract(passed)["examined_by_check"]["descriptions"], 1)
        self.assertEqual(failed.returncode, 1, failed.stderr)
        self.assertIn("[description] p/dirty step 's1': snake_case identifier", failed.stderr)
        self.assertNotIn("p/clean", "\n".join(line for line in failed.stderr.splitlines() if "[description]" in line))

    def test_the_generator_never_writes_contract_text_into_a_description(self) -> None:
        # covers: UXP-700e-2-ii
        # angle: discrimination
        flow = journey("p/labels")
        flow["contract_definitions"] = {"request": {"schema": "config/request.schema.json"}}
        flow["steps"][0]["io_contracts"] = {
            "consumes": [{"contract": "request", "fields": [{"path": "/question", "types": ["string"], "required": True}]}],
            "produces": [], "examples": [{"contract": "request", "mode": "full", "origin": "illustrative",
                                          "label": "Question", "value": {"question": "Which tests?"}}],
        }
        apply_contract_presentation(flow)
        self.assertEqual(flow["steps"][0]["description"], "the actor acts")
        self.assertEqual(flow["steps"][0]["consumes"], ["request/question: string (required)"])


class TestActorKindVocabulary(unittest.TestCase):
    schema = json.loads((PT_SRC / "schemas" / "flow.schema.json").read_text(encoding="utf-8"))

    def errors(self, flow: dict) -> list[str]:
        validator = jsonschema.Draft7Validator(self.schema)
        return [error.message for error in validator.iter_errors(flow)]

    def test_each_of_the_four_kinds_is_accepted_on_a_step_and_a_branch(self) -> None:
        # covers: UXP-700e-2-ii
        # angle: criterion
        self.assertEqual(set(gate.ACTOR_KINDS), set(
            self.schema["properties"]["steps"]["items"]["properties"]["actor_kind"]["enum"]))
        for kind in gate.ACTOR_KINDS:
            with self.subTest(kind=kind):
                flow = journey("p/kinds")
                flow["steps"][0]["actor_kind"] = kind
                flow["branches"] = [{"id": "b1", "from": "s1", "condition": "if so", "label": "b1",
                                     "description": "the actor branches", "actor_kind": kind}]
                self.assertEqual(self.errors(flow), [])

    def test_an_unknown_or_missing_step_kind_is_rejected(self) -> None:
        # covers: UXP-700e-2-ii
        # angle: failure
        for value in ("robot", "LLM", "", None):
            with self.subTest(value=value):
                flow = journey("p/kinds")
                flow["steps"][0]["actor_kind"] = value
                self.assertTrue(self.errors(flow), f"{value!r} must not validate")
        flow = journey("p/kinds")
        del flow["steps"][0]["actor_kind"]
        self.assertTrue(any("'actor_kind' is a required property" in e for e in self.errors(flow)))

    def test_the_old_human_field_is_rejected(self) -> None:
        # covers: UXP-700e-2-ii
        # angle: discrimination
        flow = journey("p/old")
        flow["steps"][0]["human"] = flow["steps"][0].pop("description")
        messages = self.errors(flow)
        self.assertTrue(any("'description' is a required property" in e for e in messages), messages)
        self.assertTrue(any("'human' was unexpected" in e for e in messages), messages)


if __name__ == "__main__":
    unittest.main()
