from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from src.finskillkg.engine import FinSkillEngine
from src.finskillkg.graph import DualKnowledgeGraph
from src.finskillkg.ml_router import TrainedSkillRouter
from src.finskillkg.normalize import load_financial_csv
from src.finskillkg.skills import SkillRegistry


TRAIN_PATH = Path("edubridge/train.py")
SPEC = importlib.util.spec_from_file_location("edubridge_train", TRAIN_PATH)
TRAIN = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = TRAIN
SPEC.loader.exec_module(TRAIN)


def test_training_dataset_has_five_balanced_classes():
    rows = TRAIN.build_split(
        TRAIN.TRAIN_TEMPLATES,
        samples_per_class=10,
        seed=42,
        wrappers=TRAIN.TRAIN_WRAPPERS,
    )

    labels = [row["label"] for row in rows]

    assert len(rows) == 50
    assert set(labels) == {
        "financial_metric_calculation",
        "financial_trend_analysis",
        "financial_risk_analysis",
        "company_comparison",
        "financial_summary_generation",
    }
    assert all(labels.count(label) == 10 for label in set(labels))


def test_router_training_and_inference(tmp_path):
    metrics = TRAIN.train_router(
        output_dir=tmp_path,
        epochs=3,
        train_samples_per_class=20,
        valid_samples_per_class=10,
        test_samples_per_class=10,
        seed=42,
    )

    model_path = tmp_path / "skill_router.joblib"
    router = TrainedSkillRouter(model_path)

    assert model_path.exists()
    assert metrics["test_accuracy"] >= 0.70
    assert router.predict("삼성전자 2025년 부채비율 알려줘") == (
        "financial_metric_calculation"
    )
    assert router.predict("삼성전자 재무상태 전체적으로 정리해줘") == (
        "financial_summary_generation"
    )


def test_trained_router_controls_engine(tmp_path):
    TRAIN.train_router(
        output_dir=tmp_path,
        epochs=3,
        train_samples_per_class=20,
        valid_samples_per_class=10,
        test_samples_per_class=10,
        seed=42,
    )

    frame = load_financial_csv("data/sample_financials.csv")
    registry = SkillRegistry.load("skills")
    graph = DualKnowledgeGraph()
    graph.add_financial_data(frame)
    graph.add_skill_registry(registry)

    router = TrainedSkillRouter(tmp_path / "skill_router.joblib")
    engine = FinSkillEngine(
        graph,
        registry,
        skill_predictor=router.predict,
    )

    result = engine.answer("샘플전자 최근 재무상태 전체적으로 정리해줘")

    assert result["target_skill"] == "financial_summary_generation"
    assert result["skill_plan"][-1] == "financial_summary_generation"


def test_large_dataset_capacity_and_split_overlap():
    train_rows = TRAIN.build_split(
        TRAIN.TRAIN_TEMPLATES,
        samples_per_class=2000,
        seed=42,
        wrappers=TRAIN.TRAIN_WRAPPERS,
    )
    valid_rows = TRAIN.build_split(
        TRAIN.VALID_TEMPLATES,
        samples_per_class=400,
        seed=43,
        wrappers=TRAIN.VALID_WRAPPERS,
    )
    test_rows = TRAIN.build_split(
        TRAIN.TEST_TEMPLATES,
        samples_per_class=400,
        seed=44,
        wrappers=TRAIN.TEST_WRAPPERS,
    )

    manifest = TRAIN.dataset_manifest(
        train_rows,
        valid_rows,
        test_rows,
    )

    assert manifest["total"] == 14000
    assert manifest["splits"]["train"]["rows"] == 10000
    assert manifest["splits"]["valid"]["rows"] == 2000
    assert manifest["splits"]["test"]["rows"] == 2000
    assert manifest["overlap"] == {
        "train_valid": 0,
        "train_test": 0,
        "valid_test": 0,
    }
