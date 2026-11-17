"""Real graph facade and TypeSafe chunk adapter over a controlled offline transport."""
import contextvars
from dataclasses import replace

from kernel.contracts.task import RevisionInfo
from kernel.providers.jev import TypeSafeJevAdapter
from kernel.providers.jev_wire import RawResponse
from kernel.scheduler.nodes_execute import ShareBudget
from tests.kernel.helpers import make_context, make_invocation
from tests.knowledge.query_answer_contract_acceptance_research_support import ResearchAssessmentCase
from tests.knowledge.query_answer_contract_acceptance_support import ROOT, SOURCE_SHA


class AnswerTransport:
    """Return explicit finite choices at the provider boundary and record actual chunks."""

    name, version = 'controlled-independent-transport', '1'

    def __init__(self):
        self.calls = []

    async def send(self, state, questions, *, purpose=''):
        self.calls.append((purpose, list(questions)))
        choices = {'population': 'returned_entities', 'inclusion': 'root_excluded',
                   'root': 'clarify', 'readiness': 'ready', 'kind': 'AcceptanceCriterion',
                   'query': 'get_acceptance_criteria'}
        answers = {}
        for key, question in questions.items():
            if question['type'] == 'noul':
                answers[key] = {'type': 'noul', 'noul': 0.99 if key == 'field.canonical_id' else 0.01}
            else:
                picked = choices[key]
                assert picked in question['criteria']
                answers[key] = {'type': 'choice', 'choice': picked, 'confidence': 1.0,
                                'probabilities': {c: float(c == picked) for c in question['criteria']}}
        return RawResponse(model='controlled-offline', answers=answers, input_tokens=10, output_tokens=1)

    async def aclose(self):
        pass


class TestGraphProviderChunks(ResearchAssessmentCase):
    """First and subsequent actual adapter chunks charge the same scheduler share."""

    async def invoke_chunked(self, allowance):
        self.service()
        transport = AnswerTransport()
        adapter = TypeSafeJevAdapter(transport, timeout_seconds=5, max_questions_per_call=5,
            max_state_chars=60000, max_retries=0, retry_backoff_seconds=0, model_name='controlled-offline')
        config = self.config.model_copy(update={'jev': self.config.jev.model_copy(
            update={'max_questions_per_call': 5})})
        context = make_context(ROOT, config=config, jev=adapter)
        budget = ShareBudget({'jev': allowance})
        context = replace(context, budget=budget, scope=context.scope.model_copy(update={
            'revision': RevisionInfo(commit=SOURCE_SHA), 'component_ids': ['knowledge_management']}))
        payload = {'need': {'id': 'need.chunk', 'category': 'task_context', 'priority': 'required',
                           'question': 'Which acceptance criteria are declared?'},
                   'source_ids': ['knowledge.graph'], 'jev_reserve': 5}
        invocation = make_invocation().model_copy(update={'input_payload': payload})
        result = await self.env.bindings.resolve('retrieve.repository', '1.0.0').ainvoke(invocation, context)
        await adapter.aclose()
        return result, budget, transport.calls

    def test_actual_chunks_charge_once_and_leave_reserved_calls(self):
        # covers: KM-500e-1
        # angle: seam
        self._asyncioRunner.run(self.check_chunks(), context=contextvars.copy_context())

    async def check_chunks(self):
        result, budget, calls = await self.invoke_chunked(13)
        planning = [keys for purpose, keys in calls if purpose == 'knowledge.answer_contract']
        assert len(planning) == 5 and sum(map(len, planning)) == 23
        assert len(calls) == 8
        assert sum(item.calls for item in result.usage) == len(calls)
        assert budget.available('jev') == 5
        assert self.requests and self.requests[-1].answer_requirements.required_fields == ['canonical_id']

    def test_unaffordable_multichunk_plan_is_refused_before_transport(self):
        # covers: KM-500e-1
        # angle: discrimination
        self._asyncioRunner.run(self.check_refusal(), context=contextvars.copy_context())

    async def check_refusal(self):
        result, budget, calls = await self.invoke_chunked(9)
        assert calls == []
        assert result.status.value == 'blocked'
        assert result.error.code == 'budget_exhausted'
        assert budget.available('jev') == 9
        assert self.requests == []
