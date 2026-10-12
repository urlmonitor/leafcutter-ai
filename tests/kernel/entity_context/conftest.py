"""Fixture creation stays source-only so missing runtime behavior fails test assertions."""

import asyncio

import pytest

from tests.kernel.entity_context.graph_selection_support import SelectionRig
from tests.kernel.entity_context.support import build, config_for, write_repo
from tests.kernel.intent.support import IntentCase


@pytest.fixture
def repo(tmp_path):
    """Real serialized canonical sources, isolated for every test."""
    write_repo(tmp_path)
    return tmp_path


class EntityServiceRig(IntentCase):
    """Public RunService with only classifier answers controlled by the test."""

    def setUp(self):
        # This helper is also used outside unittest's run(), which normally sets
        # up the runner required by IsolatedAsyncioTestCase's cleanup callbacks.
        if self._asyncioRunner is None:
            self._setupAsyncioRunner()
            self.addCleanup(self._tearDownAsyncioRunner)
        super().setUp()

    def prepare(self, **limits):
        write_repo(self.repo)
        self.config = config_for(**limits)
        build(self.repo, self.config)
        return self

    def start(self, goal, **extra):
        return asyncio.run(self.service().start_run(self.goal_task(goal, **extra)))

    def values(self, run_id):
        return asyncio.run(self.checkpoint_values(run_id))

    def resume(self, run_id, answer):
        return asyncio.run(self.service().resume_run(run_id, answer))


@pytest.fixture
def rig():
    """Prepare source-independent service helpers; tests choose when to build an index."""
    instance = EntityServiceRig()
    instance.setUp()
    try:
        yield instance
    finally:
        instance.doCleanups()


@pytest.fixture
def selection(tmp_path):
    return SelectionRig(tmp_path)
