"""Architecture acceptance for the retained retrieval LangGraph orchestration.

MODULE: test_query_answer_contract_acceptance_graph
GOAL: Reject a single-node wrapper over the prior imperative phase dispatcher.
BUSINESS CONTEXT: Retrieval research decisions must remain visible, bounded graph steps.
ARCHITECTURE: Compiled graph inspection complements separate public KernelService runs.
"""


def test_query_orchestration_exposes_distinct_connected_decision_nodes():
    # covers: KM-500e-1
    # covers: KM-500e-4
    # angle: discrimination
    """The retrieval graph owns real planning, readiness, selection and construction steps."""
    from integrations.query_graph import build_query_growth_graph
    from langgraph.graph.state import CompiledStateGraph
    graph = build_query_growth_graph()
    assert isinstance(graph, CompiledStateGraph)
    topology = graph.get_graph()
    required = {"load", "resume", "plan_answer", "clarify_scope", "readiness", "target",
                "capability_fit", "select", "clarify", "build", "execute"}
    assert required <= set(topology.nodes)
    connected = {edge.source for edge in topology.edges} | {edge.target for edge in topology.edges}
    assert required <= connected
    assert sum(bool(edge.conditional) for edge in topology.edges) >= 4
    assert any(edge.source == "capability_fit" and edge.target == "select" for edge in topology.edges)
