"""
MODULE: commit_guardian.check_file_size_rule_parity
GOAL: Reconcile every PUBLISHED description of the file-size rule -- which
    kinds of file it covers, when it applies, and how long a file of each
    kind may be -- against the REAL, enforced rule, refusing a commit that
    leaves either side saying something the other does not.
BUSINESS CONTEXT: GE-127d-1's own record found the file-size rule stated in
    two independent places -- README.md's `check-file-size` row and
    commit_guardian.json's `file_size._comment` -- that had drifted from the
    behaviour check_file_size.py actually enforces (README.md still claimed
    a new-files-only exemption GE-127b-1 deliberately removed on 2026-05-01).
    A documented claim nothing checks is indistinguishable from a true one
    until somebody reads the code. This gate makes that comparison
    mechanical and runs it on every commit that touches either side, so a
    rule corrected in one place and left stale in another is reported by
    name rather than passing on the strength of the corrected one.
ARCHITECTURE: A SECOND, separate gate from check_file_size.py: its trigger
    population is the configured published surfaces plus the enforcing
    script itself, not the staged file set check_file_size.py measures, so
    folding this into that gate's per-file loop would fire it on the wrong
    population (see this AC's own HOST constraint). Consumes the SAME
    configuration reads as check_file_size.py -- CHECKED_EXTENSIONS,
    FILE_LINE_LIMITS, DEFAULT_LINE_LIMIT from config.py -- rather than
    re-deriving the enforced scope or limits; never greps check_file_size.py's
    source for a constant (CLAUDE.md's "Verify Behaviorally, Not by Grep").
    The list of surfaces to compare is itself config-driven
    (file_size.published_rule_surfaces), never a list written into this
    check, so a newly added published surface is watched automatically once
    it is added to that list. Each surface path is resolved relative to
    THIS SCRIPT'S OWN directory (mirroring config.py's own __file__-relative
    resolution of commit_guardian.json), so the same gate works identically
    self-hosted (templates/scripts/commit_guardian/) or deployed into a
    consumer project (.leafcutter/scripts/commit_guardian/).

    THREE FACTS COMPARED, PER SURFACE: which KINDS are covered (against
    CHECKED_EXTENSIONS); WHEN the rule applies -- whether a surface claims a
    new-files-only exemption -- established on the enforced side not by
    parsing check_file_size.py but by EXERCISING its own real
    ``_classify_file`` verdict function against a throwaway probe (see
    ``_enforced_applies_to_modified_files``); and HOW LONG a file of a kind
    may be, against the real, enforced FILE_LINE_LIMITS. A surface that
    makes no claim about a given fact is never treated as disagreeing on it.

Exit Codes:
    0 - Every configured published surface's claims agree with the real,
        enforced rule on every fact that surface makes a claim about.
    1 - At least one surface's claim disagrees with the enforced rule on at
        least one fact (every surface was itself readable and parseable).
    2 - INDETERMINATE: at least one configured surface could not be read or
        (for a JSON surface) could not be parsed. Agreement is never
        reported for the remaining surfaces in this case.

Usage:
    python check_file_size_rule_parity.py
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

from check_file_size import _classify_file
from config import (
    CHECKED_EXTENSIONS,
    DEFAULT_LINE_LIMIT,
    FILE_LINE_LIMITS,
    PUBLISHED_RULE_SURFACES,
)

_SCRIPT_DIR = Path(__file__).resolve().parent

# A dotted token of 1-4 letters, not preceded by another word character (so
# "e.g." and "check_file_size.py" -- the dot immediately following a letter
# -- are never mistaken for a claimed extension) and not followed by more
# letters (so ".pyc" is read whole, not truncated to ".py").
_EXTENSION_PATTERN = re.compile(r"(?<!\w)\.([a-zA-Z]{1,4})(?![a-zA-Z])")

# A surface may correctly document kinds it deliberately does NOT cover
# (e.g. commit_guardian.json's own file_size._comment lists both an IN
# SCOPE and an OUT OF SCOPE set). Only the portion before this marker is
# read as a claim of coverage; naming an out-of-scope kind is not a claim
# that it is covered.
_OUT_OF_SCOPE_MARKER = re.compile(r"out of scope", re.IGNORECASE)

# Lines containing any of these tokens are what a non-JSON published
# surface's excerpt is narrowed to, so a surface that discusses many rules
# (e.g. the full README.md hook-reference table) is compared only on its
# file-size-rule passage, not on every other hook's own kind mentions.
_ANCHOR_TOKENS = ("check_file_size.py", "check-file-size", "file_size")

# A claimed per-kind numeric limit stated in WORDS: a run of digits
# immediately followed by "line"/"lines" (e.g. "400 lines max per file").
# Deliberately narrow (requires the literal word "line(s)" right after the
# number) so a schema example like "hard limits" or an unrelated count
# ("13 tracked files") is never mistaken for a claimed limit. Paired with
# every extension mentioned elsewhere on the SAME line by
# `_extract_limit_claims`, so this phrasing only ever appears once per
# line in practice (a future surface may legitimately use it).
_LIMIT_PATTERN = re.compile(r"(\d{1,6})\s*lines?\b", re.IGNORECASE)

# A claimed per-kind numeric limit stated by ADJACENCY: a dotted extension
# token immediately followed (across at most an optional closing quote and
# an optional colon/whitespace) by a run of digits. This is the phrasing
# the REAL published surfaces actually use -- commit_guardian.json's
# `file_size._comment` (".py 400 (unchanged), .sql 600 (unchanged), ...")
# and README.md's schema-row JSON example (`{".py": 400, ".sql": 600}`) --
# neither of which ever places the word "line"/"lines" next to a digit, so
# `_LIMIT_PATTERN` alone finds zero claims in either (GE-127d-1 real-
# artifact regression: a genuine limit-claim mutation in either surface
# passed this gate silently before this pattern was added). Anchoring on
# adjacency to the extension token -- rather than scanning the whole line
# for any number, as `_LIMIT_PATTERN` does -- is what keeps prose numbers
# with no preceding extension ("the empty 600-1000 band across the 13
# tracked files", "43% headroom") from being read as a claim: nothing in
# the real `_comment` places a dotted extension immediately before either
# of those numbers.
_ADJACENT_EXT_LIMIT_PATTERN = re.compile(r'\.([a-zA-Z]{1,4})(?![a-zA-Z])"?\s*:?\s*(\d{1,6})\b')

# "When it applies" claims: a surface claiming every changed file is
# checked (no exemption) always takes precedence, so "not only newly added
# ones" -- which textually contains "only newly added" -- is read as the
# no-exemption claim it is, never as the opposite.
_NO_EXEMPTION_PATTERN = re.compile(r"every changed file", re.IGNORECASE)
_EXEMPTION_PATTERN = re.compile(r"only\s+(?:to\s+)?newly[\s-]?added|new[\s-]?files?[\s-]?only", re.IGNORECASE)

DISAGREEMENT_TOKEN = "DISAGREEMENT"
INDETERMINATE_PREFIX = "INDETERMINATE: reason="


class SurfaceUnreadableError(Exception):
    """A configured published surface could not be read or parsed.

    Attributes:
        surface: The configured surface path (relative to this script's
            own directory) that could not be resolved.
        reason: Human-readable explanation, always naming ``surface``.
    """

    def __init__(self, surface: str, reason: str) -> None:
        self.surface = surface
        self.reason = reason
        super().__init__(reason)


def _relevant_excerpt(raw_text: str) -> str:
    """Narrow a non-JSON surface's text to its file-size-rule passage.

    Args:
        raw_text: The surface's full, unmodified text content.

    Returns:
        The lines of ``raw_text`` that mention any of ``_ANCHOR_TOKENS``,
        joined with newlines; the whole of ``raw_text`` unchanged when no
        line mentions any anchor (e.g. a surface dedicated entirely to this
        one rule, carrying no hook-name anchor of its own).
    """
    matching = [line for line in raw_text.splitlines() if any(token in line for token in _ANCHOR_TOKENS)]
    return "\n".join(matching) if matching else raw_text


def _in_scope_portion(text: str) -> str:
    """Return only the portion of *text* preceding an "out of scope" marker.

    Args:
        text: The excerpt to search.

    Returns:
        ``text`` truncated just before the first case-insensitive "out of
        scope" occurrence, or the whole of ``text`` when the marker is
        absent.
    """
    match = _OUT_OF_SCOPE_MARKER.search(text)
    return text[: match.start()] if match else text


def _extract_kinds(text: str) -> set[str]:
    """Extract the set of dotted extension tokens *text* mentions.

    Args:
        text: Prose (or a JSON comment string) to scan.

    Returns:
        The distinct, lower-cased dotted extensions found (e.g. ``{".py"}``).
    """
    return {f".{match.group(1).lower()}" for match in _EXTENSION_PATTERN.finditer(text)}


def _extract_when_applies_claim(text: str) -> bool | None:
    """Read whether *text* claims a new-files-only exemption.

    Args:
        text: A surface's claim-relevant text.

    Returns:
        ``True`` when the text claims only newly added files are checked
        (an exemption for modifications). ``False`` when it claims every
        changed file is checked (no exemption). ``None`` when the text
        makes no claim about when the rule applies at all -- never
        compared against the enforced side.
    """
    if _NO_EXEMPTION_PATTERN.search(text):
        return False
    if _EXEMPTION_PATTERN.search(text):
        return True
    return None


def _extract_limit_claims(text: str) -> dict[str, int]:
    """Read each per-kind numeric line-limit *text* claims.

    Two independent phrasings are recognised, since neither published
    surface uses the other's style (see this module's own DECISION
    HISTORY and the two pattern comments above):

    1. ADJACENCY (`_ADJACENT_EXT_LIMIT_PATTERN`): the extension token sits
       immediately next to its number -- ".py 400" (commit_guardian.json's
       real `_comment`) or `".py": 400` (README.md's real schema-row JSON
       example). Each match pairs its OWN extension with its OWN number
       directly, so multiple claims on one line (or, as in the real
       `_comment`, one single un-newlined string) are never conflated.
    2. WORDS (`_LIMIT_PATTERN`), scanned line by line so a claimed number
       is only paired with an extension mentioned on the SAME line -- e.g.
       "Python (.py) files: 400 lines max per file." -- never with an
       unrelated extension elsewhere in a multi-line surface. Only applied
       where adjacency found nothing for a given extension, so an
       adjacency match is never overwritten by a coarser line-wide one.

    Args:
        text: A surface's claim-relevant text.

    Returns:
        A mapping of claimed extension to claimed line limit. Empty when
        the text makes no such claim.
    """
    claims: dict[str, int] = {}
    for adjacent_match in _ADJACENT_EXT_LIMIT_PATTERN.finditer(text):
        claims[f".{adjacent_match.group(1).lower()}"] = int(adjacent_match.group(2))

    for line in text.splitlines():
        limit_match = _LIMIT_PATTERN.search(line)
        if not limit_match:
            continue
        for ext in _extract_kinds(line):
            claims.setdefault(ext, int(limit_match.group(1)))
    return claims


def _read_surface_claim_text(surface: str) -> str:
    """Read *surface*'s claim-relevant text, the shared input every fact is read from.

    Args:
        surface: A path relative to THIS SCRIPT'S OWN directory (e.g.
            ``"README.md"``, ``"commit_guardian.json"``) -- never a
            project-root-relative path, so the same configured list works
            self-hosted and in a deployed consumer install alike.

    Returns:
        For a ``.json`` surface, its ``file_size._comment`` string (empty
        when the field is absent or not a string) -- never the machine
        ``checked_extensions``/``line_limits`` values themselves, which are
        the enforced side being compared AGAINST, not a second reader of
        the same fact. For any other surface, the anchor-narrowed excerpt
        ``_relevant_excerpt`` returns.

    Raises:
        SurfaceUnreadableError: the surface is missing, cannot be opened,
            or (for a ``.json`` surface) cannot be parsed as JSON.
    """
    path = _SCRIPT_DIR / surface
    try:
        raw_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SurfaceUnreadableError(surface, f"'{surface}' could not be read: {exc}") from exc

    if path.suffix.lower() != ".json":
        return _relevant_excerpt(raw_text)

    try:
        document = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise SurfaceUnreadableError(surface, f"'{surface}' could not be parsed as JSON: {exc}") from exc
    comment = document.get("file_size", {}).get("_comment", "")
    return comment if isinstance(comment, str) else ""


_SurfaceClaim = tuple[set[str], "bool | None", dict[str, int]]


def _gather_surface_claims(surfaces: list[str]) -> tuple[list[str], dict[str, _SurfaceClaim]]:
    """Read and classify every configured surface's claim, on all three facts.

    Every surface is attempted, so more than one unreadable surface can be
    named in the same run; but the moment any surface is unreadable, no
    claim is resolved for any surface -- agreement is never reported for
    surfaces this run did not fully examine.

    Args:
        surfaces: Configured ``file_size.published_rule_surfaces`` entries.

    Returns:
        An ``(indeterminate_lines, claims)`` pair. When
        ``indeterminate_lines`` is non-empty, ``claims`` is incomplete and
        the caller must exit 2 without using it.
    """
    indeterminate: list[str] = []
    claims: dict[str, _SurfaceClaim] = {}

    for surface in surfaces:
        try:
            text = _read_surface_claim_text(surface)
        except SurfaceUnreadableError as exc:
            indeterminate.append(f"{INDETERMINATE_PREFIX}{exc.reason}")
            continue
        claims[surface] = (
            _extract_kinds(_in_scope_portion(text)),
            _extract_when_applies_claim(text),
            _extract_limit_claims(text),
        )

    return indeterminate, claims


def _enforced_applies_to_modified_files() -> bool:
    """Exercise the REAL, unmodified ``check_file_size._classify_file`` to
    establish -- behaviourally, never by reading its source -- whether a
    modified (not newly added) file that grows past its limit is refused.

    Writes a throwaway probe file to a fresh temporary directory and calls
    ``_classify_file`` directly with a ``previous_lengths`` entry recording
    a length within the limit, modelling a file that existed below its
    limit and then grew past it -- the exact scenario a new-files-only
    exemption would need to excuse. Uses the SAME measurement function
    ``main()`` calls at real commit time, never a re-derived copy of it.

    Returns:
        ``True`` when the enforced rule refuses that growth (no
        new-files-only exemption is in force); ``False`` when it is judged
        to pass (an exemption would be in force).

    Raises:
        OSError: the probe file could not be written.
    """
    ext = CHECKED_EXTENSIONS[0] if CHECKED_EXTENSIONS else ".py"
    limit = FILE_LINE_LIMITS.get(ext, DEFAULT_LINE_LIMIT)
    probe_lines = "\n".join(f"probe line {i}" for i in range(limit + 5)) + "\n"

    with tempfile.TemporaryDirectory() as tmp:
        probe_path = str(Path(tmp) / f"probe{ext}")
        try:
            Path(probe_path).write_text(probe_lines, encoding="utf-8")
        except OSError as exc:
            raise OSError(f"could not write the when-it-applies probe file: {exc}") from exc
        verdict, _lines, _reference = _classify_file(probe_path, {probe_path: max(0, limit - 1)})

    return verdict != "pass"


def _disagreements_for_surface(
    surface: str,
    claim: _SurfaceClaim,
    enforced_kinds: set[str],
    enforced_exemption: bool,
    enforced_limits: dict[str, int],
) -> list[str]:
    """Build every disagreement line for one surface, across all three facts.

    Args:
        surface: The configured surface path, for the reported message.
        claim: This surface's ``(kinds, when_applies, limits)`` claim, as
            returned by ``_gather_surface_claims``.
        enforced_kinds: The real, enforced ``CHECKED_EXTENSIONS``.
        enforced_exemption: Whether the enforced rule exempts a modified
            file from its limit (always ``False`` since GE-127b-1).
        enforced_limits: The real, enforced ``FILE_LINE_LIMITS``.

    Returns:
        One line per fact this surface makes a claim about that disagrees
        with the enforced side. Empty when every claim this surface makes
        agrees.
    """
    kinds_claim, when_claim, limit_claims = claim
    lines: list[str] = []

    if kinds_claim != enforced_kinds:
        lines.append(
            f"{DISAGREEMENT_TOKEN}: {surface} claims kinds={sorted(kinds_claim)} "
            f"but the enforced kinds are {sorted(enforced_kinds)}"
        )

    if when_claim is not None and when_claim != enforced_exemption:
        lines.append(
            f"{DISAGREEMENT_TOKEN}: {surface} claims a new-files-only exemption={when_claim} "
            f"but the enforced rule's exemption is {enforced_exemption}"
        )

    for ext, claimed_limit in sorted(limit_claims.items()):
        enforced_limit = enforced_limits.get(ext, DEFAULT_LINE_LIMIT)
        if claimed_limit != enforced_limit:
            lines.append(
                f"{DISAGREEMENT_TOKEN}: {surface} claims {ext} limit={claimed_limit} "
                f"but the enforced limit is {enforced_limit}"
            )

    return lines


def main() -> int:
    """Reconcile every configured published surface against the enforced rule.

    Returns:
        Exit code: 0 (every surface agrees on every fact it claims), 1 (at
        least one surface disagrees on at least one fact), or 2
        (INDETERMINATE -- at least one surface could not be read or
        parsed).
    """
    enforced_kinds = set(CHECKED_EXTENSIONS)
    surfaces = list(PUBLISHED_RULE_SURFACES)

    indeterminate, claims = _gather_surface_claims(surfaces)
    if indeterminate:
        for line in indeterminate:
            print(line, file=sys.stderr)
        return 2

    enforced_exemption = not _enforced_applies_to_modified_files()

    disagreements: list[str] = []
    for surface in surfaces:
        disagreements.extend(
            _disagreements_for_surface(surface, claims[surface], enforced_kinds, enforced_exemption, FILE_LINE_LIMITS)
        )

    print(f"Compared {len(surfaces)} surface(s) against the enforced file-size rule.")
    for line in disagreements:
        print(line)

    return 1 if disagreements else 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-21 [python-coder/GE-127d-1 real-artifact fix]: `_LIMIT_PATTERN`
  alone (digits immediately followed by "line"/"lines") extracted ZERO
  claims from either real published surface -- commit_guardian.json's
  `_comment` ("... .py 400 (unchanged) ...") and README.md's schema-row
  JSON example (`{".py": 400, ".sql": 600}`) both state a claim by placing
  the number immediately next to the extension, never next to the word
  "line(s)". A regex written against an invented test fixture that
  happened to use "N lines" phrasing therefore passed while the gate was
  blind on the actual on-disk data format ("how long" was a 0-for-2 no-op
  against the real surfaces it exists to watch). Added
  `_ADJACENT_EXT_LIMIT_PATTERN`, anchored on the extension token itself
  rather than on any number in the line, so unrelated counts in the same
  `_comment` ("the empty 600-1000 band across the 13 tracked files", "43%
  headroom") are never mistaken for a claim. The original word-based
  pattern is kept (a future surface may legitimately use "N lines"
  phrasing, and `test_ge_127d_1_scope_extension.py`'s "how long" descriptor
  depends on it); an adjacency match always wins over a same-extension
  word-based one via `dict.setdefault`.
- 2026-09-21 [python-coder/GE-127d-1 rework, H-2]: Extended from comparing
  "which kinds" alone to all three facts GE-127d-1's Gherkin names. "When
  it applies" is established on the enforced side by EXERCISING the real
  check_file_size._classify_file() against a throwaway probe
  (_enforced_applies_to_modified_files), never by parsing check_file_size.py's
  source, per this AC's own "evaluate the enforced side by exercising the
  gate" constraint; "how long" is read directly from FILE_LINE_LIMITS,
  exactly as "which kinds" already reads CHECKED_EXTENSIONS. A surface
  making no claim about a given fact is never treated as disagreeing on it.
  pr-reviewer (10:45) and ac-validator (11:05) both independently found the
  prior single-axis scope was never put in front of architect-review for an
  explicit accepted-narrowing sign-off, so it is not carried forward here.
- 2026-09-15 [python-coder/GE-127d-1]: Created. Compared the "which kinds
  are covered" fact only; the direction of correction for the two real
  stale surfaces found (README.md's check-file-size row and, historically,
  commit_guardian.json's file_size._comment) is to correct the DOCUMENTATION
  to match the already-deliberately-widened enforced behaviour, never to
  restore the old exemption.
====================================================================
"""
