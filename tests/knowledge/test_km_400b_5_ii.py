"""KM-400b-5-ii: when removing a failed generation itself fails, the result reports both failures.

Same fixture approach as KM-400b-5-i: a real Git commit whose AC YAML is written by yaml.safe_dump
and loaded by the real snapshot loader, published through the real neo4j_projection.publish via the
real knowledge.cli_sync.sync; only the Neo4j driver is replaced by doubles (subclasses of the
KM-400b-5-i ``FailureDouble``) that refuse writes (and optionally reads) as a read-only store would.

Contract these tests pin (the implementation must provide it):
  * the propagated failure keeps its type and its original count-check cause first, unreplaced;
  * after the cause, the message states, separately, that the failed generation was NOT removed in
    the exact form ``repository <repository_id> generation <generation_id>``, states the refusal
    received for the removal, and states what remains: the node and relationship figures with the
    word "remain", or the word "undetermined" when it could not be counted (never a 0);
  * ``backend.publication_removal`` is one of three distinguishable states:
      - ``{"outcome": "not_removed", "repository_id", "generation_id", "refusal",
           "remaining": {"nodes": n, "relationships": m} | "undetermined"}``
      - ``{"outcome": "partially_removed", ..., "remaining_kinds": [...], "remaining": {...}}``
      - ``{"outcome": "removed", ...}`` (unchanged from KM-400b-5-i);
  * the active generation of the repository is untouched.
"""

import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tests.knowledge.test_km_400b_2_ii import REPO_ID, TARGETS, _distinct_edges
from tests.knowledge.test_km_400b_5_i import FailureDouble, _prepare, _sync, store_scope_lines

REPO_ROOT = Path(__file__).resolve().parents[2]
REFUSAL = "store is read-only: write refused"
COUNT_CAUSE = "generation count validation failed"


class ReadOnlyDouble(FailureDouble):
    """After the publication's failure is first recorded, every write is refused as read-only."""

    refuse_reads = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.engaged = False
        self.refused = []

    async def _run(self, statement, params=None, write=False, **_ignored):
        from knowledge.errors import BackendUnavailable

        if 'g.status="failed"' in statement:
            self.engaged = True
        if self.engaged and (write or (self.refuse_reads and "RETURN count(" in statement)):
            self.refused.append(statement)
            raise BackendUnavailable(REFUSAL)
        return await super()._run(statement, params, write)


class UncountableReadOnlyDouble(ReadOnlyDouble):
    """Refuses the removal and the request to count what remains."""

    refuse_reads = True


class RelationshipRefusingDouble(FailureDouble):
    """Accepts node deletes (nodes only) and refuses relationship deletes."""

    def _delete(self, statement, params):
        from knowledge.errors import BackendUnavailable

        if "Snapshot" not in statement and "-[" in statement and "DETACH" not in statement:
            raise BackendUnavailable(REFUSAL)
        key = params.get("key")
        self.deleted_keys.append(key)
        if "Snapshot" in statement:
            self.snapshots.pop(key, None)
        else:
            for item in [i for i, g in self.nodes.items() if g == key]:
                del self.nodes[item]
        return []


def _prepare_with(double_cls, tmp_path, **kwargs):
    from tests.knowledge.test_km_400b_2_ii import _commit_repository
    from tests.knowledge.test_km_400b_2_i import _load

    sha = _commit_repository(tmp_path, list(TARGETS))
    loaded = _load(tmp_path, sha)
    store = double_cls(**kwargs)
    store.source_sha = loaded.source_sha
    store.scope_lines = store_scope_lines(loaded)
    return sha, loaded, store


def _split_cause(message):
    """Return (text up to and including the count-check cause, the text after it)."""
    match = re.search(r"relationships expected \d+ kept \d+", message)
    assert match, message
    return message[: match.end()], message[match.end() :]


def _without_ids(text, generation_id):
    return text.replace(generation_id, "<G>").replace(f"repository {REPO_ID}", "repository <R>")


def test_refused_removal_reports_original_cause_and_names_stranded_generation(tmp_path):
    # covers: KM-400b-5-ii
    # angle: criterion
    sha, loaded, store = _prepare_with(ReadOnlyDouble, tmp_path, drop_relationships=1)
    distinct = _distinct_edges(loaded)
    gid = loaded.generation_id
    own = store.own_key_for(loaded)
    before = store.untouched_state()
    assert store.active_key == store.prior_key  # control: an active generation exists

    with pytest.raises(ValueError) as caught:
        _sync(tmp_path, sha, store)

    message = str(caught.value)
    # the original cause is carried, with both figures, and was not replaced by the refusal
    cause, tail = _split_cause(message)
    assert f"relationships expected {distinct} kept {distinct - 1}" in cause, message
    assert COUNT_CAUSE in cause, message
    assert REFUSAL not in cause, message
    # the failed generation was stored, the removal was attempted, and it was refused
    assert store.dropped == 1
    assert store.refused, "the double never refused a write"
    # separately states not removed, naming R1 and G33, after the cause
    assert re.search(r"not removed", tail), message
    assert re.search(rf"repository {re.escape(REPO_ID)}\b", tail), message
    assert re.search(rf"generation {re.escape(gid)}\b", tail), message
    # the refusal received for the removal is stated
    assert REFUSAL in tail, message
    # what remains is counted, not 0 and not omitted
    assert "remain" in tail, message
    assert re.search(rf"\b{len(loaded.nodes)}\b", tail), message
    assert re.search(rf"\b{distinct - 1}\b", tail), message
    # structured result
    removal = store.publication_removal
    assert removal["outcome"] == "not_removed", removal
    assert removal["repository_id"] == REPO_ID, removal
    assert removal["generation_id"] == gid, removal
    assert REFUSAL in removal["refusal"], removal
    assert removal["remaining"] == {"nodes": len(loaded.nodes), "relationships": distinct - 1}
    # the data really is still stored, and the active generation is unchanged
    assert store.tagged(own) == (len(loaded.nodes), distinct - 1)
    assert store.active_key == store.prior_key
    assert store.untouched_state() == before


def test_partial_removal_is_named_as_partial(tmp_path):
    # covers: KM-400b-5-ii
    # angle: boundary
    sha, loaded, store = _prepare_with(RelationshipRefusingDouble, tmp_path, drop_relationships=1)
    distinct = _distinct_edges(loaded)
    gid = loaded.generation_id
    own = store.own_key_for(loaded)

    with pytest.raises(ValueError) as caught:
        _sync(tmp_path, sha, store)

    message = str(caught.value)
    cause, tail = _split_cause(message)
    assert COUNT_CAUSE in cause, message
    # nodes are really gone, relationships really remain
    assert store.tagged(own) == (0, distinct - 1), store.tagged(own)
    # named as partially removed, not as removed and not as wholly not removed
    assert "partially removed" in tail, message
    assert "not removed" not in tail, message
    assert "failed generation removed" not in message, message
    assert re.search(rf"generation {re.escape(gid)}\b", tail), message
    assert "relationships" in tail and re.search(rf"\b{distinct - 1}\b", tail), message
    assert REFUSAL in tail, message
    removal = store.publication_removal
    assert removal["outcome"] == "partially_removed", removal
    assert removal["remaining_kinds"] == ["relationships"], removal
    assert removal["remaining"] == {"nodes": 0, "relationships": distinct - 1}, removal
    assert removal["generation_id"] == gid and removal["repository_id"] == REPO_ID


def test_refused_removal_and_refused_count_reports_undetermined_never_zero(tmp_path):
    # covers: KM-400b-5-ii
    # angle: failure
    sha, loaded, store = _prepare_with(UncountableReadOnlyDouble, tmp_path, drop_relationships=1)
    gid = loaded.generation_id
    own = store.own_key_for(loaded)
    before = store.untouched_state()

    with pytest.raises(ValueError) as caught:
        _sync(tmp_path, sha, store)

    message = str(caught.value)
    cause, tail = _split_cause(message)
    assert COUNT_CAUSE in cause, message
    assert "not removed" in tail, message
    assert re.search(rf"generation {re.escape(gid)}\b", tail), message
    assert REFUSAL in tail, message
    assert "undetermined" in tail, message
    # never stated as zero, whatever the wording around it
    assert not re.search(r"\b0\b", _without_ids(tail, gid)), message
    removal = store.publication_removal
    assert removal["outcome"] == "not_removed", removal
    assert removal["remaining"] == "undetermined", removal
    assert REFUSAL in removal["refusal"], removal
    # nothing was lost, and the active generation is unchanged
    assert store.tagged(own)[0] == len(loaded.nodes)
    assert store.untouched_state() == before


def test_stranded_failure_is_distinguishable_from_a_removed_failure(tmp_path):
    # covers: KM-400b-5-ii
    # angle: discrimination
    sha, loaded, removed_store = _prepare(tmp_path, drop_relationships=1)
    with pytest.raises(ValueError) as removed_caught:
        _sync(tmp_path, sha, removed_store)
    other = tmp_path / "second"
    other.mkdir()
    sha2, loaded2, stranded_store = _prepare_with(
        UncountableReadOnlyDouble, other, drop_relationships=1
    )
    with pytest.raises(ValueError) as stranded_caught:
        _sync(other, sha2, stranded_store)

    assert removed_store.publication_removal["outcome"] == "removed"
    assert stranded_store.publication_removal["outcome"] == "not_removed"
    assert "failed generation removed" in str(removed_caught.value)
    assert "failed generation removed" not in str(stranded_caught.value)
    assert "not removed" in str(stranded_caught.value)
    assert "not removed" not in str(removed_caught.value)
    # the stranded state names what was left behind; the removed state names nothing left behind
    stranded = str(stranded_caught.value)
    assert re.search(rf"generation {re.escape(loaded2.generation_id)}\b", stranded), stranded
    assert "undetermined" in stranded and "undetermined" not in str(removed_caught.value)
    assert stranded_store.publication_removal["generation_id"] == loaded2.generation_id


_DRIVER = textwrap.dedent(
    """
    import json, sys
    from knowledge import cli_sync
    from tests.knowledge.test_km_400b_5_ii import UncountableReadOnlyDouble

    store = UncountableReadOnlyDouble(drop_relationships=1)
    store.source_sha = None
    store.scope_lines = []
    cli_sync.writer_backend = lambda root=None: store
    from knowledge.__main__ import main

    try:
        code = main()
    except SystemExit as exit_:
        code = exit_.code
    own = [k for k in store.snapshots if k not in store._foreign_keys()]
    print(json.dumps({"own_leftover": [store.tagged(k) for k in own]}), file=sys.stderr)
    raise SystemExit(code or 0)
    """
)


def test_km_400b_5_ii_reachable_from_entry_point(tmp_path):
    # covers: KM-400b-5-ii
    # angle: reachability
    # Entry point: `python -m knowledge sync --root <repo>` (knowledge.__main__.main() with real
    # argv, fresh subprocess); only the writer's Neo4j driver is replaced.
    from tests.knowledge.test_km_400b_2_ii import _commit_repository
    from tests.knowledge.test_km_400b_2_i import _load

    sha = _commit_repository(tmp_path, list(TARGETS))
    loaded = _load(tmp_path, sha)
    distinct = _distinct_edges(loaded)
    env = {k: v for k, v in os.environ.items() if not k.startswith("LEAFCUTTER_NEO4J")}
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    argv = ["knowledge", "sync", "--root", str(tmp_path), "--repository-id", REPO_ID,
            "--revision", sha]
    code = _DRIVER.replace("from knowledge.__main__ import main",
                           "from knowledge.__main__ import main\nsys.argv = %r" % (argv,))
    code = code.replace("store.source_sha = None", f"store.source_sha = {loaded.source_sha!r}")
    code = code.replace(
        "store.scope_lines = []", f"store.scope_lines = {store_scope_lines(loaded)!r}"
    )
    done = subprocess.run(
        [sys.executable, "-c", code], cwd=REPO_ROOT, env=env, capture_output=True, text=True,
        timeout=120,
    )
    assert done.returncode == 2, done.stderr
    lines = [json.loads(line) for line in done.stderr.splitlines() if line.startswith("{")]
    failure = next(line for line in lines if line.get("status") == "error")
    message = failure["message"]
    cause, tail = _split_cause(message)
    assert f"relationships expected {distinct} kept {distinct - 1}" in cause, message
    assert "not removed" in tail, message
    assert re.search(rf"repository {re.escape(REPO_ID)}\b", tail), message
    assert re.search(rf"generation {re.escape(loaded.generation_id)}\b", tail), message
    assert REFUSAL in tail and "undetermined" in tail, message
    leftover = next(line for line in lines if "own_leftover" in line)
    assert any(t[0] == len(loaded.nodes) for t in leftover["own_leftover"]), leftover
