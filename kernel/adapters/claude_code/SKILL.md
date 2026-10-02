---
name: {{NAME}}
description: Run Leafcutter's decision and research workflow for a supplied goal. Transport only; the kernel owns every decision.
argument-hint: [goal]
disable-model-invocation: true
allowed-tools: Bash({{COMMAND}} run *) Bash({{COMMAND}} resume *) Bash({{COMMAND}} status *) Edit({{CLIENT_RULE}}/**) Read({{RUN_ROOT_RULE}}/**) AskUserQuestion
---
<!-- leafcutter-kernel-skill -->

# Leafcutter kernel (transport only)

You carry messages between the user and the Leafcutter kernel. The kernel decides what happens
next; you never do. Every command below prints exactly ONE JSON document on stdout (logs go to
stderr) and ends with `--json`. `KERNEL` means `{{COMMAND}}`.

## 1. Start

1. With Write, create a scratch JSON file inside `{{CLIENT_DIR}}/` (the only place you may
   write) holding the goal VERBATIM, never paraphrased or shell-quoted:
   `{"goal": "<$ARGUMENTS>", "caller": {"id": "user", "kind": "human"},
   "scope": {"workspace_id": "<project name>", "repository_root": "<absolute project root>"}}`
   Do NOT add `requested_output_schema`: the kernel works out what kind of answer the goal
   needs. Set it only when the user explicitly asks for a decision
   (`leafcutter.decision_report.v1`), an evidence lookup (`leafcutter.evidence_bundle.v1`) or
   ideas (`leafcutter.options.v1`).
2. Run `KERNEL run --input-file <that file> --json`. Never put the goal in the command line.

## 2. Route on the envelope `status` (exit code 0)

- `waiting_host`: do ONLY `pending_interaction.operation`, nothing else.
  - Read only the files in `input_artifact_refs`.
  - Use only `allowed_operations`; never anything in `forbidden_operations`.
  - Follow `goal` and `output_requirements`; produce JSON valid against `output_json_schema`.
  - Write the submission file (section 3) inside `{{CLIENT_DIR}}/` and run `resume`.
- `waiting_human`: ask the USER, with AskUserQuestion, the packet's `question`, showing each
  `choices[].label` and `consequences` and `why_research_cannot_settle`.
  - Offer free text only if `free_text_allowed`.
  - If `structured_allowed`, offer approve or edit: a structured answer approves
    `approved_criterion_ids` / `approved_option_ids` or supplies `edited_criteria`.
  - Never answer for the user, never choose a default. Then write the human submission and `resume`.
- `completed`, `partial`, `blocked`, `failed`, `cancelled`: stop. Present `report_ref` (read the
  file), `limitations`, `open_questions`, `gaps`, `evidence_ids` and `trace_refs.trace_url` if
  present. Do not call a `partial` or `blocked` run complete.
  - If a limitation says `decision record staged: <path>; publish it ... with: <command>`, tell
    the user the record is ready and show that command. Do NOT run it: publishing writes into the
    repository and is the user's to run.
- `running`: run `KERNEL status --run-id <run_id> --json`.

## 3. Resume

Write a submission file inside `{{CLIENT_DIR}}/` and run `KERNEL resume --run-id <run_id> --input-file <file> --json`:

`{"run_id": "<run_id>", "interaction_id": "<pending_interaction.id>",
"expected_state_revision": <pending_interaction.state_revision>, "actor": <actor>,
"relayed_by": "claude_code", "response_schema_id": "<schema>", "response": <response>}`

- Host work: `actor` = `{"kind": "host", "id": "claude_code"}`, `response_schema_id` =
  `pending_interaction.output_schema_id`, `response` = your JSON output.
- Human answer: `actor` = `{"kind": "human", "id": "human:user"}`, `response_schema_id` =
  `leafcutter.human_answer.v1`, `response` = exactly ONE of `{"choice_id": "<id>"}`,
  `{"free_text": "<text>"}` or the structured fields.

## 4. Exit codes

- `0` envelope (any status above). `2` usage error: fix the command.
- `3` rejected, state unchanged: `error.code` and `error.details` say why. Fix the submission and
  resume ONCE more for a host schema or semantic error (the packet is in
  `error.details.pending_interaction`); otherwise show the error to the user.
- `4` unknown run id. `5` internal error: show `error.message` and stop.

## 5. Never

Choose the next capability or step, change policy or permissions, approve anything on the user's
behalf, edit repository files or write anywhere but `{{CLIENT_DIR}}/`, run other Leafcutter
commands (`cancel`, `install-skill` and `decisions publish` are the user's to run, never yours), invent evidence, or continue a run
after `cancelled`. Keep run ids, interaction ids and state revisions exactly as received.
