# scripts/portability

Checks that guard properties a real consumer install must have — behaviour
that only shows up once the package leaves this repository's own
self-hosted workspace.

## Purpose

Provides `check_shipped_addresses.py`, the behavioural proof for
INF-1100d-4 / INF-1100d-4-i: nothing a build copies into an install
(`templates/`, including `templates/docs/`, and `config/`) carries a
real-looking database connection address
(`postgresql://`, `postgres://` or `mysql://` with a concrete host and
port). It is not a deployed hook — it guards this repository's own shipped
sources before merge, the same shape as `scripts/ci/check_declaring_files.py`.

## Key Files

| File | Role |
|------|------|
| `check_shipped_addresses.py` | Main module: `iter_shipped_files()`, `iter_build_output_files()`, `scan_file()`, `run_scan()`, `main()` CLI |
| `__init__.py` | Package init (empty) |

## CLI Usage

```bash
# No flags — scan the declared shipped roots relative to cwd
python scripts/portability/check_shipped_addresses.py

# Scan only PATH/templates and PATH/config (a repo-root-shaped temp tree)
python scripts/portability/check_shipped_addresses.py --source-root PATH

# Scan an already-built output directory in full
python scripts/portability/check_shipped_addresses.py --build-root PATH
```

Exit 0 on a clean run over at least one shipped file; exit 1 when any
address is found (printed one per line as `<path>:<line>: ...`) or the
scan visited zero files.

## Critical Context

- The declared shipped roots (`templates/`, `config/`) are named in exactly
  one place, `SHIPPED_SUBDIRS`, shared by the no-flags default and
  `--source-root`. There is no exclusion list of any kind — a file is
  never visited only because it falls outside these two directory names,
  never via a path-based skip inside them (see INF-1100d-4-i's S7/S8
  cases).
- Detection requires a scheme (`postgresql`/`postgres`/`mysql`), a
  concrete (non-placeholder) host, and a digits-only port; credentials and
  the database suffix are optional. This is what makes a bare
  `host:port` with no credentials an address, while angle-bracket
  placeholders, `${ENV}` references and `{{config.*}}` placeholders fail
  to match by construction.
- Never spawns `build.py` (CLAUDE.md) and is not itself deployed to
  consumer installs, so it carries no `scripts/build_phases.py` deploy-map
  entry.
- Wired into `.github/workflows/ci.yml` (`shipped-address-check` job,
  full-tree, blocking) and exercised as a real subprocess by
  `unit_tests/portability/test_inf_1100d_4.py` /
  `test_inf_1100d_4_i.py`, both of which import the shared harness in
  `unit_tests/portability/_inf_1100d_4_shipped_address_harness.py`.

## Maintenance

- To add a supported scheme, extend `_SCHEMES` — no other change is
  required, since both the CI job and the tests invoke the CLI, not the
  regex, directly.
- Tests live in `unit_tests/portability/test_inf_1100d_4.py` and
  `unit_tests/portability/test_inf_1100d_4_i.py`.
