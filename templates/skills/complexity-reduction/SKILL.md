---
name: complexity-reduction
description: |
  Measured techniques for bringing a Python function or a SQL file back under the
  commit-guardian complexity limits without changing behaviour or losing logging.
  States exactly what check_complexity.py (Python, scored per function) and
  check_sql_complexity.py (SQL, scored per file) count, how to measure a score, and
  which refactorings lower it, each with its measured saving.
  Use when: a commit is refused by check-sql-complexity or check-complexity; a
  refusal tells you to use the complexity-reduction skill; a coder agent finds a
  function over the project's threshold; or you are deliberately simplifying a
  complex function or procedure.
allowed-tools:
  - Read
  - Edit
  - Bash
---

# complexity-reduction

Use this skill to get a Python function or a SQL file back under the project's
complexity limit without changing what the code does. It covers what the two checkers
count, how to measure, and which refactorings lower the score. Every before/after
example below is labelled with the score the real checker gives it.

Not covered here: the folder-density check (too many files in one directory). For
that, use the `/code-refactoring-specialist` workflow.

## The limits: read them, don't assume them

The limits are project settings, not constants of this skill. Both live in
`{{config.output_root}}/scripts/commit_guardian/commit_guardian.json`:

| Gate (hook id) | What is scored | Setting | Shipped default |
|---|---|---|---|
| `check-complexity` | each Python function or method | `complexity.max_score` | 15 |
| `check-sql-complexity` | each `.sql` file as a whole | `sql_complexity.max_score` | 75 |

A score above the limit fails; a score equal to it passes. Paths under any directory
listed in the section's `excluded_dirs` are skipped (shipped: `alembic`, `legacy`).

`check-sql-complexity` and `check-complexity` are both registered in the default hook
manifest and both refuse commits. `check-complexity` applies a ratchet: a new or
crossing function is refused above `complexity.max_score`, and a function already over
it is refused only when its score rises above its previous committed score. Coder
agents hold Python functions to `complexity.max_score`.

Print the limits that apply in this project:

```bash
python -c "import sys; sys.path.insert(0, '{{config.output_root}}/scripts/commit_guardian'); import config; print('python', config.MAX_COMPLEXITY_SCORE, '| sql', config.MAX_SQL_COMPLEXITY_SCORE)"
```

## Workflow

1. **Measure**: get the current score with the commands below.
2. **Find the cost**: use the "what counts" tables to find the constructs that carry it.
3. **Reduce**: apply a technique from the catalogue.
4. **Re-measure**: confirm the score is one the check accepts: at or under the limit
   for a new or crossing function, and at or under its previous committed score for
   one already over the limit.
5. **Verify**: run the tests and confirm that no logging, `RAISE NOTICE` or error
   handling was removed to get there.

## Measure

Python, every function in a file, highest score first:

```bash
python -c "import sys; sys.path.insert(0, '{{config.output_root}}/scripts/commit_guardian'); from pathlib import Path; from check_complexity import calculate_complexities; [print(s, n) for n, s in sorted(calculate_complexities(Path('path/to/file.py').read_text(encoding='utf-8')), key=lambda r: -r[1])]"
```

SQL, one file:

```bash
python -c "import sys; sys.path.insert(0, '{{config.output_root}}/scripts/commit_guardian'); from pathlib import Path; from check_sql_complexity import calculate_sql_complexity; print(calculate_sql_complexity(Path('path/to/file.sql').read_text(encoding='utf-8')))"
```

To see the gate's own verdict, stage the file and run the hook. It reads staged files
only: `pre-commit run check-sql-complexity` (or `pre-commit run check-complexity`).

---

## Part 1: Python

### What the checker counts

Each `def` / `async def` starts at 1 and gains:

| Construct | Adds |
|---|---|
| `if` / `elif` | +1 each (an `elif` is a nested `if`) |
| `for`, `async for`, `while` | +1 each |
| `except` clause | +1 each |
| `with` / `async with` statement | +1 per statement, however many context managers it opens |
| `and` / `or` chain | operands − 1 (`a and b and c` = +2) |
| `match` | +1 per `case` |
| comprehension or generator | +1 per `for` clause |

Not counted: `else`, `try`, `finally`, `return`, assignments, logging calls, `assert`,
conditional expressions (`x if c else y`), and `if` filters inside a comprehension.

**Traps**

- **A nested `def` saves nothing.** A closure is scored on its own, and its body
  still counts toward the enclosing function. Extract helpers to module level (or to
  a method).
- **Guard clauses do not lower the score.** Three nested `if`s and three early-return
  `if`s both score 4. Flatten for readability, not for the number.
- **Don't game the counter.** A rewrite that only hides a branch from the checker
  (a conditional expression chain, `all([...])` over conditions that must
  short-circuit) is not a reduction. The goal is a function a reader can hold in
  their head.

### Techniques

#### 1. Extract module-level helpers (the main lever)

Each extracted helper is scored on its own, so the caller keeps only the decision it
makes itself.

```python
# measured: sync_orders=7
def sync_orders(orders, store):
    if not orders:
        return 0
    valid = []
    for order in orders:
        if order.total > 0 and order.customer_id:
            valid.append(order)
    written = 0
    for order in valid:
        try:
            store.save(order)
            written += 1
        except ConnectionError:
            log.warning("save failed: %s", order.id)
    return written
```

```python
# measured: sync_orders=2, _valid_orders=2, _is_valid=2, _save_all=3
def sync_orders(orders, store):
    if not orders:
        return 0
    return _save_all(_valid_orders(orders), store)


def _valid_orders(orders):
    return [order for order in orders if _is_valid(order)]


def _is_valid(order):
    return order.total > 0 and bool(order.customer_id)


def _save_all(orders, store):
    written = 0
    for order in orders:
        try:
            store.save(order)
            written += 1
        except ConnectionError:
            log.warning("save failed: %s", order.id)
    return written
```

The same extraction done as a closure does not help:

```python
# measured: report=5, fmt=3
def report(rows):
    def fmt(row):
        if row.missing:
            return "-"
        if row.value < 0:
            return f"({abs(row.value)})"
        return str(row.value)

    if not rows:
        return ""
    return "\n".join(fmt(r) for r in rows)
```

Move `fmt` to module level and `report` drops from 5 to 3.

#### 2. Replace an `if`/`elif` chain with a lookup table (saves one per branch)

```python
# measured: pick_handler=4
def pick_handler(action):
    if action == "create":
        return create
    elif action == "update":
        return update
    elif action == "delete":
        return delete
    return reject
```

```python
# measured: pick_handler=1
HANDLERS = {"create": create, "update": update, "delete": delete}


def pick_handler(action):
    return HANDLERS.get(action, reject)
```

#### 3. Merge `except` clauses that handle errors the same way (saves one per clause merged)

```python
# measured: parse_port=3
def parse_port(raw):
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_PORT
    except TypeError:
        return DEFAULT_PORT
```

```python
# measured: parse_port=2
def parse_port(raw):
    try:
        return int(raw)
    except (ValueError, TypeError):
        return DEFAULT_PORT
```

#### 4. Open several context managers in one `with` (saves one per statement merged)

```python
# measured: copy_file=3
def copy_file(src, dst):
    with open(src, "rb") as fin:
        with open(dst, "wb") as fout:
            fout.write(fin.read())
```

```python
# measured: copy_file=2
def copy_file(src, dst):
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        fout.write(fin.read())
```

#### 5. Give a long condition a name (moves the cost)

This does not lower the total. It moves the cost into a predicate with a name worth
reading. Use it when the caller is over the limit and the condition means something.
Keep `and`/`or` in the helper so evaluation still short-circuits.

```python
# measured: maybe_ship=5
def maybe_ship(order):
    if order.paid and order.packed and not order.on_hold and order.address:
        ship(order)
```

```python
# measured: maybe_ship=2, _ready_to_ship=4
def maybe_ship(order):
    if _ready_to_ship(order):
        ship(order)


def _ready_to_ship(order):
    return order.paid and order.packed and not order.on_hold and bool(order.address)
```

#### 6. Write a filtering loop as a comprehension (saves one)

A comprehension's `if` filter is not counted. Use this where the comprehension is the
clearer form anyway.

```python
# measured: active_ids=3
def active_ids(users):
    ids = []
    for user in users:
        if user.active:
            ids.append(user.id)
    return ids
```

```python
# measured: active_ids=2
def active_ids(users):
    return [user.id for user in users if user.active]
```

---

## Part 2: SQL

### What the checker counts

The checker removes `/* ... */` and `-- ...` comments, then counts every whole-word,
case-insensitive occurrence of:

```
IF  ELSIF  CASE  WHEN  AND  OR  COALESCE  NULLIF  LEAST  GREATEST
LOOP  WHILE  FOR  EXCEPTION  WITH
```

The file's score is that count + 1. It is one score for the whole file, not per
function. A PL/Python body (`LANGUAGE plpython3u`) is scored with the Python rules
instead, and the file gets whichever score is higher.

**Traps: keywords that count where you might not expect them**

| Text | Counts as |
|---|---|
| `END IF` | `IF` again, so an `IF ... END IF` block costs 2 |
| `END LOOP`, `END CASE` | `LOOP` / `CASE` again |
| `CREATE OR REPLACE` | `OR`, once per object defined in the file |
| `DROP ... IF EXISTS`, `CREATE ... IF NOT EXISTS` | `IF` |
| `BETWEEN x AND y` | `AND` |
| `FOR UPDATE`, `FOR EACH ROW` | `FOR` |
| `WITH TIME ZONE`, `WITH (fillfactor = ...)` | `WITH` |
| `EXCEPTION WHEN others THEN` | `EXCEPTION` + `WHEN` |
| words inside string literals, e.g. a notice text containing "for" or "and" | the keyword |

### Sacred rule: never remove observability

`RAISE NOTICE` statements are often the only production observability a procedure
has. Never remove one, comment it out, or turn it into a comment to get under the
limit. The checker does read notice *text*, so a message that uses words such as
"for", "and", "with", "if" or "when" scores. Reword the message and keep the notice:

```sql
-- measured: 3
RAISE NOTICE 'loaded % rows for % with retries', v_rows, v_key;
```

```sql
-- measured: 1
RAISE NOTICE 'rows loaded: %, key: %, retried: yes', v_rows, v_key;
```

### Techniques

#### 1. Don't repeat a `CASE` in `GROUP BY` (saves the whole repeat)

PostgreSQL accepts the output column's alias (or position) in `GROUP BY`.

```sql
-- measured: 7
SELECT
    CASE WHEN amount < 10 THEN 'small' WHEN amount < 100 THEN 'medium' ELSE 'large' END AS size,
    count(*)
FROM orders
GROUP BY CASE WHEN amount < 10 THEN 'small' WHEN amount < 100 THEN 'medium' ELSE 'large' END;
```

```sql
-- measured: 4
SELECT
    CASE WHEN amount < 10 THEN 'small' WHEN amount < 100 THEN 'medium' ELSE 'large' END AS size,
    count(*)
FROM orders
GROUP BY size;
```

#### 2. Replace a value-mapping `CASE` with a lookup (saves one per `WHEN`)

```sql
-- measured: 5
SELECT id,
       CASE status WHEN 'new' THEN 0 WHEN 'open' THEN 1 WHEN 'closed' THEN 2 ELSE 3 END AS sort_rank
FROM tickets;
```

```sql
-- measured: 2
SELECT t.id, COALESCE(r.sort_rank, 3) AS sort_rank
FROM tickets AS t
LEFT JOIN (VALUES ('new', 0), ('open', 1), ('closed', 2)) AS r(status, sort_rank)
       ON r.status = t.status;
```

For a mapping used in more than one place, a small reference table is better still.

#### 3. Use `COALESCE` for a default instead of `IF ... IS NULL` (saves one)

```sql
-- measured: 3
IF v_since IS NULL THEN
    v_since := '2000-01-01'::timestamptz;
END IF;
```

```sql
-- measured: 2
v_since := COALESCE(v_since, '2000-01-01'::timestamptz);
```

#### 4. Use `IN` (or `= ANY(...)`) instead of an `OR` chain (saves one per `OR`)

```sql
-- measured: 3
SELECT * FROM events WHERE kind = 'click' OR kind = 'view' OR kind = 'share';
```

```sql
-- measured: 1
SELECT * FROM events WHERE kind IN ('click', 'view', 'share');
```

#### 5. Flatten nested `LEAST` / `GREATEST` (saves one per nested call)

```sql
-- measured: 3
SELECT LEAST(a, LEAST(b, c)) FROM t;
```

```sql
-- measured: 2
SELECT LEAST(a, b, c) FROM t;
```

#### 6. Name steps with CTEs freely: one `WITH` per clause

Only the `WITH` keyword counts, so a chain of comma-separated CTEs costs 1 however
many steps it has. Splitting a dense query into named CTEs is nearly free. Inlining
CTEs to save points is rarely worth it.

```sql
-- measured: 2
WITH paid AS (SELECT * FROM orders WHERE is_paid),
     recent AS (SELECT * FROM paid WHERE created_at > now() - interval '7 days'),
     totals AS (SELECT customer_id, sum(amount) AS total FROM recent GROUP BY customer_id)
SELECT * FROM totals;
```

#### 7. Move reusable logic into its own file (saves whatever moves)

Each `.sql` file is scored on its own. A classification `CASE`, a validation block or
a helper function that several procedures share can move to its own file, as a SQL
function the procedure calls. This also removes one `CREATE OR REPLACE` from the
crowded file for every object you move out.

---

## Checklist before committing

- [ ] Measured with the commands above, against the limit printed from config
- [ ] Found the constructs that carry the score (tables above)
- [ ] Applied one or two techniques; re-measured at or under the limit
- [ ] No logging, `RAISE NOTICE` or error handling removed
- [ ] Behaviour unchanged: tests pass
