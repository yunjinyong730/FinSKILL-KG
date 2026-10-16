from __future__ import annotations

import argparse
import copy
import csv
import json
import random
from pathlib import Path

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
)


RANDOM_SEED = 42

COMPANIES = [
    "삼성전자",
    "SK하이닉스",
    "현대자동차",
    "기아",
    "현대모비스",
    "NAVER",
    "카카오",
    "LG전자",
    "LG에너지솔루션",
    "삼성SDI",
    "POSCO홀딩스",
    "셀트리온",
    "삼성바이오로직스",
    "SK텔레콤",
    "KT",
]

METRICS = [
    "부채비율",
    "영업이익률",
    "ROA",
    "ROE",
    "매출",
    "영업이익",
]

YEARS = ["2023", "2024", "2025"]

TRAIN_TEMPLATES = {
    "financial_metric_calculation": [
        "{company} {year}년 {metric} 알려줘",
        "{company}의 {year}년 {metric} 계산해줘",
        "{company} {metric} 얼마야",
        "{year}년 {company} {metric} 확인해줘",
        "{company} 기준 {metric} 값 알려줘",
        "{company} {metric} 수치가 어떻게 돼",
    ],
    "financial_trend_analysis": [
        "{company} {start}~{end}년 {metric} 추세 알려줘",
        "{company} 최근 {metric} 변화 보여줘",
        "{company} {metric}이 최근 어떻게 변했어",
        "{company} {start}년부터 {end}년까지 {metric} 흐름 정리해줘",
        "{company} {metric} 증가 추세인지 봐줘",
        "{company} 최근 3년 {metric} 변화를 알려줘",
    ],
    "financial_risk_analysis": [
        "{company} 재무 위험 분석해줘",
        "{company} 재무 리스크 봐줘",
        "{company} 재무 안정성 어때",
        "{company} 부채와 수익성 기준으로 위험한지 알려줘",
        "{company} 건전성 점검해줘",
        "{company} 최근 재무 위험 신호가 있어",
    ],
    "company_comparison": [
        "{company}와 {company2} {metric} 비교해줘",
        "{company} vs {company2} {metric} 비교",
        "{company}하고 {company2} 중 {metric}이 더 나은 곳은 어디야",
        "{year}년 {company}와 {company2} {metric} 대비해줘",
        "{company} {company2} 두 회사의 {metric} 차이 알려줘",
        "{company}와 {company2} 재무비율 비교해줘",
    ],
    "financial_summary_generation": [
        "{company} 재무상태 요약해줘",
        "{company} 최근 재무상태 전체 분석해줘",
        "{company} 재무 상황 한 번에 정리해줘",
        "{company} 최근 실적이랑 재무비율 같이 봐줘",
        "{company} 재무 요약해줘",
        "{company} 전체 재무 분석 부탁해",
    ],
}

VALID_TEMPLATES = {
    "financial_metric_calculation": [
        "{company}의 {metric} 수치 확인",
        "{year}년 기준 {company} {metric}은 얼마인지 알려줘",
    ],
    "financial_trend_analysis": [
        "{company}의 {metric}이 몇 년간 어떻게 움직였는지 알려줘",
        "{start}~{end}년 {company} {metric} 변화 정리",
    ],
    "financial_risk_analysis": [
        "{company} 재무적으로 위험한 편이야",
        "{company} 재무 건전성 체크",
    ],
    "company_comparison": [
        "{company}와 {company2}의 {metric} 차이를 비교",
        "{company} 대비 {company2} {metric} 수준 알려줘",
    ],
    "financial_summary_generation": [
        "{company} 재무상태를 전체적으로 설명해줘",
        "{company} 최근 재무 정보 요약",
    ],
}

TEST_TEMPLATES = {
    "financial_metric_calculation": [
        "{company} {metric} 숫자만 확인해줘",
        "{company}의 {year}년 {metric} 값이 궁금해",
    ],
    "financial_trend_analysis": [
        "{company} {metric} 흐름이 좋아지고 있는지 알려줘",
        "{company} {metric} 장기 변화 확인해줘",
    ],
    "financial_risk_analysis": [
        "{company} 재무 위험도가 어느 정도야",
        "{company} 수익성과 부채 기준 리스크 분석",
    ],
    "company_comparison": [
        "{company}와 {company2} 중 {metric} 기준으로 비교해줘",
        "{company} {company2} 둘의 재무 수준을 비교해줘",
    ],
    "financial_summary_generation": [
        "{company} 재무를 전체적으로 정리해줘",
        "{company} 재무상태 한 번에 설명",
    ],
}


def _fill_template(template: str, index: int) -> str:
    company = COMPANIES[index % len(COMPANIES)]
    company2 = COMPANIES[(index * 3 + 4) % len(COMPANIES)]
    if company2 == company:
        company2 = COMPANIES[(index + 1) % len(COMPANIES)]

    metric = METRICS[(index * 5 + 1) % len(METRICS)]
    year = YEARS[index % len(YEARS)]
    start = YEARS[0]
    end = YEARS[-1]

    return template.format(
        company=company,
        company2=company2,
        metric=metric,
        year=year,
        start=start,
        end=end,
    )


def build_split(
    templates: dict[str, list[str]],
    samples_per_class: int,
    seed: int,
) -> list[dict]:
    rng = random.Random(seed)
    rows = []

    for label, label_templates in templates.items():
        candidates = []
        cycle = max(samples_per_class * 3, 200)

        for index in range(cycle):
            template = label_templates[index % len(label_templates)]
            candidates.append(
                {
                    "question": _fill_template(template, index),
                    "label": label,
                }
            )

        unique = {
            (row["question"], row["label"]): row
            for row in candidates
        }
        items = list(unique.values())
        rng.shuffle(items)

        if len(items) < samples_per_class:
            raise RuntimeError(
                f"{label} 샘플 수가 부족합니다: "
                f"required={samples_per_class}, available={len(items)}"
            )
        rows.extend(items[:samples_per_class])

    rng.shuffle(rows)
    return rows


def save_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["question", "label"])
        writer.writeheader()
        writer.writerows(rows)


def evaluate(
    vectorizer: TfidfVectorizer,
    classifier: SGDClassifier,
    rows: list[dict],
) -> dict:
    questions = [row["question"] for row in rows]
    labels = [row["label"] for row in rows]

    features = vectorizer.transform(questions)
    predictions = classifier.predict(features)

    return {
        "accuracy": float(accuracy_score(labels, predictions)),
        "macro_f1": float(f1_score(labels, predictions, average="macro")),
        "report": classification_report(
            labels,
            predictions,
            output_dict=True,
            zero_division=0,
        ),
        "labels": labels,
        "predictions": predictions.tolist(),
    }


def train_router(
    output_dir: str | Path = "edubridge/artifacts",
    epochs: int = 20,
    train_samples_per_class: int = 180,
    valid_samples_per_class: int = 50,
    test_samples_per_class: int = 50,
    seed: int = RANDOM_SEED,
) -> dict:
    output = Path(output_dir)
    dataset_dir = output / "dataset"
    output.mkdir(parents=True, exist_ok=True)

    train_rows = build_split(
        TRAIN_TEMPLATES,
        train_samples_per_class,
        seed,
    )
    valid_rows = build_split(
        VALID_TEMPLATES,
        valid_samples_per_class,
        seed + 1,
    )
    test_rows = build_split(
        TEST_TEMPLATES,
        test_samples_per_class,
        seed + 2,
    )

    save_rows(dataset_dir / "train.csv", train_rows)
    save_rows(dataset_dir / "valid.csv", valid_rows)
    save_rows(dataset_dir / "test.csv", test_rows)

    train_questions = [row["question"] for row in train_rows]
    train_labels = [row["label"] for row in train_rows]
    valid_questions = [row["question"] for row in valid_rows]
    valid_labels = [row["label"] for row in valid_rows]

    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 5),
        min_df=1,
        max_features=12000,
        sublinear_tf=True,
    )
    train_x = vectorizer.fit_transform(train_questions)
    valid_x = vectorizer.transform(valid_questions)

    classes = np.array(sorted(set(train_labels)))
    classifier = SGDClassifier(
        loss="log_loss",
        alpha=1e-5,
        random_state=seed,
        learning_rate="optimal",
        average=True,
    )

    rng = np.random.default_rng(seed)
    history = []
    best_classifier = None
    best_valid_f1 = -1.0

    train_y = np.array(train_labels)
    valid_y = np.array(valid_labels)

    for epoch in range(1, epochs + 1):
        indices = rng.permutation(len(train_y))
        epoch_x = train_x[indices]
        epoch_y = train_y[indices]

        if epoch == 1:
            classifier.partial_fit(epoch_x, epoch_y, classes=classes)
        else:
            classifier.partial_fit(epoch_x, epoch_y)

        train_pred = classifier.predict(train_x)
        valid_pred = classifier.predict(valid_x)
        valid_prob = classifier.predict_proba(valid_x)

        train_acc = accuracy_score(train_y, train_pred)
        valid_acc = accuracy_score(valid_y, valid_pred)
        valid_f1 = f1_score(valid_y, valid_pred, average="macro")
        valid_loss = log_loss(valid_y, valid_prob, labels=classes)

        history.append(
            {
                "epoch": epoch,
                "train_accuracy": float(train_acc),
                "valid_accuracy": float(valid_acc),
                "valid_macro_f1": float(valid_f1),
                "valid_log_loss": float(valid_loss),
            }
        )

        print(
            f"epoch={epoch:02d} "
            f"train_acc={train_acc:.4f} "
            f"valid_acc={valid_acc:.4f} "
            f"valid_f1={valid_f1:.4f} "
            f"valid_loss={valid_loss:.4f}"
        )

        if valid_f1 > best_valid_f1:
            best_valid_f1 = float(valid_f1)
            best_classifier = copy.deepcopy(classifier)

    if best_classifier is None:
        raise RuntimeError("학습된 router model이 없습니다.")

    test_result = evaluate(vectorizer, best_classifier, test_rows)

    model_path = output / "skill_router.joblib"
    joblib.dump(
        {
            "vectorizer": vectorizer,
            "classifier": best_classifier,
            "classes": classes.tolist(),
            "version": 1,
        },
        model_path,
    )

    with (output / "history.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "epoch",
                "train_accuracy",
                "valid_accuracy",
                "valid_macro_f1",
                "valid_log_loss",
            ],
        )
        writer.writeheader()
        writer.writerows(history)

    matrix = confusion_matrix(
        test_result["labels"],
        test_result["predictions"],
        labels=classes,
    )
    with (output / "confusion_matrix.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(["actual/predicted", *classes])
        for label, row in zip(classes, matrix):
            writer.writerow([label, *row.tolist()])

    metrics = {
        "seed": seed,
        "epochs": epochs,
        "classes": classes.tolist(),
        "dataset": {
            "train": len(train_rows),
            "valid": len(valid_rows),
            "test": len(test_rows),
        },
        "best_valid_macro_f1": best_valid_f1,
        "test_accuracy": test_result["accuracy"],
        "test_macro_f1": test_result["macro_f1"],
        "classification_report": test_result["report"],
        "model_path": str(model_path),
    }

    (output / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\nTraining complete")
    print(f"test_accuracy={metrics['test_accuracy']:.4f}")
    print(f"test_macro_f1={metrics['test_macro_f1']:.4f}")
    print(f"model={model_path}")

    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(
        description="FinSKILL-KG Skill Router training"
    )
    parser.add_argument(
        "--output-dir",
        default="edubridge/artifacts",
    )
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--train-samples-per-class", type=int, default=180)
    parser.add_argument("--valid-samples-per-class", type=int, default=50)
    parser.add_argument("--test-samples-per-class", type=int, default=50)
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    args = parser.parse_args()

    train_router(
        output_dir=args.output_dir,
        epochs=args.epochs,
        train_samples_per_class=args.train_samples_per_class,
        valid_samples_per_class=args.valid_samples_per_class,
        test_samples_per_class=args.test_samples_per_class,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
