---
trigger: glob
globs: *.sql
---

# PYTHON DEVELOPMENT STANDARDS

## 1. WORKFLOW: THE "RED-GREEN-REFACTOR" LOOP
Strictly follow this sequence for every new feature or logic change:
1.  **Logic Spec (Markdown):** Read/Create the relevant `docs/logic/*.md` file first.
2.  **Red (Test):** Create a test case in `unit_tests/subfolder` (subfolder = folder where the function lives) that fails.
3.  **Green (Code):** Write the minimal Python code to pass the test.
4.  **Refactor:** Add types, docs, and optimize.

## 2. FILE STRUCTURE & GRANULARITY
- **One Logical Unit Per File:** Adhere strictly to Single Responsibility.
  - If functional: One main entry function per file (plus small private helpers).
  - If OOP: One Class per file.
- **Naming:** Snake_case for filenames (e.g., `process_payment_handler.py`).

### 2.1. THE "COMPLEXITY CAP" (When to Split)
You must refactor a single `.py` file into a dedicated folder (Package) if **ANY** of the following triggers are met:

* **Trigger A (Size):** The file exceeds **200 lines of code**.
* **Trigger B (Helper Bloat):** The main function relies on **more than 3 private helper functions**.
* **Trigger C (Reusability):** A "private" helper function is needed by a *different* file.

**Refactoring Protocol:**
1.  **Create Folder:** Name it after the original file (e.g., `process_payment.py` -> `process_payment/`).
2.  **Entry Point:** Place the main logic in `__init__.py` or `service.py` so imports remain clean (`from process_payment import process`).
3.  **Segregate Helpers:** Move helpers into descriptive files (e.g., `validators.py`, `db_utils.py`).
4.  **Update Docs:** The folder must contain a `README.md` explaining the package structure if it contains more than 3 files.
5.  **Debug helpers:** Find / put debug functions in /debug_functions

## 3. MANDATORY HEADER (Module Docstring)
Every `.py` file MUST start with this docstring block:
"""
MODULE: [Filename]
GOAL: [What does this module achieve?]
BUSINESS CONTEXT: [Link to Markdown spec: e.g., docs/logic/payouts.md]
DEPENDENCIES: [List external services/libs, e.g., Stripe API, AWS S3, local DB]
PERFORMANCE: [e.g., O(n) complexity, or "Memory heavy - process in chunks"]
"""

## 4. IN-CODE DOCUMENTATION
- **Function Docstrings:** Must use Google Style or NumPy Style.
  - *Args:* Type and description.
  - *Returns:* Type and what it represents.
  - *Raises:* Explicitly list all errors this function might throw.
- **The "Why" Comments:**
  - ❌ BAD: `# Calculate total`
  - ✅ GOOD: `# Using Decimal instead of Float to avoid currency rounding errors per Finance Dept rules`

## 5. TYPE HINTING & SAFETY
- **Strict Typing:** All function arguments and return values MUST have type hints (`def func(a: int) -> str:`).
- **No Magic Numbers:** Define constants at the top of the file (e.g., `MAX_RETRY_ATTEMPTS = 3`).
- **No Bare Excepts:** Never use `except:`. Catch specific errors (`except ValueError:`) to prevent silent failures.

## 6. SIDE EFFECTS
If this code modifies external state (DB, API, Filesystem), explicit logging is required:
- `logger.info(f"Modifying User {user_id}...")`

## 7. FOLDER RULES
**Every directory containing Python modules MUST have an `__init__.py` file**

### Rules:
- When creating new subdirectories in Python packages, create `__init__.py` immediately
- Empty `__init__.py` files are acceptable for simple namespacing
- Use `__init__.py` to expose public API: `from .module import function`
