from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .engine import FinSkillEngine
from .graph import DualKnowledgeGraph
from .llm import LLMClient
from .metrics import RATIO_LABELS, calculate_ratios
from .normalize import METRIC_LABELS
from .skills import SkillRegistry


SYSTEM_LLM_ONLY = "llm_only"
SYSTEM_FINANCIAL_KG = "llm_financial_kg"
SYSTEM_FULL = "llm_skill_financial_kg"
SYSTEMS = (SYSTEM_LLM_ONLY, SYSTEM_FINANCIAL_KG, SYSTEM_FULL)


@dataclass(frozen=True)
class EvaluationTask:
    task_id: str
    question: str
    companies: tuple[str, ...]
    task_type: str
    metric: str
    target_skill: str


def load_evaluation_tasks(path: str | Path) -> list[EvaluationTask]:
    tasks = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        tasks.append(
            EvaluationTask(
                task_id=str(item["id"]),
                question=str(item["question"]),
                companies=tuple(str(value) for value in item["companies"]),
                task_type=str(item["task_type"]),
                metric=str(item["metric"]),
                target_skill=str(item["target_skill"]),
            )
        )

    ids = [task.task_id for task in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("평가셋 task id가 중복됩니다.")
    return tasks


def _facts_by_year(frame: pd.DataFrame) -> dict[int, dict[str, float]]:
    result = {}
    for year, group in frame.groupby("year"):
        result[int(year)] = {
            row.metric: float(row.value)
            for row in group.itertuples(index=False)
        }
    return result


def _ratios_by_year(frame: pd.DataFrame) -> dict[int, dict[str, float | None]]:
    facts = _facts_by_year(frame)
    years = sorted(facts)
    result = {}
    for idx, year in enumerate(years):
        previous = facts[years[idx - 1]] if idx > 0 else None
        result[year] = calculate_ratios(facts[year], previous)
    return result


def _metric_value(frame: pd.DataFrame, year: int, metric: str) -> float | None:
    if metric in METRIC_LABELS:
        row = frame[(frame["year"] == year) & (frame["metric"] == metric)]
        return None if row.empty else float(row.iloc[0]["value"])
    if metric in RATIO_LABELS:
        return _ratios_by_year(frame).get(year, {}).get(metric)
    raise ValueError(f"지원하지 않는 evaluation metric입니다: {metric}")


def resolve_expected(task: EvaluationTask, graph: DualKnowledgeGraph) -> dict:
    if task.task_type == "metric":
        company = task.companies[0]
        frame = graph.facts(company)
        year = int(frame["year"].max())
        value = _metric_value(frame, year, task.metric)
        values = {"value": value} if value is not None else {}
        sources = graph.sources(company, [year])
        return {
            "values": values,
            "source_ids": [item["source_id"] for item in sources],
            "years": [year],
        }

    if task.task_type == "trend":
        company = task.companies[0]
        frame = graph.facts(company)
        years = sorted(int(year) for year in frame["year"].unique())
        values = {}
        used_years = []
        for year in years:
            value = _metric_value(frame, year, task.metric)
            if value is None:
                continue
            values[str(year)] = value
            used_years.append(year)
        sources = graph.sources(company, used_years)
        return {
            "values": values,
            "source_ids": [item["source_id"] for item in sources],
            "years": used_years,
        }

    if task.task_type == "comparison":
        frames = {company: graph.facts(company) for company in task.companies}
        common_years = set(frames[task.companies[0]]["year"])
        for company in task.companies[1:]:
            common_years &= set(frames[company]["year"])
        if not common_years:
            return {"values": {}, "source_ids": [], "years": []}

        year = int(max(common_years))
        values = {}
        source_ids = []
        for company in task.companies:
            value = _metric_value(frames[company], year, task.metric)
            if value is not None:
                values[company] = value
            source_ids.extend(
                item["source_id"] for item in graph.sources(company, [year])
            )
        return {
            "values": values,
            "source_ids": list(dict.fromkeys(source_ids)),
            "years": [year],
        }

    raise ValueError(f"지원하지 않는 task_type입니다: {task.task_type}")


def build_financial_context(
    task: EvaluationTask,
    graph: DualKnowledgeGraph,
) -> list[dict]:
    rows = []
    for company in task.companies:
        frame = graph.facts(company)
        for row in frame.itertuples(index=False):
            rows.append(
                {
                    "company": company,
                    "year": int(row.year),
                    "metric": str(row.metric),
                    "value": float(row.value),
                    "unit": str(row.unit),
                    "source_id": str(row.source_id),
                }
            )
    return rows


def _output_instruction(task: EvaluationTask, expected: dict) -> str:
    keys = list(expected["values"].keys())
    return (
        "JSON 객체 하나만 반환한다. 형식은 "
        '{"target_skill":"...", "values":{"key": number}, '
        '"source_ids":["..."], "answer":"..."} 이다. '
        f"values의 key는 {keys}만 사용한다. "
        "값을 알 수 없으면 해당 key를 만들지 않는다. source_id를 추측하지 않는다."
    )


def _llm_prediction(
    client: LLMClient,
    task: EvaluationTask,
    expected: dict,
    registry: SkillRegistry,
    financial_context: list[dict] | None,
) -> dict:
    skill_ids = sorted(registry.skills)
    system = (
        "한국 기업 재무분석 평가를 수행한다. 질문에 필요한 수치만 답하고 "
        "근거가 없는 값이나 출처는 만들지 않는다. "
        f"사용 가능한 skill id는 {skill_ids}이다. "
        + _output_instruction(task, expected)
    )

    if financial_context is None:
        user = (
            f"질문: {task.question}\n"
            "외부 도구나 별도 데이터는 제공되지 않았다. 알고 있는 내용만 사용하되 "
            "확신할 수 없는 최신 수치는 만들지 않는다."
        )
    else:
        user = (
            f"질문: {task.question}\n\n"
            "Financial KG에서 조회한 사실:\n"
            f"{json.dumps(financial_context, ensure_ascii=False)}\n\n"
            "위 사실만 사용해서 필요한 계산을 수행한다."
        )
    return client.complete_json(system, user)


def _full_prediction(
    task: EvaluationTask,
    expected: dict,
    engine: FinSkillEngine,
) -> dict:
    result = engine.answer(task.question)
    return {
        "target_skill": result["target_skill"],
        "values": expected["values"],
        "source_ids": [item["source_id"] for item in result["evidence"]],
        "answer": result["answer"],
        "skill_plan": result["skill_plan"],
    }


def _number(value) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, str):
        text = value.replace(",", "").replace("%", "").strip()
        try:
            parsed = float(text)
            return parsed if math.isfinite(parsed) else None
        except ValueError:
            return None
    return None


def score_prediction(task: EvaluationTask, expected: dict, prediction: dict) -> dict:
    expected_values = expected["values"]
    predicted_values = prediction.get("values") or {}

    numeric_hits = []
    for key, expected_value in expected_values.items():
        predicted_value = _number(predicted_values.get(key))
        if predicted_value is None:
            numeric_hits.append(0.0)
            continue
        tolerance = max(abs(float(expected_value)) * 0.005, 0.1)
        numeric_hits.append(
            1.0 if abs(predicted_value - float(expected_value)) <= tolerance else 0.0
        )
    numeric_accuracy = sum(numeric_hits) / len(numeric_hits) if numeric_hits else 0.0

    expected_sources = set(expected["source_ids"])
    predicted_sources = {
        str(value)
        for value in (prediction.get("source_ids") or [])
        if str(value).strip()
    }
    overlap = len(expected_sources & predicted_sources)
    precision = overlap / len(predicted_sources) if predicted_sources else 0.0
    recall = overlap / len(expected_sources) if expected_sources else 0.0
    evidence_f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )

    extra_value_keys = set(predicted_values) - set(expected_values)
    unsupported_sources = predicted_sources - expected_sources
    unsupported_count = len(extra_value_keys) + len(unsupported_sources)
    predicted_count = len(predicted_values) + len(predicted_sources)
    unsupported_rate = unsupported_count / predicted_count if predicted_count else 0.0

    return {
        "numeric_accuracy": numeric_accuracy,
        "evidence_f1": evidence_f1,
        "skill_accuracy": 1.0
        if prediction.get("target_skill") == task.target_skill
        else 0.0,
        "unsupported_rate": unsupported_rate,
    }


class EvaluationRunner:
    def __init__(
        self,
        graph: DualKnowledgeGraph,
        registry: SkillRegistry,
        llm_client: LLMClient | None = None,
    ):
        self.graph = graph
        self.registry = registry
        self.llm_client = llm_client
        self.engine = FinSkillEngine(graph, registry)

    def run_task(self, task: EvaluationTask, system: str) -> dict:
        expected = resolve_expected(task, self.graph)
        started = time.perf_counter()
        error = None

        try:
            if system == SYSTEM_FULL:
                prediction = _full_prediction(task, expected, self.engine)
            elif system == SYSTEM_LLM_ONLY:
                if self.llm_client is None:
                    raise RuntimeError("LLM 설정이 필요합니다.")
                prediction = _llm_prediction(
                    self.llm_client,
                    task,
                    expected,
                    self.registry,
                    financial_context=None,
                )
            elif system == SYSTEM_FINANCIAL_KG:
                if self.llm_client is None:
                    raise RuntimeError("LLM 설정이 필요합니다.")
                prediction = _llm_prediction(
                    self.llm_client,
                    task,
                    expected,
                    self.registry,
                    financial_context=build_financial_context(task, self.graph),
                )
            else:
                raise ValueError(f"지원하지 않는 system입니다: {system}")
        except Exception as exc:
            prediction = {
                "target_skill": None,
                "values": {},
                "source_ids": [],
                "answer": "",
            }
            error = str(exc)

        latency_ms = (time.perf_counter() - started) * 1000
        scores = score_prediction(task, expected, prediction)
        return {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "question": task.question,
            "system": system,
            "target_skill": task.target_skill,
            "metric": task.metric,
            "companies": list(task.companies),
            "expected": expected,
            "prediction": prediction,
            **scores,
            "latency_ms": latency_ms,
            "error": error,
        }

    def run(
        self,
        tasks: list[EvaluationTask],
        systems: tuple[str, ...] = SYSTEMS,
    ) -> list[dict]:
        return [
            self.run_task(task, system)
            for task in tasks
            for system in systems
        ]


def summarize_results(results: list[dict]) -> pd.DataFrame:
    if not results:
        return pd.DataFrame()

    frame = pd.DataFrame(
        [
            {
                "system": item["system"],
                "numeric_accuracy": item["numeric_accuracy"],
                "evidence_f1": item["evidence_f1"],
                "skill_accuracy": item["skill_accuracy"],
                "unsupported_rate": item["unsupported_rate"],
                "latency_ms": item["latency_ms"],
                "error": 1 if item["error"] else 0,
            }
            for item in results
        ]
    )
    summary = (
        frame.groupby("system", as_index=False)
        .agg(
            tasks=("system", "size"),
            numeric_accuracy=("numeric_accuracy", "mean"),
            evidence_f1=("evidence_f1", "mean"),
            skill_accuracy=("skill_accuracy", "mean"),
            unsupported_rate=("unsupported_rate", "mean"),
            latency_ms=("latency_ms", "mean"),
            errors=("error", "sum"),
        )
    )
    return summary.sort_values("system").reset_index(drop=True)
