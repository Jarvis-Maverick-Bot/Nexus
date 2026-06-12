from __future__ import annotations

from nexus.governance.errors import ErrorCode
from nexus.governance.execution import validate_packet_dependency_graph

from ._evidence import write_evidence
from .fixtures.execution import valid_dependency_graph


def test_packet_dependency_graph_accepts_acyclic_graph() -> None:
    result = validate_packet_dependency_graph(valid_dependency_graph())

    assert result.accepted is True
    write_evidence("execution/dependency-graph-valid.json", result.to_evidence(), slice_id="l1gov-slice-004")


def test_packet_dependency_graph_rejects_missing_prerequisite_node() -> None:
    graph = valid_dependency_graph(prerequisites={"wp-421-002": ("wp-421-missing",)})

    result = validate_packet_dependency_graph(graph)

    assert result.accepted is False
    assert result.error_code == ErrorCode.EXECUTION_RECORD_INVALID
    assert "missing prerequisite node: wp-421-missing" in result.blocked_reasons
    write_evidence("execution/dependency-missing-node-block.json", result.to_evidence(), slice_id="l1gov-slice-004")


def test_packet_dependency_graph_rejects_cycles() -> None:
    graph = valid_dependency_graph(edges=(("wp-421-001", "wp-421-002"), ("wp-421-002", "wp-421-001")))

    result = validate_packet_dependency_graph(graph)

    assert result.accepted is False
    assert result.error_code == ErrorCode.EXECUTION_RECORD_INVALID
    assert "dependency graph contains a cycle" in result.blocked_reasons
    write_evidence("execution/dependency-graph-block.json", result.to_evidence(), slice_id="l1gov-slice-004")


def test_packet_dependency_graph_requires_repair_refs_for_blocked_edges() -> None:
    graph = valid_dependency_graph(blocked_edges=(("wp-421-001", "wp-421-002"),), repair_refs=())

    result = validate_packet_dependency_graph(graph)

    assert result.accepted is False
    assert result.error_code == ErrorCode.EXECUTION_RECORD_INVALID
    assert "blocked dependency edges require repair refs" in result.blocked_reasons
