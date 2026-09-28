---
title: "Your own work survives a build — and the package's capabilities still arrive"
date: "2026-09-23"
time: "13:00"
type: manual
components:
  - build_pipeline
  - worktree_manager
summary: "Protecting an adopter's own .claude/skills had been costing them every capability the package ships: all 41 were written to disk and none resolved by name, with nothing said about it. Separately, an adopter file whose name matched a shipped one was overwritten in silence. Both are fixed by merging at item granularity instead of deciding at the container, and a name collision is now reported with a winner that is checked against the tree the run leaves behind. Covers BP-1500g-2 and BP-1500g-2-i."
description: "THE FIRST DEFECT, AND WHY IT WAS INVISIBLE. BP-1500g-1 stopped the build destroying an adopter's own .claude/skills directory, and it worked -- but it stopped by vetoing the whole container, which meant the discovery shim was never reinstalled. Every one of the 41 shipped skills was still written into .leafcutter/skills/<name>/, so a presence check passed; not one resolved at .claude/skills/<name>/SKILL.md, so the project had no capabilities at all. The adopter's work survived, nothing warned anybody, and the package quietly never arrived. BP-1500g-2 exists precisely to make that outcome a failure rather than a pass -- its own notes name it as the cheapest available repair for BP-1500g-1 and predict someone would reach for it. The run also exited non-zero via BP-1500g-1-ii's blocked path, so it was not even the ordinary successful build the AC's Given clause describes. THE SECOND DEFECT. When the container stayed a symlink and only one name collided, build_skills() wrote straight through the link into the adopter's file with force=True and no ownership check whatsoever. No collision or conflict wording existed anywhere in scripts/build*.py. THE FIX. Both are resolved by merging at ITEM granularity rather than deciding at the container, which is what ADR-041 section 2 required all along: package items are placed individually into the existing directory and adopter items are left untouched. A new module scripts/build_capability_merge.py holds the merge; build_ownership gains detect_capability_collisions, a pure set intersection over the recomputed shipped set and the adopter-owned set -- no new traversal of the tree and no hardcoded list of names, since a test mints a contested name at run time. A collision prints `collision: <name> -- resolves to <adopter|package>`, and one test parses that declaration and then resolves the name in the finished project, so a statement that the tree contradicts fails rather than reassures. The adopter's version is preserved unconditionally -- not overwritten, not emptied, not moved, not removed -- all four asserted separately, because relocating the loser is the well-intentioned implementation a bare exists() check would pass. resolve_removal_verdict's co-claimed carve-out was generalised from strategy == copy to any strategy whenever the verdict is not package_produced; without that, _cleanup_stale_paths independently kept reporting the merged container as an unremovable conflict. A genuinely package_produced co-claimed path is still not carved out, so ADR-041 section 3's removal/claim refusal is untouched. EVIDENCE. Red baseline 10 failed / 2 passed -- the two passes being the ACs' own documented over-trigger controls -- then 18 green, re-verified after a harness split. The wider BP-1500 family sweep is 56 passed. Every test drives a real build.py subprocess: this repo's CLAUDE.md prohibits adding such spawn sites because each costs ~60s, and these ACs justify the exception explicitly, since the single-run coexistence clause cannot be demonstrated any other way and two of the entries mutate the package's own sources before building. A BP-1500g-1-ii FIXTURE WAS RE-TARGETED, NOT RELAXED, and this is the part a reviewer should check. That AC's criteria begin 'Given a build has reached a step it cannot complete without removing, emptying or overwriting content the adopter owns'. Its tests reached that state with a real .claude/skills directory holding only the adopter's own non-colliding item -- which the build genuinely could not resolve until item-level merge existed. It can now, so the fixture stopped satisfying the Given clause and the run correctly exits 0 with everything reachable and the content intact. The criteria are unchanged and no assertion was weakened; the three exit-code tests now use an adopter-owned regular FILE where the container must be a directory, which merging cannot resolve by construction. The content-survival tests passed throughout. KNOWN DESIGN CHOICE, flagged for BP-1500g-3/-4/-5 which consume this contract via BP-1500g-2's delivers_to: the collision report always declares the adopter as the winner. The AC deliberately declines to pick a winner and preservation is unconditional either way, so this is a safe default rather than a settled convention."
commits:
breaking: false
---

## Entry

Protecting the adopter had been costing them the whole package.

BP-1500g-1 correctly stopped the build from destroying an adopter's own
`.claude/skills` directory. It did so by vetoing the **container** — and as a
side effect never reinstalled the discovery shim. All 41 shipped skills were
still written to disk under `.leafcutter/skills/`, so a presence check passed.
None resolved by name, so the project had no capabilities at all.

Adopter's work intact. No warning. Package silently absent. BP-1500g-2 was
written to make exactly that outcome fail — its notes name it as the cheapest
repair for BP-1500g-1 and predict someone would reach for it.

### And a quieter one

With the container still a symlink and a single name colliding,
`build_skills()` wrote through the link into the adopter's file with
`force=True` and no ownership check. No "collision" or "conflict" wording
existed anywhere in the build.

### The fix

Merge at **item** granularity instead of deciding at the container — what
ADR-041 §2 required all along. Package items are placed individually into the
existing directory; adopter items are untouched.

A collision now prints:

```
collision: <name> -- resolves to <adopter|package>
```

and a test parses that line, then resolves the name in the finished project and
requires them to agree. A declaration the tree contradicts fails rather than
reassures. The adopter's version survives unconditionally — not overwritten,
not emptied, not **moved**, not removed, each asserted separately, because
relocating the loser is the well-intentioned implementation a bare `exists()`
would wave through.

### One thing for a reviewer

`BP-1500g-1-ii`'s fixture was **re-targeted, not relaxed**. Its criteria open
*"Given a build has reached a step it cannot complete without removing,
emptying or overwriting content the adopter owns."* Its tests reached that with
a real `.claude/skills` directory holding only the adopter's own non-colliding
item — unresolvable until item-level merge existed. It is resolvable now, so
that fixture stopped satisfying the Given clause.

The criteria are unchanged and no assertion was weakened. The three exit-code
tests now use an adopter-owned regular **file** where the container must be a
directory, which merging cannot resolve by construction. The content-survival
tests passed throughout.

Covers `BP-1500g-2` and `BP-1500g-2-i`. 18 green; BP-1500 family sweep 56 green.
