from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.finskillkg.engine import FinSkillEngine
from src.finskillkg.graph import DualKnowledgeGraph
from src.finskillkg.ml_router import TrainedSkillRouter
from src.finskillkg.normalize import load_financial_csv
from src.finskillkg.skills import SkillRegistry


def build_engine(
    model_path: str | Path,
    data_path: str | Path,
) -> tuple[FinSkillEngine, TrainedSkillRouter]:
    frame = load_financial_csv(data_path)
    registry = SkillRegistry.load("skills")

    graph = DualKnowledgeGraph()
    graph.add_financial_data(frame)
    graph.add_skill_registry(registry)

    router = TrainedSkillRouter(model_path)
    engine = FinSkillEngine(
        graph,
        registry,
        skill_predictor=router.predict,
    )
    return engine, router


def run_question(
    question: str,
    model_path: str | Path,
    data_path: str | Path,
) -> dict:
    engine, router = build_engine(model_path, data_path)
    predicted_skill, confidence = router.predict_with_confidence(question)
    result = engine.answer(question)

    print("\n[Router]")
    print(f"skill: {predicted_skill}")
    print(f"confidence: {confidence:.4f}")

    print("\n[Answer]")
    print(result["answer"])

    print("\n[Skill Plan]")
    for index, skill_id in enumerate(result["skill_plan"], 1):
        print(f"{index}. {skill_id}")

    print("\n[Evidence]")
    if result["evidence"]:
        for item in result["evidence"]:
            print(
                f"- {item.get('source_id', '')} "
                f"{item.get('source_name', '')}"
            )
    else:
        print("- none")

    return {
        "predicted_skill": predicted_skill,
        "confidence": confidence,
        "result": result,
    }


def interactive(
    model_path: str | Path,
    data_path: str | Path,
) -> None:
    engine, router = build_engine(model_path, data_path)

    print("FinSKILL-KG EduBridge inference")
    print("종료하려면 exit 입력")

    while True:
        question = input("\n질문: ").strip()
        if question.lower() in {"exit", "quit"}:
            break
        if not question:
            continue

        predicted_skill, confidence = router.predict_with_confidence(question)
        result = engine.answer(question)

        print(f"\n[Router] {predicted_skill} ({confidence:.4f})")
        print("[Answer]")
        print(result["answer"])

        print("[Skill Plan]")
        for index, skill_id in enumerate(result["skill_plan"], 1):
            print(f"{index}. {skill_id}")

        print("[Evidence]")
        if result["evidence"]:
            for item in result["evidence"]:
                print(f"- {item.get('source_id', '')}")
        else:
            print("- none")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="FinSKILL-KG trained router inference"
    )
    parser.add_argument(
        "--model",
        default="edubridge/artifacts/skill_router.joblib",
    )
    parser.add_argument(
        "--data",
        default="data/sample_financials.csv",
    )
    parser.add_argument("--question")
    args = parser.parse_args()

    model_path = Path(args.model)
    if not model_path.exists():
        raise FileNotFoundError(
            f"학습 모델이 없습니다: {model_path}\n"
            "먼저 python edubridge/train.py 를 실행하세요."
        )

    if args.question:
        run_question(
            args.question,
            model_path,
            args.data,
        )
    else:
        interactive(model_path, args.data)


if __name__ == "__main__":
    main()
