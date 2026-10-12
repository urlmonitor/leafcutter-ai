---
title: "The unassigned-work-agent guard now returns its narrowed value, so three annotations can tell the truth"
date: "2026-09-23"
time: "16:45"
type: manual
components: 
  - ac_store
  - ticket_creation_pipeline
summary: "_require_work_agent refused a null assigned_agent correctly but told the type checker nothing: a -> None guard narrows nothing, so _build_agents_map had to keep annotating its parameter str while genuinely receiving None on several hundred store records (366 of 4218 measured 2026-09-23) — its own docstring said 'Raises UnassignedWorkAgentError when assigned_agent is None' directly beneath a signature that said the value could not be None. The guard now returns the narrowed value (-> str) and the caller binds work_agent = _require_work_agent(assigned_agent), which lets _build_agents_map widen honestly to str | None while _legacy_agents_map and _collect_needed_agents keep their truthful str. Behaviour is unchanged and byte-proven: same refusal message, same exit 1, byte-identical generated ticket. The -> str is machine-checked at the definition; the _sib() importlib seam still erases it at the call site, and that residual is recorded in the docstring rather than papered over."
description: "THE SHAPE OF THE LIE. A guard landed recently making the ticket generator refuse an AC whose assigned_agent is null; a sweep of the store on 2026-09-23 found 366 of 4218 records carrying an explicit null (the brief said 355 — the store is under concurrent edit, which is why the code says 'several hundred' rather than pinning a number that rots), so None is a real runtime value on this path, not a defensive hypothetical. The guard is correctly placed — _build_agents_map's single entry point, so the LEGACY and COMPUTED paths refuse identically — but it was type-opaque for two compounding reasons. First, _require_work_agent(assigned_agent: str | None) -> None narrows nothing: a checker learns no fact about the argument from a function that returns None. Second, _gtfa_agents_map reaches the guard through the _sib() importlib shim, which has no return annotation, so mypy types the whole sibling module as Any and does not see the call at all. The consequence was three annotations that contradicted the code: _build_agents_map declared assigned_agent: str while receiving None, and its Raises entry documented exactly the None it claimed could not occur. A previous pass tried widening the parameter alone and hit a cascade, so it reported rather than forced the change. CONFIRMED CALL GRAPH (re-derived before editing, not taken from the brief). _require_work_agent is defined at _gtfa_agents_inputs.py:62 and has exactly ONE call site: _gtfa_agents_map.py inside _build_agents_map. _legacy_agents_map is defined and called only within _gtfa_agents_map. _collect_needed_agents is defined in _gtfa_agents_inputs, rebound across the _sib() seam, and called once. _build_agents_map's own callers are _gtfa_cli.py (two sites), _gtfa_body.py (one), a re-export in generate_ticket_from_ac.py, and the test suite. No test calls _require_work_agent directly, so no test observes the changed return. THE CHANGE. _require_work_agent is now -> str and ends with `return assigned_agent`; _build_agents_map binds `work_agent = _require_work_agent(assigned_agent)` and passes work_agent to both _legacy_agents_map and _collect_needed_agents. Its parameter widens to str | None. WHAT WAS DELIBERATELY LEFT AS str, and why: _legacy_agents_map and _collect_needed_agents are reachable only post-guard, so str is the truth for them. Widening THEM would be actively wrong — an earlier pass proved it, with mypy flagging all_needed.add(...) into a set[str], which is precisely the null-phase defect the guard exists to prevent (a literal null phase in the frontmatter and a None row in the Sign-offs checklist). EVIDENCE THAT THE NARROWING IS REAL, AND THE PART THAT IS NOT. mypy at CI's exact invocation (--ignore-missing-imports --explicit-package-bases --no-error-summary) reports 0 errors before and 0 after; the point was never to clear errors but to let the parameter carry str | None without introducing any. The cascade was reproduced first on pristine code: widening the parameter alone yields exactly ONE error — 'Argument 1 to _legacy_agents_map has incompatible type str | None; expected str' — and notably NOT a second one for _collect_needed_agents, because that call crosses the _sib() seam into Any. That asymmetry is itself the seam made visible. Three further probes, all reverted: (1) reveal_type at the definition site reports 'str' after the raise, so the guard genuinely narrows there; (2) neutering the raise turns the return into a hard error, 'Incompatible return value type (got str | None, expected str)', so the -> str is mechanically enforced and cannot rot silently — under the old -> None, deleting the raise would have produced nothing; (3) reveal_type at the CALL site reports Any for both _require_work_agent and work_agent, while the locally-defined _legacy_agents_map reveals as 'def (assigned_agent: str) -> dict[str, str]'. STATED PLAINLY, because a guard that only looks narrowed is worse than one honestly marked opaque: mypy accepts the new caller not because it saw the narrowing but because Any absorbs it. The guarantee is checked at the definition and merely propagated, not re-verified, at the caller. It is not cosmetic either — a future edit that bypasses work_agent and passes the raw str | None parameter to a str-typed local function is now caught, which is the error reproduced above. Closing the residual needs a real (non-importlib) import at the _sib() seam; it was NOT faked with a cast, an assert, or a # type: ignore. The docstring records the limit so the next reader is not misled. BEHAVIOURAL NO-OP, BYTE-COMPARED IN FRESH PROCESSES. generate_ticket_from_ac.py --ac ACD-1100d --dry-run still refuses by name with exit 1 and a byte-identical stdout and stderr; the refusal string is untouched in the diff. --ac BO-2200c-5 --dry-run still exits 0 with byte-identical 5100-byte output. ruff clean on both changed files. File sizes against the 400-line check-file-size cap, measured with the hook's own count_lines (docstrings and comments stripped) rather than raw wc: _gtfa_agents_map.py 237 -> 241, _gtfa_agents_inputs.py 196 -> 197, _gtfa_cli.py unchanged at 318 and untouched. Raw line counts are higher (393 and 435) but are not what the hook measures. NO NEW AC. This introduces no new behaviour — the refusal, its message, its exit code and its placement are unchanged, and only the type plumbing plus one local binding differ. The behaviour is already covered by TKT-600b-5, whose tests exercise _build_agents_map rather than the guard directly and are unaffected by the changed return."
commits: []
breaking: false
---

## Entry

`_require_work_agent` refuses an AC whose `assigned_agent` is null. A sweep of
the store on 2026-09-23 found **366** of 4218 records carrying an explicit null
(the brief said 355; the store is being edited concurrently, which is why the
docstring says "several hundred" rather than pinning a number that rots). Either
way `None` is a real runtime value here, not a defensive hypothetical. The guard
is correctly placed, at `_build_agents_map`'s single entry point, so the legacy
and computed paths refuse identically.

It was invisible to the type checker, for two compounding reasons:

1. `-> None` narrows nothing. A checker learns no fact about an argument from a
   function that returns `None`.
2. `_gtfa_agents_map` reaches the guard through the `_sib()` importlib shim,
   which has no return annotation — so mypy types the sibling module as `Any`
   and does not see the call at all.

So `_build_agents_map(assigned_agent: str)` kept declaring `str` while receiving
`None`, with a `Raises` entry documenting the exact value its signature denied.

### The change

```python
work_agent = _require_work_agent(assigned_agent)   # -> str
```

The parameter widens honestly to `str | None`. `_legacy_agents_map` and
`_collect_needed_agents` **keep** their `str`: they are reachable only
post-guard, and widening them would be wrong — an earlier pass proved it, with
mypy flagging `all_needed.add(...)` into a `set[str]`, which is precisely the
null-phase defect the guard exists to prevent.

### Is the narrowing real?

Partly, and the part that is not is worth stating plainly.

**Real.** `reveal_type` after the raise reports `str`. Neutering the raise
produces a hard error — *Incompatible return value type (got "str | None",
expected "str")* — so the `-> str` is mechanically enforced and cannot rot
silently. Under the old `-> None`, deleting the guard produced nothing.

**Not real at the call site.** `reveal_type(work_agent)` there reports `Any`.
mypy accepts the widened caller not because it saw the narrowing but because
`Any` absorbs it. The seam still wins.

The asymmetry is visible in the reproduced cascade: widening the parameter alone
yields exactly **one** error, on `_legacy_agents_map` (a local definition mypy
can see) — and none for `_collect_needed_agents`, which crosses the seam.

This is not cosmetic: an edit that bypasses `work_agent` and passes the raw
`str | None` onward is now caught. But the guarantee is *checked at the
definition and merely propagated* at the caller. Closing the gap needs a real
import at the `_sib()` seam. It was **not** faked with a `cast`, an `assert`, or
a `# type: ignore`; the docstring records the limit instead.

### Evidence

mypy 0 before, 0 after, at CI's exact invocation. Both dry-runs byte-identical
in fresh processes: `ACD-1100d` still refuses by name with exit 1 and an
untouched message; `BO-2200c-5` still emits the same 5100 bytes. ruff clean.
Measured file sizes (hook's own `count_lines`, not raw `wc`): 237→241 and
196→197 against the 400 cap.

No new AC — no new behaviour; `TKT-600b-5` already covers it.
