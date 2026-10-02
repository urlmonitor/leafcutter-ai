"""
MODULE: tests.kernel.retrieval.test_retrieval_locators
GOAL: Behavioural tests of explicit locators on `retrieve.repository`: each form (path,
    `path#Lx-Ly`, `path#heading`, `path::Symbol`) is fetched exactly, marked in provenance and
    kept by ranking, and refused outside the read roots, under deny globs, on traversal and
    outside every configured source.
BUSINESS CONTEXT: An option or finding that cites `kernel/contracts/decision.py` must be able to
    pull exactly that place into the next evidence bundle; the lookup may never read more than a
    search could (Rev 3 sections 10.3 and 13.3).
ARCHITECTURE: Runs the real executor against a throwaway repository with ScriptedJev answering
    relevance; reads only the returned bundle. Offline and fast.
"""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from kernel.capabilities.retrieval import RepositoryRetrievalExecutor
from kernel.config import SourceConfig, load_kernel_config
from kernel.contracts import schema_ids
from kernel.contracts.enums import EvidenceCategory
from kernel.contracts.evidence import EvidenceNeed
from kernel.contracts.payloads import RetrievalRequestPayload
from kernel.providers.fakes import ScriptedJev, noul_answer
from tests.kernel.capabilities.support import invocation, no_git
from tests.kernel.helpers import as_json, bundle_of, make_context

CODE = ("class Decision:\n    status: str\n\n    def close(self):\n        return 1\n\n\n"
        "def helper():\n    return 2\n")
ADR = ("# ADR-9 Store\nintro\n\n## Context\nwhy we store\n\n## Alternatives\n"
       "Postgres was an alternative.\n\n### Neo4j\nrejected.\n\n## Consequences\nfiles.\n")


def _config(**retrieval: object):
    """Config with one repo_text source over `kernel` and `docs` (and retrieval overrides)."""
    base = load_kernel_config()
    source = SourceConfig(id="repo.all", kind="repo_text",
                          categories=[EvidenceCategory.PRIOR_DECISIONS],
                          roots=["kernel", "docs"], deny_globs=["docs/secret/*"])
    cfg = base.model_copy(update={"sources": [source]})
    if retrieval:
        cfg = cfg.model_copy(update={"retrieval": base.retrieval.model_copy(update=retrieval)})
    return cfg


class LocatorCase(unittest.TestCase):
    """A temp repository with a module, an ADR, denied files and a file outside every source."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve() / "repo"
        for rel, text in (("kernel/contracts/decision.py", CODE), ("docs/adr.md", ADR),
                          ("docs/secret/plan.md", "secret plan\n"), (".env", "TOKEN=1\n"),
                          ("elsewhere/notes.md", "notes\n"), ("kernel/key.pem", "PEM\n")):
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        (self.root.parent / "outside.md").write_text("outside\n", encoding="utf-8")
        self.jev = ScriptedJev().script("retrieval.rerank", "relevant.*", noul_answer(0.9))
        no_git(self)

    def fetch(self, *locators: str, question: str = "unrelated words zebra", config=None,
              scope_update=None, **request):
        """Run retrieval with the locators and return (result, bundle)."""
        need = EvidenceNeed(id="need.prior_decisions", category=EvidenceCategory.PRIOR_DECISIONS,
                            question=question)
        payload = RetrievalRequestPayload(
            need=need, explicit_locators=list(locators), **request).model_dump(mode="json")
        ctx = make_context(self.root, jev=self.jev, config=config or _config())
        if scope_update:
            ctx = replace(ctx, scope=ctx.scope.model_copy(update=scope_update))
        inv = invocation("retrieve.repository", schema_ids.RETRIEVAL_REQUEST, payload)
        result = asyncio.run(RepositoryRetrievalExecutor().ainvoke(inv, ctx))
        return result, bundle_of(result)

    def explicit(self, result) -> list:
        return [e for e in result.evidence if e.provenance.strategy == "explicit_locator"]


class TestEachForm(LocatorCase):
    """Every supported form returns exactly the named place, marked as explicit."""

    def test_a_repo_relative_path_returns_the_file(self) -> None:
        result, _ = self.fetch("kernel/contracts/decision.py")
        (item,) = self.explicit(result)
        self.assertEqual(item.excerpt, CODE.rstrip("\n"))
        self.assertTrue(item.source.locator.startswith("kernel/contracts/decision.py#L1-L9"))

    def test_a_line_range_returns_those_lines(self) -> None:
        result, _ = self.fetch("kernel/contracts/decision.py#L4-L5")
        (item,) = self.explicit(result)
        self.assertEqual(item.excerpt, "    def close(self):\n        return 1")
        self.assertEqual(item.source.locator, "kernel/contracts/decision.py#L4-L5")

    def test_a_heading_returns_the_section_with_its_subsections(self) -> None:
        result, _ = self.fetch("docs/adr.md#Alternatives")
        (item,) = self.explicit(result)
        self.assertIn("Postgres", item.excerpt)
        self.assertIn("### Neo4j", item.excerpt)
        self.assertNotIn("Consequences", item.excerpt)
        self.assertIn("(§Alternatives)", item.source.locator)

    def test_a_symbol_returns_the_class_or_method(self) -> None:
        result, _ = self.fetch("kernel/contracts/decision.py::Decision",
                               "kernel/contracts/decision.py::Decision.close")
        whole, method = self.explicit(result)
        self.assertIn("status: str", whole.excerpt)
        self.assertEqual(method.excerpt.strip(), "def close(self):\n        return 1")
        self.assertIn("(def Decision.close)", method.source.locator)

    def test_hash_and_provenance_describe_the_returned_text(self) -> None:
        from kernel.contracts.base import content_hash
        result, _ = self.fetch("docs/adr.md#Context")
        (item,) = self.explicit(result)
        self.assertEqual(item.content_hash, content_hash(item.excerpt))
        self.assertEqual(item.provenance.strategy, "explicit_locator")

    def test_an_explicit_hit_survives_a_low_relevance_judgement(self) -> None:
        """Kept from V0.1: a low Jev score cannot drop a named place (round E: none is asked)."""
        self.jev = ScriptedJev().script("retrieval.rerank", "relevant.*", noul_answer(0.05))
        result, _ = self.fetch("kernel/contracts/decision.py::helper")
        self.assertEqual(len(self.explicit(result)), 1)

    def test_an_explicit_hit_is_kept_without_being_judged(self) -> None:
        """Round E: a named place is kept regardless, so it is not sent to Jev (no judgement)."""
        self.jev = ScriptedJev().script("retrieval.rerank", "relevant.*", noul_answer(0.05))
        result, _ = self.fetch("kernel/contracts/decision.py::helper")
        self.assertEqual(len(self.explicit(result)), 1)
        self.assertIsNone(self.explicit(result)[0].provenance.relevance)
        sent = " ".join(c["locator"] for b in self.jev.batches
                        for c in as_json(b.state)["candidates"].values())
        self.assertNotIn("decision.py", sent)

    def test_explicit_hits_come_before_search_hits(self) -> None:
        result, _ = self.fetch("docs/adr.md#Consequences", question="alternatives postgres")
        self.assertEqual(result.evidence[0].provenance.strategy, "explicit_locator")
        self.assertTrue(any(e.provenance.strategy == "repo_text" for e in result.evidence))

    def test_locators_work_without_any_query_terms(self) -> None:
        result, bundle = self.fetch("kernel/contracts/decision.py::helper", question="a b")
        self.assertEqual(len(self.explicit(result)), 1)
        self.assertEqual(bundle.attempted_sources, [])


class TestRefusals(LocatorCase):
    """What a search could not read, a locator cannot read either."""

    def refused(self, locator: str, reason: str, **kwargs) -> None:
        result, bundle = self.fetch(locator, **kwargs)
        self.assertEqual(self.explicit(result), [], locator)
        self.assertTrue(any(repr(locator) in x and reason in x for x in bundle.limitations),
                        (reason, bundle.limitations))

    def test_traversal_and_absolute_paths_are_refused(self) -> None:
        self.refused("../outside.md", "must be relative")
        self.refused("docs/../../outside.md", "must be relative")
        self.refused(str(self.root.parent / "outside.md"), "must be relative")

    def test_deny_globs_are_refused_globally_and_per_source(self) -> None:
        self.refused("kernel/key.pem", "denied")
        self.refused("docs/secret/plan.md", "denied")

    def test_a_path_outside_every_source_root_is_refused(self) -> None:
        self.refused("elsewhere/notes.md", "not under any configured source")
        self.refused(".env", "not under any configured source")

    def test_scope_read_roots_restrict_locators(self) -> None:
        self.refused("kernel/contracts/decision.py", "read roots",
                     scope_update={"read_roots": ["docs"]})

    def test_a_requested_source_id_narrows_the_locator_sources(self) -> None:
        self.refused("docs/adr.md", "not under any configured source", source_ids=["other"])

    def test_missing_targets_are_reported_not_empty(self) -> None:
        self.refused("docs/nothing.md", "unreadable")
        self.refused("docs/adr.md#No such heading", "no heading matches")
        self.refused("kernel/contracts/decision.py::Nope", "no top-level class or function")
        self.refused("kernel/contracts/decision.py#L99-L100", "beyond the end")

    def test_the_number_of_locators_is_bounded(self) -> None:
        cfg = _config(max_explicit_locators=1)
        result, bundle = self.fetch("docs/adr.md#Context", "docs/adr.md#Consequences",
                                    config=cfg)
        self.assertEqual(len(self.explicit(result)), 1)
        self.assertTrue(any("max_explicit_locators=1" in x for x in bundle.limitations))


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Locator tests assert both the served forms and every refusal
#   path; refusals must show up as limitations, never as a silent empty result. (#KernelV01/B)
# ====================================================================
