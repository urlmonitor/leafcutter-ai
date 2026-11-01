"""MODULE: test_tq200d5_reach_docs

GOAL: Prove, through the real command line, that a live test-runner row reaches a fake claude with a short
    command line (TQ-200d-5), and hold the README section 'How a live run starts the agent' and the new
    how-to to the code: the flags the builder uses, the agents the config has, the options the parser accepts.

Target: scripts/evals/run_agent_eval.py (CLI), scripts/evals/README.md, docs/how-to/run-a-live-agent-eval.md
AC: TQ-200d-5
"""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys

import unit_tests.evals.tq200d5._docs as docs
import unit_tests.evals.tq200d5._fake as fk

GOLD = fk.EVALS / "sets" / "test-runner" / "recorded" / "configured-database" / "transcript.jsonl"
SECTION = "How a live run starts the agent"


def test_live_test_runner_row_reaches_fake_claude_with_a_short_command_line(tmp_path):
    # covers: TQ-200d-5
    # angle: reachability
    cli, calls, private = fk.make_real_cli_dir(tmp_path / "cli"), tmp_path / "calls", tmp_path / "ostemp"
    calls.mkdir()
    private.mkdir()
    env = {k: v for k, v in os.environ.items() if k not in ("LEAFCUTTER_EVAL_CLAUDE_CLI", "LEAFCUTTER_EVAL_USE_API", "ANTHROPIC_API_KEY")}
    env.update(PATH=str(cli) + os.pathsep + env.get("PATH", ""), FAKE_CLAUDE_DIR=str(calls), PYTHONUTF8="1",
               FAKE_CLAUDE_OUTCOME=json.dumps({"stdout_file": str(GOLD)}), TMP=str(private), TEMP=str(private), TMPDIR=str(private))
    results = tmp_path / "results.json"
    done = subprocess.run([sys.executable, str(fk.EVALS / "run_agent_eval.py"), "--agent", "test-runner", "--row", "configured-database",
                           "--results-file", str(results)], cwd=fk.REPO, env=env, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=600, check=False)
    assert done.returncode in (0, 1), done.stdout[-1500:] + done.stderr[-1500:]
    [row] = json.loads(results.read_text(encoding="utf-8"))["rows"]
    assert row["id"] == "configured-database" and not row.get("error") and row["score"]["assertions"], row
    logged = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(calls.glob("call-*.json"))]
    assert len(logged) == 1, "the row started the agent exactly once"
    [call] = logged
    template = fk.module("run_agent_eval").load_system_prompt(fk.REPO / "templates" / "agents" / "test-runner.md")
    cmdline = subprocess.list2cmdline(["claude", *call["argv"]])
    assert len(cmdline) < fk.LIMIT and template[:200] not in cmdline and template[200:400] not in cmdline
    assert call["prompt_flag"] == fk.APPEND_FLAG
    prompt = base64.b64decode(call["prompt_b64"]).decode("utf-8")
    assert prompt.startswith(template[:200]) and "{{config.output_root}}" not in prompt, "the file holds the rendered template"
    row_input = json.loads(next(line for line in (fk.EVALS / "sets" / "test-runner.jsonl").read_text(encoding="utf-8").splitlines()
                                if '"configured-database"' in line))["input"]
    assert base64.b64decode(call["stdin_b64"]).decode("utf-8") == row_input and row_input not in cmdline


def test_readme_names_the_route_the_builder_uses():
    # covers: TQ-200d-5
    # angle: real_artifact
    readme = docs.text_of(docs.README)
    body = docs.section(readme, SECTION)
    how_to = docs.text_of(docs.HOW_TO)
    builder = fk.module("agent_launch.command")
    for token in (builder.REPLACE_FLAG, builder.APPEND_FLAG, builder.INPUT_ROUTE):
        assert token in body, f"the section does not name {token!r}, which the builder uses"
    assert builder.REPLACE_FLAG != builder.APPEND_FLAG and builder.REPLACE_FLAG.startswith("--")
    assert "32,767" in body and re.search(r"\b\d+\.\d+\.\d+\b", body), "why (the limit) and the CLI version the route was confirmed on"
    assert re.search(r"temp", body, re.I) and re.search(r"remov|delet", body, re.I), "where the prompt file lives and that it is removed"
    links = re.findall(r"\]\(([^)#]*run-a-live-agent-eval\.md)\)", body)
    assert links, "the section links the how-to"
    assert all((docs.README.parent / target).resolve().is_file() for target in links), f"a link does not resolve: {links}"
    for name, text in (("README", readme), ("how-to", how_to)):
        assert docs.command_line_claims(text) == [], f"{name} says instructions or input go on the command line"
    # the detector is not blind and not trigger-happy
    for bad in ("The instructions go on the command line.", "The row input is passed as a command-line argument (-p <input>).",
                "The template is appended with --append-system-prompt <template>."):
        assert docs.claims_command_line_delivery(bad), bad
    for good in ("The instructions travel in a prompt file, never on the command line.",
                 "The row input goes on stdin, so no row can exceed the 32,767-character Windows command line.",
                 "The command line holds the model and the tool list."):
        assert not docs.claims_command_line_delivery(good), good


def test_how_to_commands_name_configured_agents_and_real_flags():
    # covers: TQ-200d-5
    # angle: real_artifact
    text = docs.text_of(docs.HOW_TO)
    meta = docs.frontmatter(text)
    assert meta.get("type") == "how-to" and meta.get("title") and meta.get("description") and meta.get("related_docs")
    assert "testing_quality" in meta.get("components", [])
    agents = docs.eval_agents()
    named = docs.agent_names(text)
    assert named and named <= set(agents), f"agents the how-to names that the config lacks: {sorted(named - set(agents))}"
    produced = {"test-writer", "sql-test-writer", "test-designer", "test-runner"}
    assert produced <= docs.agent_names("\n".join(docs.run_lines(text))), "a live command for each produced-tests agent"
    assert {agents[a].get("scoring_mode", "label") for a in named} >= {"label", "artifact", "produced_tests"}, "one label, one artifact, the produced-tests agents"
    parser_flags = {s for a in fk.module("run_agent_eval").build_parser()._actions for s in a.option_strings}
    shown = docs.flags_shown(text)
    assert {"--agent", "--score-gold"} <= shown and shown <= parser_flags, f"flags the parser does not accept: {sorted(shown - parser_flags)}"
    for needle in ("LOCAL RUN", "scripts/evals/results", "stdin", "Reading a launch failure", "Finding claude on Windows",
                   "A run that stops as a harness failure"):
        assert needle in text, f"the how-to does not contain {needle!r}"
    # the extractors see what is there
    sample = "```\npython scripts/evals/run_agent_eval.py --agent nope --bogus-flag --row x\n```"
    assert docs.agent_names(sample) == {"nope"} and docs.flags_shown(sample) == {"--agent", "--bogus-flag", "--row"}
