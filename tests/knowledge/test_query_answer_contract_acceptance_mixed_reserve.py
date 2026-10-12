"""Independent merge regression for mixed graph/native research and requester reserve.

The public KernelService, research planner, scheduler, native repository search,
neutral assessment and persistence are real. Only graph storage and Jev are
controlled boundaries; no live provider or database is contacted.
"""
import contextvars

from kernel.config import SourceConfig
from kernel.contracts import schema_ids
from tests.knowledge.query_answer_contract_acceptance_research_support import ResearchAssessmentCase


class TestMixedSourceResearchReserve(ResearchAssessmentCase):
    """A source split must not let graph planning consume a caller's reserve."""

    def configure_mixed(self, limit):
        self.config = self.config.model_copy(update={
            "limits": self.config.limits.model_copy(update={"max_jev_calls": limit}),
            "sources": [*self.config.sources, SourceConfig(
                id="repo.answers", kind="repo_text", categories=["task_context"],
                roots=["docs/reference/knowledge-retrieval-answers.md"])],
        })

    async def run_mixed(self, limit, reserve):
        self.configure_mixed(limit)
        task = self.task_with(None)
        task = task.model_copy(update={"input_payload": {
            **task.input_payload, "jev_reserve": reserve}})
        result = await self.service().start_run(task)
        values = await self.checkpoint_values(result.run_id)
        children = [r for r in values["requests"].values()
                    if r.payload_schema == schema_ids.RETRIEVAL_REQUEST]
        return result, children

    def test_graph_and_native_children_leave_the_requested_reserve(self):
        # covers: KM-500e-1
        # angle: seam
        # angle: discrimination
        self._asyncioRunner.run(self.check_tight_budget(), context=contextvars.copy_context())

    async def check_tight_budget(self):
        limit, reserve = 8, 5
        result, children = await self.run_mixed(limit, reserve)
        assert result.usage_summary.jev_calls == self.jev.call_count
        assert limit - result.usage_summary.jev_calls >= reserve, {
            "remaining": limit - result.usage_summary.jev_calls,
            "reserve": reserve,
            "purposes": [b.purpose for b in self.jev.batches],
            "child_sources": [r.payload["source_ids"] for r in children],
            "status": result.status.value,
        }
        assert children or result.limitations, "A bounded refusal must explain the omitted work."

    def test_affordable_mixed_sources_keep_both_groups_and_answer_obligations(self):
        # covers: KM-500e-1
        # angle: seam
        # angle: criterion
        self._asyncioRunner.run(self.check_affordable(), context=contextvars.copy_context())

    async def check_affordable(self):
        _, children = await self.run_mixed(40, 5)
        assert {tuple(r.payload["source_ids"]) for r in children} == {
            ("knowledge.graph",), ("repo.answers",)}
        assert all(r.payload["answer_requirements"] == self.requirements for r in children)
        assert self.requests, "The actual graph consumer must be reached when affordable."
        assert any(b.purpose == "retrieval.rerank" for b in self.jev.batches)

    def test_reserve_and_obligations_survive_human_pause_and_reopened_service(self):
        # covers: KM-500e-1
        # angle: seam
        self._asyncioRunner.run(self.check_resume(), context=contextvars.copy_context())

    async def check_resume(self):
        import json
        from kernel.contracts import RunStatus
        from tests.kernel.integration.scenario_support import answer_human
        self.configure_mixed(15)
        self.requirements['scope'] = {
            'population': 'ac_descendants', 'root_id': 'KM-500c', 'levels': ['L2']}
        task = self.task_with(None)
        task = task.model_copy(update={'input_payload': {**task.input_payload, 'jev_reserve': 8}})
        pending = await self.service().start_run(task)
        assert pending.status == RunStatus.WAITING_HUMAN
        values = await self.checkpoint_values(pending.run_id)
        states = [item.continuation.state for item in values['work_items'].values()
                  if item.continuation and item.continuation.state.get('original_question')]
        assert states and all(state['jev_reserve'] == 8 for state in states)
        answer = answer_human(pending, {'free_text': json.dumps({'scope': {'inclusion': 'root_excluded'}})})
        resumed = await self.service().resume_run(pending.run_id, answer)
        assert 15 - resumed.usage_summary.jev_calls >= 8
        values = await self.checkpoint_values(resumed.run_id)
        children = [r for r in values['requests'].values()
                    if r.payload_schema == schema_ids.RETRIEVAL_REQUEST]
        assert children and all(r.payload['jev_reserve'] == 8 for r in children)
        assert all(r.payload['answer_requirements'] == self.requirements for r in children)
        assert self.requests and self.requests[-1].answer_requirements.scope.inclusion == 'root_excluded'
