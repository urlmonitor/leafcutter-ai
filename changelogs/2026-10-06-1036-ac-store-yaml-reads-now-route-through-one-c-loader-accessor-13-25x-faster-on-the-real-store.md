---
title: "AC-store YAML reads now route through one C-loader accessor, 13.25x faster on the real store"
date: "2026-10-06"
time: "10:36"
type: feature
components: 
  - ac_store
  - commit_guardian
  - testing_quality
summary: "Every tool that reads the acceptance-criteria store now parses YAML through libyaml's C implementation when it is available, cutting store-wide read time by over 13x with no change to what is accepted as valid."
description: "TQ-600a-11: added scripts/ac_store/yaml_safe_loader.py, a shared get_safe_yaml_loader() accessor that resolves to PyYAML's CSafeLoader via getattr(yaml, \"CSafeLoader\", yaml.SafeLoader) with a guarded fallback to the pure-Python SafeLoader -- never a hard import, so the package stays installable where PyYAML was built without libyaml. Converted all ~73 store-reading call sites across scripts/ac_store/ and templates/scripts/commit_guardian/ from yaml.safe_load(x) to yaml.load(x, Loader=get_safe_yaml_loader()); the one pre-existing exception, scripts/render_effective_prompt.py, already used the fast idiom inline and was left as documented. Measured 13.25x on the real 4,635-file, 23.8MB store (24.68s pure-Python vs 1.86s C-backed). A differential test parses the whole store with both loaders in one process and asserts the parsed objects are equal record-for-record, not merely that both parse without raising. The new module is registered in build_phases_ac_store.py's AC_STORE_DEPLOY_MAP so commit-guardian hooks resolve it from the deployed layout; reachability was confirmed by running the deployed validate_ac_schema.py (OK: all 4756 AC YAML files are valid). Net behavior change: this removes a recursion-depth guard that only pure-Python PyYAML enforced -- CSafeLoader parses deeply-nested structures (e.g. 600 levels of nested brackets) that raise RecursionError under the pure-Python SafeLoader. Checked against the four divergence classes named in the AC (duplicate keys, timestamp scalars, ambiguous numerics, merge keys): all four agree between loaders under the installed PyYAML 6.0.1; only parse depth differs. Accepted as a reasonable tradeoff for a first-party store read exclusively by internal tooling."
breaking: false
---

## Entry

### One shared accessor, 13.25x faster on the real store

Every reader in the AC-store toolchain named `yaml.safe_load` directly. `TQ-600a-11`
replaces that with a single shared accessor, `get_safe_yaml_loader()` in the new
`scripts/ac_store/yaml_safe_loader.py`, and routes roughly 73 call sites across
`scripts/ac_store/` and `templates/scripts/commit_guardian/` through it:
`yaml.safe_load(x)` becomes `yaml.load(x, Loader=get_safe_yaml_loader())`. The one
pre-existing exception, `scripts/render_effective_prompt.py`, already used the fast
idiom inline (`getattr(yaml, "CSafeLoader", yaml.SafeLoader)`) and is the in-repo
precedent this change generalises rather than invents — it is left as the
documented exception rather than converted.

Measured on the real store as it stands on disk — 4,635 YAML records, 23.8 MB —
a full sweep drops from 24.68s with the pure-Python safe parser to 1.86s with the
libyaml-backed one: a 13.25x ratio. The two headline consumers both benefit: the
store-wide schema validation behind the required "AC store valid" pull-request
check, and the ticket-generation dry run.

### The fallback is guarded, never a hard import

`get_safe_yaml_loader()` resolves via `getattr(yaml, "CSafeLoader", yaml.SafeLoader)`.
The C-backed loader is absent whenever the installed PyYAML was built without
libyaml, which is a real configuration for adopters of this package — a bare
`from yaml import CSafeLoader` would make the package uninstallable there, with the
failure surfacing at import time on an unrelated command. The fallback keeps every
environment working; only environments with libyaml get the speed-up.

### Proof is differential, over the real store, not "it parses"

The test asserting correctness parses the whole real store with both loaders in one
process and compares the resulting Python objects for equality record-by-record —
not merely that both loaders parse without raising. Checked against the four
divergence classes PyYAML's two safe loaders can disagree on — duplicate keys,
timestamp scalars, ambiguous numerics, and merge keys — all four agree between the
loaders under the installed PyYAML 6.0.1 for this store's content.

### Net behavior change: a recursion-depth guard is gone

The one real divergence found is depth, not content: `"[" * 600 + "]" * 600` raises
`RecursionError` under the pure-Python `SafeLoader` but parses cleanly under
`CSafeLoader`. This change removes that recursion-depth ceiling. Accepted as a
reasonable tradeoff for a first-party store read exclusively by internal tooling —
nothing in the AC store approaches that nesting depth today.

### Deploy-manifest and reachability

`yaml_safe_loader.py` is registered in `build_phases_ac_store.py`'s
`AC_STORE_DEPLOY_MAP`, because several `templates/scripts/commit_guardian/*.py`
hooks reach it via the existing `_ac_store_locator` sibling-import convention and
run from the **deployed** layout, not the source tree — the same deploy-manifest
rule `done_proof.py` previously tripped (see `CLAUDE.md` "New Hook / Gate
Dependencies Must Be in the Build Deploy-Manifest"). Reachability was confirmed by
running the deployed `validate_ac_schema.py`: `OK: all 4756 AC YAML files are
valid`.
