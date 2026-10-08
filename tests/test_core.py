from pathlib import Path

import pandas as pd

from src.finskillkg.engine import FinSkillEngine
from src.finskillkg.graph import DualKnowledgeGraph
from src.finskillkg.metrics import calculate_ratios, trend_direction
from src.finskillkg.normalize import normalize_dart_records
from src.finskillkg.pipeline import run_pipeline
from src.finskillkg.skills import SkillRegistry


def test_financial_ratio_calculation():
    facts = {
        "revenue": 100.0,
        "operating_income": 10.0,
        "net_income": 8.0,
        "assets": 200.0,
        "liabilities": 80.0,
        "equity": 120.0,
    }
    previous = {"revenue": 80.0}
    ratios = calculate_ratios(facts, previous)

    assert round(ratios["debt_ratio"], 2) == 66.67
    assert ratios["operating_margin"] == 10.0
    assert ratios["roa"] == 4.0
    assert round(ratios["roe"], 2) == 6.67
    assert ratios["revenue_growth"] == 25.0


def test_trend_direction():
    assert trend_direction([1, 2, 3]) == "상승"
    assert trend_direction([3, 2, 1]) == "하락"
    assert trend_direction([1, 2, 1]) == "혼조"


def test_skill_plan_resolves_dependencies():
    registry = SkillRegistry.load("skills")
    plan = registry.plan("financial_summary_generation")

    assert plan[-1] == "financial_summary_generation"
    assert plan.index("financial_statement_extraction") < plan.index("financial_fact_validation")
    assert plan.index("financial_metric_calculation") < plan.index("financial_trend_analysis")
    assert plan.index("financial_trend_analysis") < plan.index("financial_risk_analysis")


def test_normalize_dart_records():
    records = [
        {"sj_div": "IS", "account_nm": "매출액", "thstrm_amount": "1,000", "rcept_no": "R1"},
        {"sj_div": "IS", "account_nm": "영업이익", "thstrm_amount": "100", "rcept_no": "R1"},
        {"sj_div": "BS", "account_nm": "자산총계", "thstrm_amount": "2,000", "rcept_no": "R1"},
    ]
    frame = normalize_dart_records(records, "001", "테스트", 2025, "fallback")

    assert set(frame["metric"]) == {"revenue", "operating_income", "assets"}
    assert frame.loc[frame["metric"] == "revenue", "value"].iloc[0] == 1000.0


def test_pipeline_and_engine(tmp_path: Path):
    summary = run_pipeline(
        data_path="data/sample_financials.csv",
        skills_dir="skills",
        output_dir=tmp_path,
    )
    assert summary["companies"] == 2
    assert summary["skills"] == 7
    assert summary["bridges"] > 0
    assert summary["validation_issues"] == 0
    assert (tmp_path / "dual_kg.json").exists()
    assert (tmp_path / "validation_issues.csv").exists()

    frame = pd.read_csv("data/sample_financials.csv", dtype={"company_code": str, "source_id": str})
    registry = SkillRegistry.load("skills")
    graph = DualKnowledgeGraph()
    graph.add_financial_data(frame)
    graph.add_skill_registry(registry)
    engine = FinSkillEngine(graph, registry)

    result = engine.answer("샘플전자 최근 3년 재무상태 분석해줘")
    assert result["companies"] == ["샘플전자"]
    assert "Risk Signal" in result["answer"]
    assert len(result["evidence"]) == 3

    compare = engine.answer("샘플전자와 샘플메모리 비교해줘")
    assert compare["intent"] == "comparison"
    assert "샘플전자" in compare["answer"]
    assert "샘플메모리" in compare["answer"]
