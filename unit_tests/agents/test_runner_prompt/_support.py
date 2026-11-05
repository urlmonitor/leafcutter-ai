"""
MODULE: unit_tests/agents/test_runner_prompt/_support.py
GOAL: Shared readers and rule checkers for the test-runner prompt tests of TQ-200d-4-ii and
    TQ-200d-4-iii. Not collected by pytest (the name does not start with test_).
BUSINESS CONTEXT: templates/agents/test-runner.md is a prompt. What a model does with it cannot be
    unit-tested, so the checkable claims are pinned here: each rule is a function over template TEXT
    that returns a list of problem codes (empty means the rule holds). Every rule is scoped to its
    own section, with fenced blocks separated from prose, so a word that another section happens to
    contain never satisfies it. The tests feed these functions the real template and then real
    mutations of it.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[3]
TEMPLATE = REPO / "templates" / "agents" / "test-runner.md"
REFERENCE_DOC = REPO / "docs" / "reference" / "skills-config-fields.md"
KEY = "testing_context.test_command"
CONFIGURED_FORM = "<testing_context.test_command> <file>"
FALLBACK_FORM = "python -m pytest <file>"
NEGATION = re.compile(r"\b(not|never|neither|no|cannot)\b", re.IGNORECASE)


def read(path: Path) -> str:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def split_frontmatter(text: str) -> tuple[str, str]:
    assert text.startswith("---\n"), "the template must start with a frontmatter block"
    head, _, body = text[4:].partition("\n---\n")
    return head, body


def frontmatter(text: str) -> dict:
    return yaml.safe_load(split_frontmatter(text)[0])


def _headings(text: str, level: str = "## ") -> list[tuple[int, str]]:
    """(character offset, heading line) of every heading of the level outside fenced blocks."""
    found, offset, in_fence = [], 0, False
    for line in text.splitlines(keepends=True):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence and line.startswith(level):
            found.append((offset, line.rstrip("\n")))
        offset += len(line)
    return found


def section_span(text: str, title: str, *, prefix: bool = False) -> tuple[int, int] | None:
    """(start, end) offsets of the level-2 section titled `title`, heading line included."""
    heads = _headings(text)
    for index, (start, line) in enumerate(heads):
        name = line[3:].strip()
        if name == title or (prefix and name.startswith(title)):
            end = heads[index + 1][0] if index + 1 < len(heads) else len(text)
            return start, end
    return None


def section(text: str, title: str, *, prefix: bool = False) -> str | None:
    span = section_span(text, title, prefix=prefix)
    return None if span is None else text[span[0]:span[1]]


def section_titles(text: str) -> list[str]:
    return [line[3:].strip() for _, line in _headings(text)]


def fences(text: str) -> list[str]:
    return re.findall(r"```[^\n]*\n(.*?)```", text, flags=re.DOTALL)


def prose(text: str) -> str:
    return re.sub(r"```[^\n]*\n.*?```", "\n", text, flags=re.DOTALL)


def sentences(text: str) -> list[str]:
    """Prose sentences; a blank line, a bullet or a heading always ends the sentence before it."""
    found = []
    for block in re.split(r"\n\s*\n|\n(?=\s*[-*] )|\n(?=#)", prose(text)):
        found.extend(s for s in re.split(r"(?<=[.!?])(?<!\.\.\.)\s+", flat(block)) if s)
    return found


def replace_section(text: str, title: str, new_section: str) -> str:
    span = section_span(text, title)
    assert span is not None, f"no section {title!r}"
    return text[:span[0]] + new_section + text[span[1]:]


def rewrite_sentences(text: str, title: str, predicate, replacement: str) -> str:
    """The template with every prose sentence of the section that `predicate` accepts replaced."""
    original = section(text, title)
    assert original is not None, f"no section {title!r}"
    changed = original
    hit = False
    for sentence in sentences(original):
        if predicate(sentence):
            hit = True
            pattern = r"\s+".join(re.escape(word) for word in sentence.split())
            changed, count = re.subn(pattern, lambda _m: replacement, changed, count=1)
            assert count == 1, f"sentence not found verbatim in {title!r}: {sentence!r}"
    assert hit, f"no sentence of {title!r} matched the mutation predicate"
    return replace_section(text, title, changed)


# --------------------------------------------------------------------------------- TQ-200d-4-ii

def key_problems(text: str) -> list[str]:
    config_keys = frontmatter(text).get("config_keys")
    if not isinstance(config_keys, dict) or KEY not in config_keys:
        return ["key-missing"]
    entry = config_keys[KEY]
    if not isinstance(entry, dict) or entry.get("required") is not False:
        return ["key-not-optional"]
    return []


_SCRIPT_RUN = re.compile(
    r"(?:^|[\s`(])(?:PYTHONPATH=\S+\s+)?(?:poetry run\s+)?python3?\s+(?:-[uBEsS]\s+)*(?!-)([^\s`]+?\.py)\b"
)


def plain_script_runs(text: str) -> list[str]:
    """Body lines that run a TEST file as a plain script ('python <path>.py'); scripts that are not
    test files (the db_check checker) are not test runs."""
    offenders = []
    for line in split_frontmatter(text)[1].splitlines():
        for match in _SCRIPT_RUN.finditer(line):
            path = match.group(1).strip("\"'")
            base = path.rsplit("/", 1)[-1]
            is_test_file = (
                base.startswith(("test", "check_")) or "<" in base
                or path.startswith(("unit_tests/", "tests/", "./tests/"))
            )
            if is_test_file:
                offenders.append(line.strip())
    return offenders


def single_file_sentence(text: str) -> str | None:
    table_section = section(text, "Routing Table")
    for paragraph in re.split(r"\n\s*\n", table_section or ""):
        if "single-file" in paragraph and not paragraph.lstrip().startswith("|"):
            return flat(paragraph)
    return None


_UNSET = re.compile(r"\b(absent|empty|unset|not set|not configured|missing)\b", re.IGNORECASE)


def _command_problems(sentence: str, forms: tuple[str, ...]) -> list[str]:
    if KEY not in sentence:
        return ["key-not-named"]
    problems = [f"missing:{form}" for form in forms if form not in sentence]
    if "python -m pytest" in sentence and not _UNSET.search(sentence):
        problems.append("fallback-not-conditional")
    if "python -m pytest" in sentence and sentence.find(KEY) > sentence.find("python -m pytest"):
        problems.append("fallback-before-configured-command")
    return problems


def routing_problems(text: str) -> list[str]:
    sentence = single_file_sentence(text)
    if sentence is None:
        return ["no-single-file-sentence"]
    return _command_problems(sentence, (CONFIGURED_FORM, FALLBACK_FORM))


def single_action_bullet(text: str) -> str | None:
    actions = section(text, "Actions") or ""
    for bullet in re.split(r"\n(?=- )", actions):
        if bullet.startswith("- **`single"):
            return flat(bullet)
    return None


def action_problems(text: str) -> list[str]:
    bullet = single_action_bullet(text)
    if bullet is None:
        return ["no-single-bullet"]
    return _command_problems(bullet, ("<testing_context.test_command>", "python -m pytest"))


def reference_row(doc: str) -> list[str] | None:
    block = section(doc, "Testing Context", prefix=True) or ""
    for line in block.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and cells and cells[0].strip("`") == KEY:
            return cells
    return None


def reference_problems(doc: str) -> list[str]:
    cells = reference_row(doc)
    if cells is None:
        return ["row-missing-from-testing-context-table"]
    if len(cells) != 5:
        return ["row-not-five-columns"]
    problems = []
    if cells[1] != "string":
        problems.append("type-not-string")
    if cells[2].lower() != "no":
        problems.append("not-optional")
    if not re.search(r"test[- ]runner", cells[4], re.IGNORECASE):
        problems.append("test-runner-not-named")
    if "python -m pytest" not in cells[4]:
        problems.append("fallback-not-stated")
    return problems


# -------------------------------------------------------------------------------- TQ-200d-4-iii

_COUNT = re.compile(r"(greater than zero|above zero|more than zero|at least one|> ?0)", re.IGNORECASE)
_PASS_WORD = re.compile(r"\bPASS\b")


def is_pass_rule(sentence: str) -> bool:
    return bool(
        _PASS_WORD.search(sentence) and _COUNT.search(sentence)
        and re.search(r"\bsummary\b", sentence, re.IGNORECASE)
        and re.search(r"\b(only|requires?|unless|never)\b", sentence, re.IGNORECASE)
    )


def is_exit_pass_sentence(sentence: str) -> bool:
    return bool(re.search(r"\bexit", sentence, re.IGNORECASE) and re.search(r"\bpass(es|ed)?\b", sentence, re.IGNORECASE))


def success_problems(text: str) -> list[str]:
    block = section(text, "Output: Success")
    if block is None:
        return ["no-success-section"]
    problems = []
    sents = sentences(block)
    if not any(is_pass_rule(s) for s in sents):
        problems.append("no-pass-needs-a-count-rule")
    exit_sents = [s for s in sents if is_exit_pass_sentence(s)]
    if not exit_sents or not all(NEGATION.search(s) for s in exit_sents):
        problems.append("exit-status-alone-not-excluded")
    lines = [line for body in fences(block) for line in body.splitlines()]
    if not any(re.search(r"summary", line, re.IGNORECASE) for line in lines):
        problems.append("report-block-quotes-no-runner-summary")
    if not any(_is_unittest_count_note(s) for s in sents):
        problems.append("unittest-count-note-missing")
    return problems


def _is_unittest_count_note(sentence: str) -> bool:
    """For unittest, 'Ran N tests ... OK' with N above zero is the passed count."""
    return bool("unittest" in sentence and "Ran N tests" in sentence and "OK" in sentence and _COUNT.search(sentence))


NO_TEST_RAN_REASONS = ("nothing collected", "no passed test", "no runner summary")
NO_PASSED_TEST_TRIGGERS = ("0 passed, 1 skipped", "deselected", "Ran 0 tests")


_NO_TEST_RAN_LINES = (
    # (pattern, code, must the line be present?)
    (r"\s*Status:\s*NO TEST RAN\b", "block-lacks-status-no-test-ran", True),
    (r"\s*Status:\s*PASS\b", "block-says-pass", False),
    (r"\s*Command( run)?:\s*\S", "block-lacks-the-command-run", True),
    (r"\s*Reason:\s*\S", "block-lacks-a-reason", True),
)


def _no_test_ran_block_problems(block: str) -> list[str]:
    lines = [line for body in fences(block) for line in body.splitlines()]
    problems = []
    for pattern, code, required in _NO_TEST_RAN_LINES:
        if any(re.match(pattern, line) for line in lines) != required:
            problems.append(code)
    return problems + _no_test_ran_reason_problems(block, lines)


def _no_test_ran_reason_problems(block: str, lines: list[str]) -> list[str]:
    problems = []
    words = flat(block).lower()
    for phrase, code in zip(NO_TEST_RAN_REASONS, ("reason-nothing-collected-missing",
                                                  "reason-no-passed-test-missing",
                                                  "reason-no-runner-summary-missing")):
        if phrase not in words:
            problems.append(code)
    reason_line = next((line for line in lines if re.match(r"\s*Reason:", line)), "")
    if not all(phrase in reason_line for phrase in NO_TEST_RAN_REASONS):
        problems.append("reason-line-lacks-a-named-reason")
    if not all(trigger in flat(prose(block)) for trigger in NO_PASSED_TEST_TRIGGERS):
        problems.append("no-passed-test-trigger-wording-missing")
    return problems


def no_test_ran_problems(text: str) -> list[str]:
    titles = section_titles(text)
    if "Output: No Test Ran" not in titles:
        return ["no-section"]
    problems = []
    if titles.index("Output: No Test Ran") != titles.index("Output: Success") + 1:
        problems.append("not-placed-after-success")
    return problems + _no_test_ran_block_problems(section(text, "Output: No Test Ran") or "")



def _false_in(sentence: str, name: str) -> bool:
    return bool(re.search(rf"{name}`?\W+(?:is\W+|to\W+|=\W+|set to\W+)?`?false\b", sentence, re.IGNORECASE))


def machine_problems(text: str) -> list[str]:
    block = section(text, "Machine-Parsed Dispatch Output Contract")
    if block is None:
        return ["no-machine-parsed-section"]
    rule = [s for s in sentences(block) if re.search(r"no test ran", s, re.IGNORECASE)]
    if not rule:
        return ["no-no-test-ran-rule"]
    problems = []
    says_true = any(re.search(r"passed`?\W+(is\W+)?`?true", s) for s in rule)
    if not any(_false_in(s, "passed") for s in rule) or says_true:
        problems.append("passed-not-false-when-no-test-ran")
    if not any("anomalies" in s for s in rule):
        problems.append("reason-not-in-anomalies")
    if not all(key in block for key in ('"passed"', '"output"', '"failing_tests"', '"anomalies"')):
        problems.append("reply-keys-changed")
    if not any(_outcome_is_error(s) for s in rule):
        problems.append("outcome-not-error-when-no-test-ran")
    return problems


def _outcome_is_error(sentence: str) -> bool:
    return bool(re.search(r'outcome`?\W+(?:is\W+|to\W+|=\W+|set to\W+)?`?"error"', sentence, re.IGNORECASE))


def combined_problems(text: str) -> list[str]:
    block = section(text, "Combined Output (action: all)")
    if block is None:
        return ["no-combined-section"]
    rows = [r for r in block.splitlines() if re.match(r"\|\s*(live-trader|sql-functions)\s*\|", r)]
    if len(rows) != 2:
        return ["suite-rows-not-two"]
    return [] if all("NO TEST RAN" in r for r in rows) else ["status-vocabulary-lacks-no-test-ran"]


def manifest_problems(text: str) -> list[str]:
    block = section(text, "Completion Manifest")
    if block is None:
        return ["no-manifest-section"]
    for s in sentences(block):
        if re.search(r"no test ran", s, re.IGNORECASE) and _false_in(s, "test_suite_executed"):
            return [] if all(r in s for r in NO_TEST_RAN_REASONS) else ["manifest-reasons-not-mirrored"]
    return ["manifest-lacks-test-suite-executed-false-for-no-test-ran"]


def swap(text: str, title: str, old: str, new: str) -> str:
    """The template with `old` (whitespace-tolerant, every occurrence) replaced by `new` inside one section."""
    original = section(text, title)
    assert original is not None, f"no section {title!r}"
    pattern = r"\s+".join(re.escape(word) for word in old.split())
    changed, count = re.subn(pattern, lambda _m: new, original)
    assert count, f"{old!r} not found in section {title!r}"
    return replace_section(text, title, changed)
