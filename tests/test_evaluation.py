from __future__ import annotations

import pandas as pd

from src.finskillkg.cohort import load_dart_cohort
from src.finskillkg.evaluation import (
    SYSTEM_FULL,
    EvaluationRunner,
    EvaluationTask,
    load_evaluation_tasks,
    resolve_expected,
    score_prediction,
)
from src.finskillkg.graph import DualKnowledgeGraph
from src.finskillkg.skills import SkillRegistry


def build_sample_graph() -> tuple[DualKnowledgeGraph, SkillRegistry]:
    frame = pd.read_csv(
        "data/sample_financials.csv",
        dtype={"company_code": str, "source_id": str},
    )
    registry = SkillRegistry.load("skills")
    graph = DualKnowledgeGraph()
    graph.add_financial_data(frame)
    graph.add_skill_registry(registry)
    return graph, registry


def test_dart_cohort_has_15_companies():
    cohort = load_dart_cohort()

    assert len(cohort.companies) == 15
    assert cohort.years == (2023, 2024, 2025)
    assert len({company.name for company in cohort.companies}) == 15


def test_evaluation_dataset_matches_cohort():
    cohort = load_dart_cohort()
    tasks = load_evaluation_tasks("data/evaluation_questions.jsonl")
    company_names = {company.name for company in cohort.companies}

    assert len(tasks) == 36
    assert {task.task_type for task in tasks} == {"metric", "trend", "comparison"}
    assert all(set(task.companies).issubset(company_names) for task in tasks)


def test_expected_metric_and_scoring():
    graph, _ = build_sample_graph()
    task = EvaluationTask(
        task_id="sample",
        question="샘플전자 부채비율 알려줘",
        companies=("샘플전자",),
        task_type="metric",
        metric="debt_ratio",
        target_skill="financial_metric_calculation",
    )

    expected = resolve_expected(task, graph)
    value = expected["values"]["value"]
    prediction = {
        "target_skill": "financial_metric_calculation",
        "values": {"value": value},
        "source_ids": expected["source_ids"],
    }
    score = score_prediction(task, expected, prediction)

    assert round(value, 2) == 55.84
    assert score["numeric_accuracy"] == 1.0
    assert score["evidence_f1"] == 1.0
    assert score["skill_accuracy"] == 1.0
    assert score["unsupported_rate"] == 0.0


def test_full_system_evaluation_runs_without_llm():
    graph, registry = build_sample_graph()
    task = EvaluationTask(
        task_id="sample",
        question="샘플전자 부채비율 알려줘",
        companies=("샘플전자",),
        task_type="metric",
        metric="debt_ratio",
        target_skill="financial_metric_calculation",
    )

    result = EvaluationRunner(graph, registry).run_task(task, SYSTEM_FULL)

    assert result["numeric_accuracy"] == 1.0
    assert result["evidence_f1"] == 1.0
    assert result["skill_accuracy"] == 1.0
    assert result["error"] is None
