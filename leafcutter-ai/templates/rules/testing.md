---
trigger: glob
globs: unit_tests/**, **/test_*.py, **/*_test.py
description: Rules for writing and modifying unit tests. Read when adding, changing, or debugging tests.
---

# Testing Rules

## 1. Always Read the README First
Before adding, modifying, or debugging any test:
1. **Read the `README.md`** in the test's parent directory (e.g., `unit_tests/live_trader/README.md`).
2. **Read the `README.md`** of the source module being tested (e.g., `live_trader/logic/README.md`).
3. These READMEs contain **gotchas, mocking patterns, and known key mismatches** that will save you from repeating past mistakes.

## 2. Test Design Principles

### No Database Connections
All unit tests in `unit_tests/live_trader/` run on every commit via pre-commit hooks. They must:
- **Never connect to a database.**
- **Mock all external dependencies** (pybit, sqlalchemy, API keys).
- **Complete in under 5 seconds** total.

### Synthetic vs Real-Data Tests
- **Synthetic tests** (`test_divergence_detector.py`): Use hand-crafted mock data. These are the primary regression tests.
- **Real-data tests** (`test_divergence_detector_real_data.py`): Compare against JSON fixtures generated from the local database. These catch drift between Python logic and DB state.

### Real-Data Fixture Generation
Fixtures are generated using `debugging/scripts/generate_engine_fixture.py`:
```bash
poetry run python debugging/scripts/generate_engine_fixture.py \
    --symbol ETHUSDT \
    --open-time "2026-03-07 22:47:00+00:00" \
    --engine all
```
If a test fails with `FileNotFoundError` for a fixture, **regenerate it** using the script above (requires a local DB connection).

## 3. Common Gotchas

### Mocking `pybit` and `sqlalchemy`
When testing files that import `live_trader.main` (directly or indirectly), you must mock `pybit` and `sqlalchemy` in `sys.modules` **before** the import occurs. Always include:
- `pybit`, `pybit.unified_trading`
- `sqlalchemy`, `sqlalchemy.orm`, `sqlalchemy.orm.query`, `sqlalchemy.dialects`
- `os.environ` for `API_KEY`, `API_SECRET`, `API_KEY_TESTNET`, `API_SECRET_TESTNET`

### Key Name Mismatches Between Code and Database
The Python code and the database sometimes use different key names for the same concept:

| Concept | Python Code Key | Database Key |
|---|---|---|
| Divergence direction | `"type"` | `"extreme"` |

When writing real-data tests that compare Python output to DB fixtures, use safe access: `data.get('type', data.get('extreme'))`.

### Model Attribute Names
The `SupportResistanceLevels` model uses:
- `level.price` (NOT `level.level_price`)
- `level.interval` (NOT `level.level_interval`)

### Stop-Loss Calculation
Stop-loss is always calculated from the **entry price** (candle close), not from the wick's low/high:
```python
# LONG:  stop_loss = entry_price * (1 - stop_loss_pct)
# SHORT: stop_loss = entry_price * (1 + stop_loss_pct)
```

## 4. Running Tests

```bash
# All live trader tests (runs on commit)
poetry run pytest unit_tests/live_trader/ -v

# Stop on first failure (useful for debugging)
poetry run pytest unit_tests/live_trader/ --maxfail=1

# SQL function tests (manual only, connects to DB)
poetry run pytest unit_tests/sql_functions/ -v
```

## 5. When Changing Output Formats
If you rename a dictionary key or change a return format in any logic module:
1. Update **all tests** that assert on that key.
2. Check if there are **real-data tests** that compare against DB fixtures (the fixtures may still use the old key name).
3. Update the **README.md** in both the source and test directories.
4. Consider whether the **database schema** also needs updating (e.g., SQL functions that write the same key).
