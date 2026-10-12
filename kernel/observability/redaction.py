"""
MODULE: kernel.observability.redaction
GOAL: Redactor that masks secrets and policy-restricted content in any JSON-like structure before
    it leaves the process (Langfuse export, spool, Jev and host packets).
BUSINESS CONTEXT: Repo excerpts and run data go to third parties (Rev 3 sections 12 and 13.3);
    loaded credentials, secret-looking strings and files covered by the repo deny rules must never
    be exported, and export size must stay bounded. Persisted evidence is never touched.
ARCHITECTURE: Redactor.mask(data=...) walks dicts, lists, tuples, pydantic models and strings.
    Order per string: exact loaded secret values, scanner regex rules (vendored from the
    security-scanner), high-entropy tokens, then truncation. Dict-level rules: an entry whose
    locator/path matches a deny glob loses its excerpt/content/text; "excerpt" follows
    data_policy.telemetry_excerpts (truncated | hash | none). The signature matches Langfuse's
    MaskFunction so the instance plugs into Langfuse(mask=...).
"""

from __future__ import annotations

import fnmatch
import hashlib
import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import BaseModel

from kernel.config import DataPolicyConfig

# Vendored from templates/skills/security-scanner/scripts/scan_secrets.py (_RULES).
_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("PRIVATE_KEY", re.compile(r"-----BEGIN\s+(RSA|EC|OPENSSH)\s+PRIVATE KEY-----")),
    ("AWS_KEY", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("EXCHANGE_API_KEY", re.compile(
        r"(?i)(api_key|apikey|api_secret)[^\n]{0,30}['\"][A-Za-z0-9]{30,}['\"]")),
    ("GENERIC_SECRET", re.compile(
        r"(?i)(password|passwd|secret|token|auth_key)\s*[=:]\s*['\"][^'\"]{8,}['\"]")),
)
_TOKEN_RE = re.compile(r"[A-Za-z0-9+/=_\-]{20,}")
_ENTROPY_THRESHOLD = 4.5
_EXTENSION = re.compile(r"\.[A-Za-z0-9]{1,5}\b")
_RANDOM_PART = 20
_RANDOM_PART_ENTROPY = 4.2
_MIN_SECRET_LENGTH = 6
_MAX_DEPTH = 24
_PATH_KEYS = frozenset({"locator", "path", "file", "source_path"})
_BODY_KEYS = frozenset({"excerpt", "content", "text"})


def _in_path(text: str, match: re.Match[str]) -> bool:
    """True if the match sits in a path: after a separator, or before one or a file extension."""
    before = text[match.start() - 1] if match.start() else ""
    after = text[match.end():]
    return before in "/\\" or after[:1] in ("/", "\\", "#") or bool(_EXTENSION.match(after))


def shannon_entropy(token: str) -> float:
    """Return the Shannon entropy (bits per character) of token."""
    counts = Counter(token)
    total = len(token)
    return -sum((n / total) * math.log2(n / total) for n in counts.values())


def matches_deny_glob(path: str, deny_globs: Iterable[str]) -> bool:
    """Return True if a path (an optional #fragment is ignored) matches a repo deny glob."""
    normal = path.split("#", 1)[0].replace("\\", "/").removeprefix("./")
    base = normal.rsplit("/", 1)[-1]
    for glob in deny_globs:
        if fnmatch.fnmatchcase(normal, glob):
            return True
        if glob.startswith("**/") and fnmatch.fnmatchcase(normal, glob[3:]):
            return True
        if "/" not in glob and fnmatch.fnmatchcase(base, glob):
            return True
    return False


class Redactor:
    """Masks secrets, denied-file content and oversize fields in arbitrary data."""

    def __init__(self, secrets: Mapping[str, str], policy: DataPolicyConfig,
                 deny_globs: Iterable[str] = ()) -> None:
        """Create a redactor.

        Args:
            secrets: Loaded secret values by name (SecretSettings.secret_values()).
            policy: data_policy section (excerpt mode and field length limit).
            deny_globs: Repo deny rules (retrieval.deny_globs).
        """
        self._secrets = sorted(((n, v) for n, v in secrets.items()
                                if len(v) >= _MIN_SECRET_LENGTH),
                               key=lambda item: -len(item[1]))
        self._policy = policy
        self._deny = tuple(deny_globs)

    def __call__(self, *, data: Any, **_: Any) -> Any:
        """Langfuse MaskFunction entry point."""
        return self.mask(data)

    def mask(self, data: Any, _depth: int = 0) -> Any:
        """Return a redacted copy of data (dicts, lists, tuples, models and strings)."""
        if _depth > _MAX_DEPTH:
            return "[REDACTED:depth]"
        if isinstance(data, str):
            return self.mask_text(data)
        if isinstance(data, BaseModel):
            return self.mask(data.model_dump(mode="json"), _depth + 1)
        if isinstance(data, Mapping):
            return self._mask_mapping(data, _depth)
        if isinstance(data, (list, tuple, set, frozenset)):
            return [self.mask(item, _depth + 1) for item in data]
        if data is None or isinstance(data, (bool, int, float)):
            return data
        return self.mask_text(str(data))

    def mask_text(self, text: str) -> str:
        """Redact secrets in one string and truncate it to the field limit."""
        for name, value in self._secrets:
            text = text.replace(value, f"[REDACTED:{name}]")
        for rule_id, pattern in _RULES:
            text = pattern.sub(f"[REDACTED:{rule_id}]", text)
        text = _TOKEN_RE.sub(lambda match: self._entropy_sub(match, text), text)
        return self._truncate(text)

    def _entropy_sub(self, match: re.Match[str], text: str) -> str:
        """Replace a mixed letter/digit token whose entropy exceeds the threshold.

        A token inside a repository path (next to a separator or a file extension) is a name, not
        a secret, unless one of its parts is long and random.
        """
        token = match.group(0)
        mixed = any(c.isdigit() for c in token) and any(c.isalpha() for c in token)
        if not (mixed and shannon_entropy(token) > _ENTROPY_THRESHOLD):
            return token
        if _in_path(text, match) and not any(
                len(part) >= _RANDOM_PART and shannon_entropy(part) > _RANDOM_PART_ENTROPY
                for part in re.split(r"[_\-]", token)):
            return token
        return "[REDACTED:entropy]"

    def _truncate(self, text: str) -> str:
        """Cut text to telemetry_max_field_chars, marking the cut."""
        limit = self._policy.telemetry_max_field_chars
        if len(text) <= limit:
            return text
        return f"{text[:limit]}...[truncated {len(text) - limit} chars]"

    def _mask_mapping(self, data: Mapping[Any, Any], depth: int) -> dict[str, Any]:
        """Mask a mapping, applying the deny-glob and excerpt-policy rules."""
        denied = any(isinstance(data.get(k), str) and matches_deny_glob(data[k], self._deny)
                     for k in _PATH_KEYS)
        masked: dict[str, Any] = {}
        for key, value in data.items():
            name = str(key)
            if denied and name in _BODY_KEYS:
                masked[name] = "[REDACTED:deny_glob]"
            elif name == "excerpt" and isinstance(value, str):
                masked[name] = self._apply_excerpt_policy(value)
            else:
                masked[name] = self.mask(value, depth + 1)
        return masked

    def _apply_excerpt_policy(self, excerpt: str) -> str:
        """Apply data_policy.telemetry_excerpts to an excerpt string."""
        mode = self._policy.telemetry_excerpts
        if mode == "none":
            return "[OMITTED:excerpt]"
        if mode == "hash":
            return "sha256:" + hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
        return self.mask_text(excerpt)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: A name inside a repository path is no longer an entropy secret
#   (`15_TICKET-20260826-ACD-2100c-3.md` reached a host as `[REDACTED:entropy].md`); a path part
#   that is long and random is still masked. (#KernelBootstrapV0/GROUND)
# - 2026-09-30 23:00 [python-coder]: Scanner rules are vendored, not imported by path from
#   templates/ (that tree is not shipped to adopters). (#KernelBootstrapV0/P2)
# - 2026-09-30 23:00 [python-coder]: The entropy rule only fires on tokens mixing letters and
#   digits so long file paths and hex digests are not blanked; secrets in prose still are.
#   (#KernelBootstrapV0/P2)
# ====================================================================
