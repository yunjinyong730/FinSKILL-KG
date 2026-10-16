from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path("edubridge/main.py")
SPEC = importlib.util.spec_from_file_location("edubridge_main", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_metric_question():
    result = MODULE.answer("샘플전자 2025년 부채비율 알려줘")

    assert result["route"]["intent"] == "metric"
    assert "55.84%" in result["answer"]
    assert result["sources"] == ["DEMO001-2025"]


def test_trend_question():
    result = MODULE.answer("샘플전자 2023~2025년 매출 추세 알려줘")

    assert result["route"]["intent"] == "trend"
    assert "상승" in result["answer"]
    assert len(result["sources"]) == 3


def test_comparison_question():
    result = MODULE.answer("샘플전자와 샘플메모리 ROE 비교해줘")

    assert result["route"]["intent"] == "comparison"
    assert "샘플전자" in result["answer"]
    assert "샘플메모리" in result["answer"]


def test_summary_skill_plan():
    plan = MODULE.resolve_plan("financial_summary_generation")

    assert plan[0] == "financial_statement_extraction"
    assert plan[-1] == "financial_summary_generation"
