---
title: "The fast YAML parser requirement now says where it must not be used, not just where it helps"
date: "2026-10-08"
time: "10:15"
type: manual
components: 
  - testing_quality
summary: "A requirement promised that every tool reading the requirements store would use a faster parser. That turned out to be unsafe in most places, so it was narrowed to the one place it is both safe and worth it, and the requirement now says so rather than promising what was abandoned."
description: "Amends TQ-600a-11 to match what the package actually does after the YAML-loader migration was narrowed from eighty-five call sites to two. Three clauses are retracted explicitly rather than left unmet: the claim that the required store-validation gate would parse ten times faster, the claim that it would finish in a quarter of its baseline, and the claim that no entry point would name the pure-Python parser directly. The last one is reversed, not merely abandoned: about eighty-one files now name the pure-Python parser deliberately, because the faster libyaml-backed parser accepts some malformed input that the pure-Python one rejects, and several guards depended on that rejection to treat a broken file as broken. Error fidelity was chosen over speed at the required gate. The rule is now inverted: the pure-Python parser is the default and needs no justification, and the fast parser is a bounded exception that must pass a four-part test covering parse volume, error-path dependence, equivalence with the reference parser, and whether the result decides a guard's verdict. The measurable claim is repointed at the one whole-store walk in agent card generation, measured at roughly ten to thirteen times faster in two separate sittings, and is expressed as a ratio against a baseline taken in the same sitting. Two further findings are recorded: a third C-parser site that bypassed the shared accessor through an inline idiom, which the amended rule now counts as the same decision, and that one of the two surviving call sites has no production caller, so the live footprint is one site. The struck clauses are preserved verbatim under a do-not-reinstate heading."
---

## Entry
