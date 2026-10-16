from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


DATA_PATH = Path(__file__).with_name("sample_financials.csv")

METRIC_LABELS = {
    "revenue": "매출",
    "operating_income": "영업이익",
    "net_income": "당기순이익",
    "assets": "자산",
    "liabilities": "부채",
    "equity": "자본",
    "debt_ratio": "부채비율",
    "operating_margin": "영업이익률",
    "roa": "ROA",
    "roe": "ROE",
}

METRIC_KEYWORDS = {
    "부채비율": "debt_ratio",
    "영업이익률": "operating_margin",
    "ROA": "roa",
    "roa": "roa",
    "ROE": "roe",
    "roe": "roe",
    "매출": "revenue",
    "영업이익": "operating_income",
    "순이익": "net_income",
    "자산": "assets",
    "부채": "liabilities",
    "자본": "equity",
}

SKILLS = {
    "financial_statement_extraction": {
        "name": "재무정보 추출",
        "requires": [],
    },
    "financial_fact_validation": {
        "name": "재무정보 검증",
        "requires": ["financial_statement_extraction"],
    },
    "financial_metric_calculation": {
        "name": "재무비율 계산",
        "requires": ["financial_fact_validation"],
    },
    "financial_trend_analysis": {
        "name": "추세 분석",
        "requires": ["financial_metric_calculation"],
    },
    "financial_risk_analysis": {
        "name": "Risk Signal",
        "requires": ["financial_metric_calculation", "financial_trend_analysis"],
    },
    "company_comparison": {
        "name": "기업 비교",
        "requires": ["financial_metric_calculation"],
    },
    "financial_summary_generation": {
        "name": "재무 요약",
        "requires": [
            "financial_metric_calculation",
            "financial_trend_analysis",
            "financial_risk_analysis",
        ],
    },
}


def load_data() -> dict:
    data: dict[str, dict[int, dict]] = {}
    with DATA_PATH.open("r", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            company = row["company_name"]
            year = int(row["year"])
            facts = data.setdefault(company, {}).setdefault(
                year,
                {"source_id": row["source_id"]},
            )
            facts[row["metric"]] = float(row["value"])
    return data


DATA = load_data()


def safe_ratio(a: float | None, b: float | None) -> float | None:
    if a is None or b in (None, 0):
        return None
    return a / b * 100


def metric_value(facts: dict, metric: str) -> float | None:
    if metric in facts:
        return facts[metric]
    if metric == "debt_ratio":
        return safe_ratio(facts.get("liabilities"), facts.get("equity"))
    if metric == "operating_margin":
        return safe_ratio(facts.get("operating_income"), facts.get("revenue"))
    if metric == "roa":
        return safe_ratio(facts.get("net_income"), facts.get("assets"))
    if metric == "roe":
        return safe_ratio(facts.get("net_income"), facts.get("equity"))
    return None


def format_value(metric: str, value: float | None) -> str:
    if value is None:
        return "N/A"
    if metric in {"debt_ratio", "operating_margin", "roa", "roe"}:
        return f"{value:.2f}%"
    return f"{value / 1_000_000_000_000:,.2f}조원"


def resolve_plan(skill_id: str) -> list[str]:
    plan: list[str] = []

    def visit(current: str) -> None:
        if current in plan:
            return
        for dependency in SKILLS[current]["requires"]:
            visit(dependency)
        plan.append(current)

    visit(skill_id)
    return plan


def parse_query(query: str) -> dict:
    companies = [name for name in DATA if name in query]
    if not companies:
        companies = [next(iter(DATA))]

    years = [int(value) for value in re.findall(r"20\d{2}", query)]
    metric = next(
        (metric for keyword, metric in METRIC_KEYWORDS.items() if keyword in query),
        None,
    )

    if any(word in query.lower() for word in ["비교", "vs", "대비"]):
        intent, skill = "comparison", "company_comparison"
    elif any(word in query for word in ["추세", "변화", "증가", "감소"]):
        intent, skill = "trend", "financial_trend_analysis"
    elif any(word in query for word in ["위험", "리스크", "risk"]):
        intent, skill = "risk", "financial_risk_analysis"
    elif any(word in query for word in ["분석", "요약", "재무상태"]):
        intent, skill = "summary", "financial_summary_generation"
    else:
        intent, skill = "metric", "financial_metric_calculation"

    return {
        "intent": intent,
        "skill": skill,
        "companies": companies,
        "years": years,
        "metric": metric,
        "plan": resolve_plan(skill),
    }


def select_year(company: str, years: list[int]) -> int:
    available = sorted(DATA[company])
    year = years[-1] if years else available[-1]
    if year not in DATA[company]:
        raise ValueError(
            f"{company} {year}년 데이터가 없습니다. "
            f"사용 가능: {', '.join(map(str, available))}"
        )
    return year


def trend(values: list[float]) -> str:
    if len(values) < 2:
        return "판단불가"
    if all(a < b for a, b in zip(values, values[1:])):
        return "상승"
    if all(a > b for a, b in zip(values, values[1:])):
        return "하락"
    return "혼조"


def answer(query: str) -> dict:
    route = parse_query(query)
    intent = route["intent"]
    companies = route["companies"]
    metric = route["metric"]

    if intent == "comparison":
        if len(companies) < 2:
            companies = list(DATA)[:2]
        common = sorted(set(DATA[companies[0]]) & set(DATA[companies[1]]))
        year = route["years"][-1] if route["years"] else common[-1]
        metric = metric or "roe"
        lines = [f"{year}년 기준 {METRIC_LABELS[metric]} 비교입니다."]
        sources = []
        for company in companies[:2]:
            facts = DATA[company][year]
            lines.append(
                f"- {company}: {format_value(metric, metric_value(facts, metric))}"
            )
            sources.append(facts["source_id"])
        text = "\n".join(lines)

    elif intent == "trend":
        company = companies[0]
        metric = metric or "revenue"
        years = sorted(DATA[company])
        if len(route["years"]) >= 2:
            start, end = route["years"][0], route["years"][-1]
            years = [year for year in years if start <= year <= end]

        values, sources, rows = [], [], []
        for year in years:
            facts = DATA[company][year]
            value = metric_value(facts, metric)
            if value is None:
                continue
            values.append(value)
            sources.append(facts["source_id"])
            rows.append(f"- {year}: {format_value(metric, value)}")

        text = "\n".join(
            [
                f"{company}의 {years[0]}~{years[-1]}년 "
                f"{METRIC_LABELS[metric]} 추세는 {trend(values)}입니다.",
                *rows,
            ]
        )

    else:
        company = companies[0]
        year = select_year(company, route["years"])
        facts = DATA[company][year]
        sources = [facts["source_id"]]

        if intent == "risk":
            debt = metric_value(facts, "debt_ratio") or 0
            margin = metric_value(facts, "operating_margin") or 0
            score = 2 if debt >= 200 else 1 if debt >= 100 else 0
            score += 2 if margin < 0 else 1 if margin < 5 else 0
            level = "HIGH" if score >= 4 else "MEDIUM" if score >= 2 else "LOW"
            text = (
                f"{company} {year}년 Risk Signal은 {level}입니다.\n"
                "- 프로젝트용 단순 규칙이며 투자등급이나 신용등급이 아닙니다."
            )

        elif intent == "summary":
            text = "\n".join(
                [
                    f"{company} {year}년 재무 요약입니다.",
                    f"- 매출: {format_value('revenue', facts.get('revenue'))}",
                    f"- 영업이익률: {format_value('operating_margin', metric_value(facts, 'operating_margin'))}",
                    f"- 부채비율: {format_value('debt_ratio', metric_value(facts, 'debt_ratio'))}",
                    f"- ROE: {format_value('roe', metric_value(facts, 'roe'))}",
                ]
            )

        else:
            metric = metric or "debt_ratio"
            value = metric_value(facts, metric)
            text = (
                f"{company}의 {year}년 {METRIC_LABELS[metric]}은 "
                f"{format_value(metric, value)}입니다."
            )

    return {"answer": text, "sources": sources, "route": route}


def print_result(query: str) -> None:
    result = answer(query)
    print("\n[질문]")
    print(query)
    print("\n[답변]")
    print(result["answer"])

    print("\n[실행 SKILL]")
    for idx, skill_id in enumerate(result["route"]["plan"], 1):
        print(f"{idx}. {skill_id} - {SKILLS[skill_id]['name']}")

    print("\n[Evidence]")
    for source_id in result["sources"]:
        print(f"- {source_id}")


def show_financial_kg(company: str, year: int) -> None:
    facts = DATA[company][year]
    print(f"\nCompany({company})")
    print(f"├─ HAS_REPORT → Report({facts['source_id']})")
    for metric in [
        "revenue",
        "operating_income",
        "net_income",
        "assets",
        "liabilities",
        "equity",
    ]:
        print(
            f"├─ HAS_FINANCIAL_FACT → {METRIC_LABELS[metric]}"
            f"({format_value(metric, facts[metric])})"
        )
        print(f"│  ├─ OF_METRIC → {metric}")
        print(f"│  ├─ FOR_PERIOD → {year}")
        print(f"│  └─ EXTRACTED_FROM → {facts['source_id']}")


def show_skill_kg() -> None:
    print("\nSkill KG")
    for skill_id, skill in SKILLS.items():
        requires = ", ".join(skill["requires"]) or "-"
        print(f"- {skill_id}")
        print(f"  requires: {requires}")


def run_demo() -> None:
    for query in [
        "샘플전자 2025년 부채비율 알려줘",
        "샘플전자 2023~2025년 매출 추세 알려줘",
        "샘플전자와 샘플메모리 ROE 비교해줘",
        "샘플전자 최근 재무상태 분석해줘",
    ]:
        print_result(query)
        print("\n" + "-" * 60)


def interactive() -> None:
    print("FinSKILL-KG EduBridge 실행 버전")
    print("외부 API 없이 sample data로 실행합니다.")

    while True:
        print(
            "\n1. 질문하기\n"
            "2. Financial KG 보기\n"
            "3. Skill KG 보기\n"
            "4. 기본 데모 실행\n"
            "0. 종료"
        )
        menu = input("\n선택: ").strip()

        if menu == "1":
            print_result(input("질문: ").strip())
        elif menu == "2":
            company = input("기업 [샘플전자]: ").strip() or "샘플전자"
            year = int(input("연도 [2025]: ").strip() or "2025")
            show_financial_kg(company, year)
        elif menu == "3":
            show_skill_kg()
        elif menu == "4":
            run_demo()
        elif menu == "0":
            break
        else:
            print("0~4 중에서 선택해 주세요.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--question")
    parser.add_argument("--financial-kg", action="store_true")
    parser.add_argument("--skill-kg", action="store_true")
    parser.add_argument("--company", default="샘플전자")
    parser.add_argument("--year", type=int, default=2025)
    args = parser.parse_args()

    if args.demo:
        run_demo()
    elif args.question:
        print_result(args.question)
    elif args.financial_kg:
        show_financial_kg(args.company, args.year)
    elif args.skill_kg:
        show_skill_kg()
    else:
        interactive()


if __name__ == "__main__":
    main()
