from __future__ import annotations

from dataclasses import dataclass

from .graph import DualKnowledgeGraph
from .skills import SkillRegistry


METRIC_QUERY_MAP = [
    ("부채비율", "debt_ratio"),
    ("영업이익률", "operating_margin"),
    ("매출성장률", "revenue_growth"),
    ("성장률", "revenue_growth"),
    ("roa", "roa"),
    ("총자산이익률", "roa"),
    ("roe", "roe"),
    ("자기자본이익률", "roe"),
    ("영업이익", "operating_income"),
    ("당기순이익", "net_income"),
    ("순이익", "net_income"),
    ("매출", "revenue"),
    ("자산", "assets"),
    ("부채", "liabilities"),
    ("자본", "equity"),
]


@dataclass(frozen=True)
class QueryRoute:
    intent: str
    target_skill: str
    companies: tuple[str, ...]
    metric: str | None
    plan: tuple[str, ...]


def _find_companies(query: str, graph: DualKnowledgeGraph) -> tuple[str, ...]:
    query_lower = query.lower()
    found = []
    for name in graph.company_names():
        position = query_lower.find(name.lower())
        if position >= 0:
            found.append((position, name))
    found.sort(key=lambda item: item[0])
    return tuple(name for _, name in found)


def _find_metric(query: str) -> str | None:
    query_lower = query.lower()
    for keyword, metric in METRIC_QUERY_MAP:
        if keyword in query_lower:
            return metric
    return None


def route_query(
    query: str,
    graph: DualKnowledgeGraph,
    registry: SkillRegistry,
) -> QueryRoute:
    text = query.lower()
    companies = _find_companies(query, graph)
    metric = _find_metric(query)

    if any(word in text for word in ["비교", "vs", "대비"]):
        intent = "comparison"
        skill = "company_comparison"
    elif any(word in text for word in ["위험", "리스크", "건전", "안정", "악화"]):
        intent = "risk"
        skill = "financial_risk_analysis"
    elif metric is not None and not any(word in text for word in ["추세", "변화", "최근"]):
        intent = "metric"
        skill = "financial_metric_calculation"
    elif any(word in text for word in ["재무상태", "전체 분석", "종합", "요약"]):
        intent = "summary"
        skill = "financial_summary_generation"
    elif any(word in text for word in ["추세", "변화", "최근", "증가", "감소", "성장"]):
        intent = "trend"
        skill = "financial_trend_analysis"
    else:
        intent = "summary"
        skill = "financial_summary_generation"

    return QueryRoute(
        intent=intent,
        target_skill=skill,
        companies=companies,
        metric=metric,
        plan=tuple(registry.plan(skill)),
    )
