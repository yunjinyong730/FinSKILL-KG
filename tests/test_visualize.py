from __future__ import annotations

import pandas as pd

from src.finskillkg.graph import DualKnowledgeGraph
from src.finskillkg.skills import SkillRegistry
from src.finskillkg.visualize import (
    financial_kg_dot,
    skill_detail_dot,
    skill_kg_dot,
)


def build_graph() -> tuple[DualKnowledgeGraph, SkillRegistry]:
    frame = pd.read_csv(
        "data/sample_financials.csv",
        dtype={"company_code": str, "source_id": str},
    )
    registry = SkillRegistry.load("skills")
    graph = DualKnowledgeGraph()
    graph.add_financial_data(frame)
    graph.add_skill_registry(registry)
    return graph, registry


def test_financial_kg_dot_contains_core_relations():
    graph, _ = build_graph()
    dot = financial_kg_dot(graph, "샘플전자", 2025)

    assert "HAS_FINANCIAL_FACT" in dot
    assert "OF_METRIC" in dot
    assert "FOR_PERIOD" in dot
    assert "EXTRACTED_FROM" in dot


def test_skill_kg_dot_contains_dependency_and_bridge():
    _, registry = build_graph()
    dot = skill_kg_dot(registry, "financial_summary_generation")

    assert "REQUIRES" in dot
    assert "REQUIRES_METRIC" in dot
    assert "financial_summary_generation" in dot


def test_skill_detail_dot_contains_skill_metadata_relations():
    _, registry = build_graph()
    dot = skill_detail_dot(registry, "financial_metric_calculation")

    assert "CONSUMES" in dot
    assert "PRODUCES" in dot
    assert "USES_TOOL" in dot
    assert "VALIDATED_BY" in dot
