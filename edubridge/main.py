from __future__ import annotations

import argparse
import re
from dataclasses import dataclass


SAMPLE_DATA = {
    "샘플전자": {
        2023: {
            "revenue": 82_000_000_000_000,
            "operating_income": 6_150_000_000_000,
            "net_income": 4_100_000_000_000,
            "assets": 105_000_000_000_000,
            "liabilities": 39_000_000_000_000,
            "equity": 66_000_000_000_000,
            "source_id": "DEMO001-2023",
        },
        2024: {
            "revenue": 91_000_000_000_000,
            "operating_income": 8_190_000_000_000,
            "net_income": 5_600_000_000_000,
            "assets": 112_000_000_000_000,
            "liabilities": 41_000_000_000_000,
            "equity": 71_000_000_000_000,
            "source_id": "DEMO001-2024",
        },
        2025: {
            "revenue": 99_000_000_000_000,
            "operating_income": 9_900_000_000_000,
            "net_income": 6_800_000_000_000,
            "assets": 120_000_000_000_000,
            "liabilities": 43_000_000_000_000,
            "equity": 77_000_000_000_000,
            "source_id": "DEMO001-2025",
        },
    },
    "샘플메모리": {
        2023: {
            "revenue": 51_000_000_000_000,
            "operating_income": 2_550_000_000_000,
            "net_income": 1_700_000_000_000,
            "assets": 76_000_000_000_000,
            "liabilities": 36_000_000_000_000,
            "equity": 40_000_000_000_000,
            "source_id": "DEMO002-2023",
        },
        2024: {
            "revenue": 65_000_000_000_000,
            "operating_income": 5_200_000_000_000,
            "net_income": 3_300_000_000_000,
            "assets": 83_000_000_000_000,
            "liabilities": 38_000_000_000_000,
            "equity": 45_000_000_000_000,
            "source_id": "DEMO002-2024",
        },
        2025: {
            "revenue": 78_000_000_000_000,
            "operating_income": 7_020_000_000_000,
            "net_income": 4_600_000_000_000,
            "assets": 90_000_000_000_000,
            "liabilities": 42_000_000_000_000,
            "equity": 48_000_000_000_000,
            "source_id": "DEMO002-2025",
        },
    },
}

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

SKILLS = {
    "financial_statement_extraction": {
        "name": "재무정보 추출",
        "requires": [],
        "description": "질문에 필요한 Financial Fact를 확인한다.",
    },
    "financial_fact_validation": {
        "name": "재무정보 검증",
        "requires": ["financial_statement_extraction"],
        "description": "누락값과 출처를 확인한다.",
    },
    "financial_metric_calculation": {
        "name": "재무비율 계산",
        "requires": ["financial_fact_validation"],
        "description": "부채비율, 영업이익률, ROA, ROE를 계산한다.",
    },
    "financial_trend_analysis": {
        "name": "추세 분석",
        "requires": ["financial_metric_calculation"],
        "description": "연도별 값의 상승, 하락, 혼조를 확인한다.",
    },
    "financial_risk_analysis": {
        "name": "Risk Signal",
        "requires": ["financial_metric_calculation", "financial_trend_analysis"],
        "description": "간단한 규칙 기반 Risk Signal을 계산한다.",
    },
    "company_comparison": {
        "name": "기업 비교",
        "requires": ["financial_metric_calculation"],
        "description": "같은 연도 기준으로 두 기업의 지표를 비교한다.",
    },
    "financial_summary_generation": {
        "name": "재무 요약",
        "requires": [
            "financial_metric_calculation",
            "financial_trend_analysis",
            "financial_risk_analysis",
        ],
        "description": "수치, 추세, Risk Signal과 근거를 한 번에 정리한다.",
    },
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


@dataclass(frozen=True)
class QueryRoute:
    intent: str
    companies: tuple[str, ...]
    metric: str | None
    years: tuple[int, ...]
    target_skill: str
    skill_plan: tuple[str, ...]


def safe_divide(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator * 100


def calculate_metric(facts: dict, metric: str) -> float | None:
    if metric in facts:
        return float(facts[metric])
    if metric == "debt_ratio":
        return safe_divide(facts.get("liabilities"), facts.get("equity"))
    if metric == "operating_margin":
        return safe_divide(facts.get("operating_income"), facts.get("revenue"))
    if metric == "roa":
        return safe_divide(facts.get("net_income"), facts.get("assets"))
    if metric == "roe":
        return safe_divide(facts.get("net_income"), facts.get("equity"))
    return None


def format_value(metric: str, value: float | None) -> str:
    if value is None:
        return "N/A"
    if metric in {"debt_ratio", "operating_margin", "roa", "roe"}:
        return f"{value:.2f}%"
    trillion = value / 1_000_000_000_000
    return f"{trillion:,.2f}조원"


def trend_direction(values: list[float]) -> str:
    if len(values) < 2:
        return "판단불가"
    if all(a < b for a, b in zip(values, values[1:])):
        return "상승"
    if all(a > b for a, b in zip(values, values[1:])):
        return "하락"
    if all(a == b for a, b in zip(values, values[1:])):
        return "유지"
    return "혼조"


def resolve_plan(skill_id: str) -> tuple[str, ...]:
    result: list[str] = []
    visiting: set[str] = set()

    def visit(current: str) -> None:
        if current in result:
            return
        if current in visiting:
            raise RuntimeError(f"SKILL dependency cycle: {current}")
        visiting.add(current)
        for dependency in SKILLS[current]["requires"]:
            visit(dependency)
        visiting.remove(current)
        result.append(current)

    visit(skill_id)
    return tuple(result)


def parse_query(query: str) -> QueryRoute:
    companies = tuple(name for name in SAMPLE_DATA if name in query)
    if not companies:
        companies = ("샘플전자",)

    years = tuple(int(value) for value in re.findall(r"20\d{2}", query))

    metric = None
    for keyword, metric_id in METRIC_KEYWORDS.items():
        if keyword in query:
            metric = metric_id
            break

    if any(word in query.lower() for word in ["비교", "vs", "대비"]):
        intent = "comparison"
        target_skill = "company_comparison"
    elif any(word in query for word in ["추세", "변화", "증가", "감소"]):
        intent = "trend"
        target_skill = "financial_trend_analysis"
    elif any(word in query for word in ["리스크", "위험", "risk"]):
        intent = "risk"
        target_skill = "financial_risk_analysis"
    elif any(word in query for word in ["요약", "재무상태", "분석"]):
        intent = "summary"
        target_skill = "financial_summary_generation"
    else:
        intent = "metric"
        target_skill = "financial_metric_calculation"

    return QueryRoute(
        intent=intent,
        companies=companies,
        metric=metric,
        years=years,
        target_skill=target_skill,
        skill_plan=resolve_plan(target_skill),
    )


def select_year(company: str, years: tuple[int, ...]) -> int:
    available = sorted(SAMPLE_DATA[company])
    if years:
        requested = years[-1]
        if requested not in available:
            raise ValueError(
                f"{company} {requested}년 데이터가 없습니다. "
                f"사용 가능: {', '.join(map(str, available))}"
            )
        return requested
    return available[-1]


def answer_metric(route: QueryRoute) -> tuple[str, list[str]]:
    company = route.companies[0]
    year = select_year(company, route.years)
    facts = SAMPLE_DATA[company][year]
    metric = route.metric or "debt_ratio"
    value = calculate_metric(facts, metric)
    label = METRIC_LABELS.get(metric, metric)
    answer = f"{company}의 {year}년 {label}은 {format_value(metric, value)}입니다."
    return answer, [facts["source_id"]]


def answer_trend(route: QueryRoute) -> tuple[str, list[str]]:
    company = route.companies[0]
    metric = route.metric or "revenue"
    available = sorted(SAMPLE_DATA[company])

    if len(route.years) >= 2:
        start, end = route.years[0], route.years[-1]
        years = [year for year in available if start <= year <= end]
    else:
        years = available

    values = []
    sources = []
    lines = []
    for year in years:
        facts = SAMPLE_DATA[company][year]
        value = calculate_metric(facts, metric)
        if value is None:
            continue
        values.append(value)
        sources.append(facts["source_id"])
        lines.append(f"- {year}: {format_value(metric, value)}")

    label = METRIC_LABELS.get(metric, metric)
    header = f"{company}의 {years[0]}~{years[-1]}년 {label} 추세는 {trend_direction(values)}입니다."
    return "\n".join([header, *lines]), sources


def answer_comparison(route: QueryRoute) -> tuple[str, list[str]]:
    companies = route.companies[:2]
    if len(companies) < 2:
        companies = ("샘플전자", "샘플메모리")

    metric = route.metric or "roe"
    common_years = sorted(set(SAMPLE_DATA[companies[0]]) & set(SAMPLE_DATA[companies[1]]))
    year = route.years[-1] if route.years else common_years[-1]
    if year not in common_years:
        raise ValueError(f"{year}년은 두 기업의 공통 데이터 연도가 아닙니다.")

    lines = [f"{year}년 기준 {METRIC_LABELS.get(metric, metric)} 비교입니다."]
    sources = []
    for company in companies:
        facts = SAMPLE_DATA[company][year]
        value = calculate_metric(facts, metric)
        lines.append(f"- {company}: {format_value(metric, value)}")
        sources.append(facts["source_id"])

    return "\n".join(lines), sources


def risk_signal(facts: dict) -> tuple[str, list[str]]:
    score = 0
    reasons = []
    debt_ratio = calculate_metric(facts, "debt_ratio")
    operating_margin = calculate_metric(facts, "operating_margin")

    if debt_ratio is not None and debt_ratio >= 200:
        score += 2
        reasons.append("부채비율 200% 이상")
    elif debt_ratio is not None and debt_ratio >= 100:
        score += 1
        reasons.append("부채비율 100% 이상")

    if operating_margin is not None and operating_margin < 0:
        score += 2
        reasons.append("영업이익률 적자")
    elif operating_margin is not None and operating_margin < 5:
        score += 1
        reasons.append("영업이익률 5% 미만")

    if score >= 4:
        level = "HIGH"
    elif score >= 2:
        level = "MEDIUM"
    else:
        level = "LOW"

    return level, reasons or ["현재 단순 규칙에서 뚜렷한 경고 조건 없음"]


def answer_summary(route: QueryRoute) -> tuple[str, list[str]]:
    company = route.companies[0]
    year = select_year(company, route.years)
    facts = SAMPLE_DATA[company][year]
    risk, reasons = risk_signal(facts)

    revenue_values = [
        SAMPLE_DATA[company][item]["revenue"] for item in sorted(SAMPLE_DATA[company])
    ]
    lines = [
        f"{company} {year}년 재무 요약입니다.",
        f"- 매출: {format_value('revenue', facts['revenue'])}",
        f"- 영업이익률: {format_value('operating_margin', calculate_metric(facts, 'operating_margin'))}",
        f"- 부채비율: {format_value('debt_ratio', calculate_metric(facts, 'debt_ratio'))}",
        f"- ROE: {format_value('roe', calculate_metric(facts, 'roe'))}",
        f"- 매출 추세: {trend_direction(revenue_values)}",
        f"- Risk Signal: {risk}",
        f"- Risk 근거: {', '.join(reasons)}",
    ]
    return "\n".join(lines), [facts["source_id"]]


def answer_risk(route: QueryRoute) -> tuple[str, list[str]]:
    company = route.companies[0]
    year = select_year(company, route.years)
    facts = SAMPLE_DATA[company][year]
    level, reasons = risk_signal(facts)
    answer = "\n".join(
        [
            f"{company} {year}년 Risk Signal은 {level}입니다.",
            *[f"- {reason}" for reason in reasons],
            "- 프로젝트용 단순 규칙이며 투자등급이나 신용등급을 의미하지 않습니다.",
        ]
    )
    return answer, [facts["source_id"]]


def answer(query: str) -> dict:
    route = parse_query(query)

    if route.intent == "comparison":
        text, sources = answer_comparison(route)
    elif route.intent == "trend":
        text, sources = answer_trend(route)
    elif route.intent == "summary":
        text, sources = answer_summary(route)
    elif route.intent == "risk":
        text, sources = answer_risk(route)
    else:
        text, sources = answer_metric(route)

    return {
        "route": route,
        "answer": text,
        "sources": sources,
    }


def print_result(query: str) -> None:
    result = answer(query)
    route: QueryRoute = result["route"]

    print("\n[질문]")
    print(query)
    print("\n[답변]")
    print(result["answer"])
    print("\n[실행 SKILL]")
    for idx, skill_id in enumerate(route.skill_plan, 1):
        print(f"{idx}. {skill_id} - {SKILLS[skill_id]['name']}")
    print("\n[Evidence]")
    for source_id in result["sources"]:
        print(f"- {source_id}")


def print_financial_kg(company: str = "샘플전자", year: int = 2025) -> None:
    if company not in SAMPLE_DATA:
        raise ValueError(f"지원 기업: {', '.join(SAMPLE_DATA)}")
    if year not in SAMPLE_DATA[company]:
        raise ValueError(f"지원 연도: {', '.join(map(str, sorted(SAMPLE_DATA[company])))}")

    facts = SAMPLE_DATA[company][year]
    print(f"\nFinancial KG Sample: {company} / {year}")
    print(f"Company({company})")
    print(f"├─ HAS_REPORT → Report({facts['source_id']})")

    metrics = [
        "revenue",
        "operating_income",
        "net_income",
        "assets",
        "liabilities",
        "equity",
    ]
    for idx, metric in enumerate(metrics):
        branch = "└─" if idx == len(metrics) - 1 else "├─"
        print(
            f"{branch} HAS_FINANCIAL_FACT → "
            f"{METRIC_LABELS[metric]}({format_value(metric, facts[metric])})"
        )
        print(f"   ├─ OF_METRIC → {metric}")
        print(f"   ├─ FOR_PERIOD → {year}")
        print(f"   └─ EXTRACTED_FROM → {facts['source_id']}")


def print_skill_kg() -> None:
    print("\nSkill KG")
    for skill_id, skill in SKILLS.items():
        requires = ", ".join(skill["requires"]) or "-"
        print(f"- {skill_id}")
        print(f"  name: {skill['name']}")
        print(f"  requires: {requires}")


def print_skill(skill_id: str) -> None:
    if skill_id not in SKILLS:
        raise ValueError(f"지원 SKILL: {', '.join(SKILLS)}")
    skill = SKILLS[skill_id]
    print(f"\n{skill_id}")
    print(f"name: {skill['name']}")
    print(f"description: {skill['description']}")
    print(f"requires: {', '.join(skill['requires']) or '-'}")
    print("plan:")
    for idx, item in enumerate(resolve_plan(skill_id), 1):
        print(f"  {idx}. {item}")


def run_demo() -> None:
    questions = [
        "샘플전자 2025년 부채비율 알려줘",
        "샘플전자 2023~2025년 매출 추세 알려줘",
        "샘플전자와 샘플메모리 ROE 비교해줘",
        "샘플전자 최근 재무상태 분석해줘",
    ]
    print("=" * 68)
    print("FinSKILL-KG EduBridge Demo")
    print("=" * 68)
    for query in questions:
        print_result(query)
        print("\n" + "-" * 68)


def interactive() -> None:
    print("=" * 68)
    print("FinSKILL-KG EduBridge 실행 버전")
    print("외부 API 없이 sample data로 동작합니다.")
    print("=" * 68)

    while True:
        print(
            "\n1. 질문하기\n"
            "2. Financial KG 보기\n"
            "3. Skill KG 보기\n"
            "4. SKILL 보기\n"
            "5. 기본 데모 실행\n"
            "0. 종료"
        )
        menu = input("\n선택: ").strip()

        try:
            if menu == "1":
                query = input("질문: ").strip()
                print_result(query)
            elif menu == "2":
                company = input("기업 [샘플전자]: ").strip() or "샘플전자"
                year_text = input("연도 [2025]: ").strip() or "2025"
                print_financial_kg(company, int(year_text))
            elif menu == "3":
                print_skill_kg()
            elif menu == "4":
                print("지원 SKILL:")
                for skill_id in SKILLS:
                    print(f"- {skill_id}")
                skill_id = input("SKILL: ").strip()
                print_skill(skill_id)
            elif menu == "5":
                run_demo()
            elif menu == "0":
                print("종료합니다.")
                return
            else:
                print("0~5 중에서 선택해 주세요.")
        except (ValueError, KeyError) as exc:
            print(f"오류: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="FinSKILL-KG EduBridge 실행 버전")
    parser.add_argument("--demo", action="store_true", help="기본 질문 4개 실행")
    parser.add_argument("--question", help="질문 한 개 실행")
    parser.add_argument("--financial-kg", action="store_true", help="Financial KG 출력")
    parser.add_argument("--skill-kg", action="store_true", help="Skill KG 출력")
    parser.add_argument("--skill", help="SKILL 상세 출력")
    parser.add_argument("--company", default="샘플전자")
    parser.add_argument("--year", type=int, default=2025)
    args = parser.parse_args()

    if args.demo:
        run_demo()
    elif args.question:
        print_result(args.question)
    elif args.financial_kg:
        print_financial_kg(args.company, args.year)
    elif args.skill_kg:
        print_skill_kg()
    elif args.skill:
        print_skill(args.skill)
    else:
        interactive()


if __name__ == "__main__":
    main()
