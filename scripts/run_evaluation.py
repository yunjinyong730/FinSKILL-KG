from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.finskillkg.config import LLMConfig
from src.finskillkg.evaluation import (
    SYSTEMS,
    EvaluationRunner,
    load_evaluation_tasks,
    summarize_results,
)
from src.finskillkg.graph import DualKnowledgeGraph
from src.finskillkg.llm import LLMClient
from src.finskillkg.normalize import load_financial_csv
from src.finskillkg.skills import SkillRegistry


def main() -> None:
    parser = argparse.ArgumentParser(
        description="LLM Only vs Financial KG vs Skill KG + Financial KG 평가"
    )
    parser.add_argument("--data", default="data/dart_financials.csv")
    parser.add_argument("--dataset", default="data/evaluation_questions.jsonl")
    parser.add_argument("--skills", default="skills")
    parser.add_argument("--output", default="outputs/evaluation")
    parser.add_argument(
        "--systems",
        nargs="+",
        choices=SYSTEMS,
        default=list(SYSTEMS),
    )
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    frame = load_financial_csv(args.data)
    registry = SkillRegistry.load(args.skills)
    graph = DualKnowledgeGraph()
    graph.add_financial_data(frame)
    graph.add_skill_registry(registry)

    needs_llm = any(system != "llm_skill_financial_kg" for system in args.systems)
    llm_client = None
    if needs_llm:
        config = LLMConfig.from_env()
        llm_client = LLMClient(
            config.api_url,
            config.api_key,
            config.model,
            timeout=config.timeout,
        )

    tasks = load_evaluation_tasks(args.dataset)
    available_companies = set(graph.company_names())
    tasks = [
        task
        for task in tasks
        if set(task.companies).issubset(available_companies)
    ]
    if args.limit:
        tasks = tasks[: args.limit]
    if not tasks:
        raise RuntimeError("현재 데이터셋으로 실행 가능한 평가 task가 없습니다.")

    runner = EvaluationRunner(graph, registry, llm_client=llm_client)
    results = runner.run(tasks, systems=tuple(args.systems))
    summary = summarize_results(results)

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)

    with (output / "results.jsonl").open("w", encoding="utf-8") as handle:
        for item in results:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    summary.to_csv(output / "summary.csv", index=False)

    print(summary.to_string(index=False))
    print(f"saved: {output / 'results.jsonl'}")
    print(f"saved: {output / 'summary.csv'}")


if __name__ == "__main__":
    main()
