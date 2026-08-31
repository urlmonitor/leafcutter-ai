---
title: A craft should not be asked to run a check the run made impossible
date: "2026-08-31"
time: "11:50"
type: manual
components: 
  - build_orchestration
summary: "Criteria for a dispatch preflight that compares what an agent's instructions require against what the run actually grants it, and refuses to accept a sign-off reporting a check that could not have run."
description: "A live fast-lane run's coder reported, unprompted, that its tool grant excluded the Skill tool, so the doc-enforcer and complexity-reduction skills its own template mandates could not be invoked. Worse than a missing tool: that template's sign-off block asks the agent to report those skills' results, so an agent that cannot run them is still asked to fill in a line describing their outcome. Five records under BO-1900a (dispatch preflight) make the mismatch detectable before spawn and make a sign-off unable to state an outcome for a capability the craft had no means to invoke."
---

## Entry

A live `/fast-lane-build` run reached its coder phase today. The python-coder returned this in its own sign-off, unprompted:

> This dispatch's tool grant was Bash/Read/Edit/Write/StructuredOutput only — no Skill or
> Agent tool was available, so doc-enforcer, complexity-reduction, and research-agent
> delegation could not be invoked as prescribed. [...] This substitutes for, but does not
> replace, the mandated skill invocations; flagging for supervisor awareness.

That agent behaved well. The system did not.

`templates/agents/python-coder.md` **mandates** both skills — "Invoke the `doc-enforcer` skill via the `Skill` tool on every Python file you [touch]", and the same for `complexity-reduction`. It also states both "must exist in `.claude/skills/`".

**The sharper problem is one line further down.** That template's sign-off block asks the agent to report:

```
- doc-enforcer: <pass / N violations fixed>
- complexity-reduction: <pass / N functions refactored>
```

So an agent with no means of running them is nonetheless asked to fill in a line describing their outcome. Today's agent refused and said why. A less careful one writes `pass`, and the sign-off carries a result no tool produced — a phantom-done vector sitting in the template itself.

It is not only the coder. `pr-reviewer` depends on the `pr-review-toolkit:review-pr` skill and is the lane's review phase. And `fast-lane-ship.js` specifies no tool grant on any dispatch at all — grep for `tools`, `allowedTools` and `Skill` returns nothing — so whatever the grant is, it is not being chosen deliberately. No lane agent template declares `skills_invoked`, so there is currently no machine-readable statement of what a phase agent needs.

### Where these went, and why not where I first suggested

Under **`BO-1900a`** — "a fit-to-dispatch check runs before any agent is spawned", whose own notes read *"nothing is spawned against a target that has not been proven fit."* A dispatch whose grant omits the agent's mandated capabilities is not fit.

`BO-2400g` was the obvious-looking home and is the wrong one, for two reasons. It is fast-lane-only, but the mandating templates are shared with the heavy pipeline, so scoping the fix there leaves every other dispatch unchecked. And it is review-scoped, while the observed victim is the coder, which is not a reading.

### The five

- **`BO-1900a-5`** — a phase agent is not dispatched into a run that withholds the capabilities its instructions require. Its third clause is load-bearing: a dispatch that *does* grant them proceeds, **and once the agent returns the run can show each capability was actually invoked**. Without that, the criterion is satisfiable by a text comparison that never establishes anything ran.
- **`-5-i`** — a required capability that nothing declares is *unconfirmed*, not satisfied. Fail-closed, so "nothing declared" stays distinguishable from "requirements met".
- **`-5-ii`** — a run that proceeds without a required capability names it. A clean run carries no such entry, so presence and absence mean different things.
- **`-5-iii`** — a sign-off carries no outcome for a capability the craft could not invoke, and one that states an outcome anyway is refused.
- **`-5-iv`** — every dispatched craft is checked, not only the one that writes code, which forces the unverified `pr-reviewer` question to an answer.

### Two authoring notes worth keeping

`-5-iii` is worded "no craft **produces** a result line for a check that never ran" rather than the natural "no result is written". That is deliberate: `derive_declares_side_effect` is negation-blind (`KI-BP-20260831-0940`), so "is written" inside a negated clause derives a durable side effect the record does not have. The reason is recorded in the record so nobody reverts the wording. All five were pre-tested against the derivation before commit — all derive `False` with the field absent, which is correct.

`BO-1900a` is now **5 of 5** L2s. No `child_limit_override` was added. Any further L2 needs a tree split or promotion to L1 — and `BO-1900` has three free L1 slots, which is where a first-class "a dispatched craft is equipped" capability contract would go. That promotion is recorded as an open option rather than foreclosed by this placement.

All five are `readiness: draft`. The template defect itself — a sign-off block asking for results of skills the agent cannot invoke — is a prompt change these criteria make *detectable*; whether the template should stop asking is a separate decision, not specified here.
