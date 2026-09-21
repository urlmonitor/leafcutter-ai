# BA — GE-129a decomposition (session-hook liveness), 2026-09-14/15

Authored `GE-129a-1..-5` plus `GE-129a-3-i` and `GE-129a-4-i` in
`guardrail-engine/GE-129-proven-wherever-it-runs/`. Subject: has a guard wired to the
editor's own tool calls ever been seen to refuse. Reusable findings below; the placement
facts are in `feedback_po_ba_ge129_second_registration_surface.md` and are not repeated.

## The settings.json entry is an OBJECT, not a command string — correct the framing

`GE-129.yaml` and `GE-129a.yaml` both describe entries as "COMMAND STRINGS inside matcher
groups" with "no field on a command string to hang a declaration from". Read in-worktree
2026-09-14, `templates/settings.json` is:

```
hooks: { <Event>: [ { matcher: "<regex>", hooks: [ {type, command, timeout}, ... ] } ] }
```

So an entry **is** a JSON object with fields. The load-bearing half of the PO's claim holds
— there is **no identifier** on an entry — but "nowhere to put a value" does not. That
changes the open question from "there is no room" to "the room there is belongs to the
editor's own settings parser", which is a question about that parser's tolerance of unknown
keys, not about the file's shape. Do not repeat the original framing.

## Resolving the declaration-binding question: fix the property, leave the location

The right BA move was to settle the **property** the binding must have and leave the file
choice to the IT PO. `GE-129a-2` fixes: the tie is derived from particulars read off the
surface at run time (event + matcher + resolved script); repointing an entry makes the run
report the declaration as tied to nothing AND the entry as undeclared, crediting neither;
one declaration never answers for two entries. Every candidate home (in-entry, side-car,
next to the guard) satisfies that, so the IT PO can still choose.

Identity candidates and why only one survives — reusable whenever a surface has no ids:
script path (merges two wirings of one script — and it is exactly BP-1600a-1's identity,
so choosing it collapses the two records), array index (drifts on an unrelated insert),
event+matcher+resolved script (stable, distinguishing, wholly derived). Chosen.

## The seam against BP-1600a-1 is sharper than the PO's table suggests

BP-1600a-1's criteria **already read settings.json** — "take from each configured entry the
hook script that entry's command executes". It is not a disk-only record. The real seam is
what each one keeps: BP-1600a-1 reduces the surface to a **set of scripts** (event and
matcher discarded, which is correct for "does anything run this?"), GE-129a keeps the
**entry**. The discriminating case, now written into `GE-129a-1`'s criteria: the same guard
wired at two events is **one** wired script to BP-1600a-1 and **two** subjects to GE-129a,
and both are right. That one sentence is what keeps the two from being read as duplicates.
Still no `depends_on` — nothing is consumed in either direction.

## Non-obvious finding worth carrying: this "one surface" is several

Guards wired **before** a tool call can stop it; guards wired **after** one cannot. So a
declaration can be faultless and useless simultaneously — well-formed, in the right
vocabulary, naming a rejection the place it is wired can never produce. ADR-045 never had
to ask this because every hooks_manifest gate reaches the same commit-time verdict.
`GE-129a-3` makes the run say which of the two it is.

## Clauses deliberately NOT restated (check before authoring anything else here)

| Clause | Owner |
|---|---|
| alter-and-revert with the declaration held byte-identical | `GE-120f-1` |
| "the run states the entry point it used; only the real one counts" | `GE-120f-1-i` |
| stated count of checks examined; **zero examined ⇒ unresolved** | `GE-120f-3` |
| declaration as a condition of registration | `GE-120f-4` |
| which copy the verifying process loaded (general rule) | `GE-126c-5` |
| the four-value vocabulary itself | `GE-126b-5` / `verification_flow.schema.json` |

**Live consequence for the IT PO**: GE-120f-3's zero-examined-⇒-unresolved clause is written
once. If the session surface is served by a *second population reader behind the same
runner* it is already covered; if a *second runner* is chosen, that clause must be
**extended** to it and must not be re-authored under GE-129a. Recorded in `GE-129a-1`'s
doc_links so the mechanism decision cannot silently drop it.

## Anti-vacuity pairing over the REAL surface has a schedule consequence

`GE-129a-4` requires another guard on the **same real surface** to be reported as having
demonstrated its refusal in the same run as the worked example. A fixture cannot stand in.
That forces at least one real session guard to be declared and genuinely examined in the
landing change — affordable (this surface wires guards that really do deny), and it is the
only pairing that makes the report distinguish the inert guard from a live one beside it.

## Naming a real script in a criterion, made non-expiring

House rule is fixtures. Overridden in `GE-129a-4` because the parent fixes the acceptance
shape as a property of the real repo. Expiry handled by asserting **"the state reported is
the state its own examination produced"** rather than "this guard is inert" — still true the
day the guard is repaired, and it kills an implementation that hard-codes a verdict by name.

## Mechanical notes

- `derive_declares_side_effect` was run over all seven new records before finishing: all
  `False`, so omitting the field is correct. Worth doing for any AC whose Then mentions a
  report or a record — the matcher is phrase-based and "<durable noun> is written" is easy
  to write by accident.
- The L3s' parents (`GE-129a-3`, `GE-129a-4`) need their own `covered_by`, not just the L1's.
  Easy to miss when the L1 update is the one the brief names.
- `docs/reference/claude-code-hooks.md` is **334 lines** against the 300-line doc-length
  ratchet, so the reference-doc AC (`GE-129a-5`) cannot simply append there. Flagged in that
  record's doc_links so the documentation author meets the constraint at the start rather
  than at the end.
