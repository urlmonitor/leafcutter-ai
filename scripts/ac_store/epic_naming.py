"""
epic_naming.py — Title normalisation and concise EPIC-name derivation.

MODULE: epic_naming
GOAL: Turn a human-readable AC title into the PascalCase component of an EPIC
      folder name, applying quote stripping, non-ASCII punctuation
      normalisation, an idempotence guard, and — when the naive conversion is
      too long — LLM summarisation with word-boundary truncation as fallback.
BUSINESS CONTEXT: Implements ACD-1200a-6 (concise epic names) and
      ACD-1200a-3-ii / ACD-1200a-3-iii (ASCII-safe slugs, dry-run/real-run
      parity). Extracted from goal_to_epic.py so that file can meet the
      400-line check_file_size limit.
ARCHITECTURE: Pure string transformation plus one optional network call. Sits
      near the bottom of the goal-to-epic dependency graph: imports only
      epic_runtime (for the shared logger). Deployed flat beside
      goal_to_epic.py in <output_root>/scripts/ac_store/ (see
      AC_STORE_DEPLOY_MAP in scripts/build_phases.py).

AC coverage owned by this module:
    ACD-1200a-3-ii:  apostrophe/quote characters are deleted in place, not
                     turned into word boundaries.
    ACD-1200a-3-iii: ASCII-safe slug; _to_pascal_case is idempotent so dry-run
                     and real-run derive the same name from one code path.
    ACD-1200a-6:     epic folder name is concise (<=5 PascalCase words,
                     <=40 chars), via LLM summarisation with truncation
                     fallback.
"""

from __future__ import annotations

import re

from epic_runtime import get_logger

# ---------------------------------------------------------------------------
# PascalCase conversion
# ---------------------------------------------------------------------------

#: Characters stripped in-place (zero-width deletion) before PascalCase
#: conversion: U+0027 ASCII apostrophe, U+0022 double-quote,
#: U+0060 backtick, U+2019 curly apostrophe (ACD-1200a-3-ii).
_QUOTE_CHARS_TO_STRIP = chr(0x0027) + chr(0x0022) + chr(0x0060) + chr(0x2019)


def _strip_quote_chars(title: str) -> str:
    """Remove apostrophe and quote characters from *title* in-place.

    Deletes each of the following characters with zero width (no separator
    inserted, adjacent letters join into a single word):

    - U+0027 — ASCII apostrophe / straight single-quote
    - U+0022 — ASCII double-quote
    - U+0060 — backtick / grave accent
    - U+2019 — right single quotation mark (curly apostrophe)

    The deletion happens BEFORE any word-splitting so that a quote embedded
    mid-word (e.g. ``user's``) does not create a word boundary; the result
    is a single intact word (``users``), not two words (``user`` + ``s``).

    This function is a pure string transformation with no I/O and must NOT
    be wrapped in try/except (Error Handling Policy Rule 4).

    Args:
        title: Raw AC title string that may contain quote/apostrophe chars.

    Returns:
        Title string with all specified quote characters removed.
        Adjacent letters join directly — no separator is inserted.

    Examples::

        _strip_quote_chars("Validate user's API inputs")
        # → "Validate users API inputs"

        _strip_quote_chars("Reject malformed customer’s payloads")
        # → "Reject malformed customers payloads"

        _strip_quote_chars('say "hello" and `go`')
        # → "say hello and go"
    """
    return title.translate(str.maketrans("", "", _QUOTE_CHARS_TO_STRIP))


def _normalize_non_ascii_punct(title: str) -> str:
    """Normalize non-ASCII punctuation and symbols to spaces (word-boundary treatment).

    Characters with Unicode category P* (punctuation) or S* (symbol) or Z*
    (separator) that are not ASCII are replaced with a space so they are
    treated as word boundaries rather than being carried through literally
    into the PascalCase result.  This covers em-dash (U+2014), en-dash
    (U+2013), smart quotes, ellipsis, bullet points, and similar
    path-hostile characters.

    ASCII characters are passed through unchanged.  Characters that are
    neither ASCII nor classified as punctuation/symbol/separator (e.g.
    accented letters used as genuine word characters) are also passed
    through unchanged.

    This function is a pure string transformation with no I/O and must NOT
    be wrapped in try/except (Error Handling Policy Rule 4).

    Args:
        title: Title string that may contain non-ASCII punctuation.

    Returns:
        Title string with non-ASCII punctuation/symbols/separators replaced
        by single spaces.
    """
    import unicodedata  # noqa: PLC0415 — stdlib, deferred for module-load performance
    result: list[str] = []
    for ch in title:
        if ord(ch) < 128:
            result.append(ch)
        else:
            cat = unicodedata.category(ch)
            if cat.startswith("P") or cat.startswith("S") or cat.startswith("Z"):
                result.append(" ")
            else:
                result.append(ch)
    return "".join(result)


def _to_pascal_case(title: str) -> str:
    """Convert a human-readable title string to PascalCase.

    Pre-processing pipeline (applied in this order):
    1. Strip leading/trailing whitespace.
    2. Strip apostrophe/quote characters (U+0027, U+0022, U+0060, U+2019)
       in-place via :func:`_strip_quote_chars` so that a quote embedded
       mid-word (e.g. ``user's`` / ``customer’s``) joins its adjacent letters
       into a single PascalCase word (e.g. ``Users``/``Customers``) rather than
       creating a word boundary. This runs BEFORE non-ASCII normalisation so the
       curly apostrophe U+2019 is removed in-place instead of being turned into
       a space.
    3. Normalise remaining non-ASCII punctuation (em-dash, en-dash, ellipsis,
       etc.) to spaces via :func:`_normalize_non_ascii_punct` so that they act
       as word boundaries and do not appear literally in the output.
    4. Idempotence guard (acronym-safe): if the pre-processed string is a
       single token with a leading uppercase letter and no word separators
       (i.e. it is already PascalCase, such as a name previously produced by
       this function or by :func:`_derive_epic_name`), it is returned
       unchanged. This keeps re-application safe — e.g. a derived epic name
       passed back through :func:`assemble_epic_folder` — without corrupting
       casing, while a raw title containing an acronym (``validate API inputs``)
       still lower-cases the acronym tail (``ValidateApiInputs``) because it
       contains word separators and so skips the guard.
    5. Split on whitespace, hyphens, and underscores.
    6. Capitalise the first character of each non-empty token and join without
       separators.

    Args:
        title: The AC title string (e.g. "validate api inputs").

    Returns:
        PascalCase string (e.g. "ValidateApiInputs").  The result contains
        only the characters that survive pre-processing; non-ASCII punctuation
        is absent from the output.
    """
    # Strip apostrophe/quote characters (incl. non-ASCII U+2019) FIRST, in-place,
    # so a quote embedded mid-word (e.g. "user's" / "customer’s") joins its
    # adjacent letters ("Users"/"Customers") rather than becoming a word boundary.
    # This must precede non-ASCII normalisation, which would otherwise turn the
    # curly apostrophe U+2019 into a space and split the word.
    dequoted = _strip_quote_chars(title.strip())
    normalized = _normalize_non_ascii_punct(dequoted)
    # Idempotence guard (acronym-safe): an already-PascalCase single token
    # (leading uppercase, no word separators) is returned unchanged so that
    # re-applying the conversion does not corrupt casing (dry-run/real-run
    # parity, ACD-1200a-3-iii), while raw titles with separators still flow
    # through the split+capitalise path below.
    if normalized and normalized[0].isupper() and not re.search(r"[\s\-_]", normalized):
        return normalized
    words = re.split(r"[\s\-_]+", normalized)
    return "".join(word.capitalize() for word in words if word)


# ---------------------------------------------------------------------------
# Concise epic name derivation (ACD-1200a-6)
# ---------------------------------------------------------------------------

_EPIC_NAME_MAX_CHARS = 40
"""Maximum length (characters) for a derived EPIC PascalCase component.

When the naive PascalCase conversion of an AC title exceeds this threshold,
the system attempts LLM-assisted summarisation to produce a concise name.
See ACD-1200a-6 for the full acceptance criteria.
"""


def _summarise_title_via_llm(title: str) -> str | None:
    """Ask the Claude API to summarise *title* into a concise PascalCase name.

    Returns a PascalCase string of at most 5 words that captures the essential
    intent of *title*, or ``None`` if the model is unavailable or returns an
    unusable response.

    The function is intentionally thin: it calls the Anthropic SDK with a
    one-shot prompt and parses the first non-empty line of the response as
    the name. No retries, no streaming — the caller handles the fallback path.

    Args:
        title: The full AC title to summarise (e.g. "Cross-field constraints
               and relational references are enforced together").

    Returns:
        A PascalCase string of 1–5 capitalised words (e.g.
        "AcRelationalIntegrity"), or ``None`` on any error.
    """
    try:
        import anthropic  # noqa: PLC0415 — optional runtime dependency
    except ImportError:
        return None

    prompt = (
        "Summarise the following software feature title into a concise PascalCase "
        "identifier of at most 5 words (no spaces, no hyphens). The result must "
        "capture the essential intent of the title and must NOT naively concatenate "
        "all words. Reply with ONLY the PascalCase identifier and nothing else.\n\n"
        f"Title: {title}"
    )

    try:
        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=64,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:  # noqa: BLE001 — broad catch for network/API unavailability
        get_logger().warning(
            "LLM title summarisation failed (falling back to truncation): %s", exc
        )
        return None

    try:
        raw = message.content[0].text.strip()
    except (AttributeError, IndexError):
        return None

    # Strip any residual "EPIC-" prefix the model may have added
    if raw.upper().startswith("EPIC-"):
        raw = raw[5:]

    # Validate: must be non-empty, alphanumeric only, and at most 40 chars
    if raw and re.match(r"^[A-Za-z][A-Za-z0-9]{0,39}$", raw):
        return raw

    return None


def _truncate_pascal_at(pascal: str, max_chars: int) -> str:
    """Truncate *pascal* at a word boundary so the result is ≤ *max_chars* chars.

    "Words" inside a PascalCase string are identified by capital letters.
    The function retains as many complete capitalised words as fit within
    *max_chars*, ensuring no partial word is left at the end.

    If even the first word exceeds *max_chars*, the first word is kept as-is
    (the caller's only sensible option when the limit is very tight).

    Args:
        pascal: A PascalCase string, e.g. "CrossFieldConstraintsAndRelational".
        max_chars: Maximum number of characters in the returned string.

    Returns:
        A truncated PascalCase string with no trailing partial word and
        len ≤ max_chars (unless even the first word is longer, in which case
        the first word is returned unchanged).

    Examples::

        _truncate_pascal_at("CrossFieldConstraintsAndRelational", 20)
        # → "CrossFieldConstraints"  (≤20 chars, complete word boundary)

        _truncate_pascal_at("ValidateApiInputs", 40)
        # → "ValidateApiInputs"  (already ≤40)
    """
    if len(pascal) <= max_chars:
        return pascal

    # Split on capital letter boundaries to find word starts
    # re.finditer gives us (start_idx, word) pairs for each PascalCase word.
    word_starts = [m.start() for m in re.finditer(r"[A-Z][a-z0-9]*", pascal)]

    # Walk backwards through word boundaries to find the last boundary
    # where the prefix is within max_chars.
    best = ""
    for idx in reversed(word_starts):
        candidate = pascal[:idx]
        if len(candidate) <= max_chars and candidate:
            best = candidate
            break

    # Fallback: no boundary found within max_chars — return first word intact
    if not best:
        first_end = word_starts[1] if len(word_starts) > 1 else len(pascal)
        best = pascal[:first_end]

    return best


def _derive_epic_name(title: str) -> str:
    """Derive a concise PascalCase EPIC name from *title*.

    Algorithm (ACD-1200a-6):
    1. Compute the naive PascalCase conversion of *title*.
    2. If the result is ≤ 40 characters, return it unchanged.
    3. Otherwise, attempt LLM-assisted summarisation via
       :func:`_summarise_title_via_llm`.
    4. If the LLM returns a usable result, return that.
    5. If the LLM is unavailable or errors, truncate the naive result at
       40 characters (no trailing partial word) and return that.

    Args:
        title: The human-readable AC title string.

    Returns:
        A concise PascalCase string of ≤ 40 characters (unless the first
        word alone exceeds 40 characters, in which case the first word is
        preserved intact — a pathological edge case for unusually long words).

    Examples::

        _derive_epic_name("validate api inputs")
        # → "ValidateApiInputs"   (≤40 chars — no LLM needed)

        _derive_epic_name(
            "Cross-field constraints and relational references are enforced together"
        )
        # → "AcRelationalIntegrity"  (LLM summarised; or truncated fallback)
    """
    naive = _to_pascal_case(title)

    if len(naive) <= _EPIC_NAME_MAX_CHARS:
        return naive

    # Attempt LLM summarisation
    llm_result = _summarise_title_via_llm(title)
    if llm_result:
        return llm_result

    # Fallback: truncate at word boundary
    return _truncate_pascal_at(naive, _EPIC_NAME_MAX_CHARS)


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-08 00:00 [EPIC-AcParentChildLinkEnforcement/06]: Concise epic name derivation. (#EPIC-AcParentChildLinkEnforcement/06)
  Implements ACD-1200a-6: _derive_epic_name() replaces bare _to_pascal_case() in
  run(). When naive PascalCase result exceeds 40 characters, attempts LLM
  summarisation via _summarise_title_via_llm() (claude-3-5-haiku-latest, one-shot
  prompt for concise PascalCase of at most 5 words). Falls back to
  _truncate_pascal_at() which truncates at the last complete PascalCase word
  boundary within 40 characters when the model is unavailable or errors. Rejects
  naive concatenations like "Crossfieldconstraintsandrelationalreferencesareenforcedtogether".
- 2026-07-17 [ACD-1200a-3-iii]: ASCII-safe slug and dry-run/real-run parity.
  Implements ACD-1200a-3-iii: (1) Added _normalize_non_ascii_punct() to strip
  non-ASCII punctuation (em-dash, en-dash, smart quotes, etc.) to spaces before
  PascalCase conversion, ensuring the derived folder name contains only ASCII
  alphanumeric characters. (2) Updated _to_pascal_case() split regex to
  r"(?=[A-Z])|[\\s\\-_]+" so the function is idempotent on already-PascalCase
  strings (splits on PascalCase word boundaries in addition to whitespace/hyphens).
  (3) Removed redundant _to_pascal_case() call from assemble_epic_folder(); the
  caller (run()) already passes a pre-derived PascalCase epic_name from
  _derive_epic_name(), and re-applying the conversion corrupted the casing via
  str.capitalize() on a single-token PascalCase string. Both dry-run and real-run
  now use the same derived name from a single shared code path (n_location_rule: 1).
  Must not regress ACD-1200a-3-ii (apostrophe/quote stripping still applied via
  _strip_quote_chars() in _to_pascal_case()).
- 2026-09-14 12:00 [goal-to-epic-decompose]: Moved here from
  scripts/goal_to_epic.py, which exceeded the 400-line check_file_size limit.
  All six functions and both constants moved verbatim. The only edit is in
  _summarise_title_via_llm's except branch: the deferred
  logging.getLogger(__name__) became epic_runtime.get_logger(), keeping the
  pre-split logger name "goal_to_epic". Level, message and control flow are
  unchanged.

  _derive_epic_name() and _summarise_title_via_llm() stayed TOGETHER here
  rather than the caller being left behind in goal_to_epic.py, so mock patches
  must now target this module. unit_tests/ac_store/test_concise_epic_name.py
  did `patch.object(goal_to_epic, "_summarise_title_via_llm", ...)`, which
  after the split would rebind a name goal_to_epic re-exports but never calls —
  the stub would simply never be reached. Those seven sites were retargeted to
  `epic_naming`; no assertion was altered, only the patch's target module.
  (#TICKETLESS reason=file-size-decomposition-refactor)
====================================================================
"""
