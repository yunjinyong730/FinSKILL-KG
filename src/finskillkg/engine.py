from __future__ import annotations

import pandas as pd

from .graph import DualKnowledgeGraph
from .metrics import (
    RATIO_LABELS,
    assess_financial_risk,
    calculate_ratios,
    format_money,
    trend_direction,
)
from .normalize import METRIC_LABELS
from .router import QueryRoute, route_query
from .skills import SkillRegistry


class FinSkillEngine:
    def __init__(self, graph: DualKnowledgeGraph, registry: SkillRegistry):
        self.graph = graph
        self.registry = registry

    def answer(self, query: str) -> dict:
        route = route_query(query, self.graph, self.registry)
        if not route.companies:
            return self._result(
                route,
                "질문에서 등록된 기업명을 찾지 못했습니다. "
                f"사용 가능한 기업: {', '.join(self.graph.company_names())}",
                [],
            )

        if route.intent == "comparison":
            if len(route.companies) < 2:
                return self._result(
                    route,
                    "기업 비교는 두 개 이상의 기업명이 필요합니다.",
                    [],
                )
            return self._comparison(route)
        if route.intent == "metric":
            return self._metric(route)
        if route.intent == "trend":
            return self._trend(route)
        if route.intent == "risk":
            return self._risk(route)
        return self._summary(route)

    @staticmethod
    def _year_facts(frame: pd.DataFrame) -> dict[int, dict[str, float]]:
        result = {}
        for year, group in frame.groupby("year"):
            result[int(year)] = {
                row.metric: float(row.value)
                for row in group.itertuples(index=False)
            }
        return result

    @staticmethod
    def _ratio_by_year(frame: pd.DataFrame) -> dict[int, dict[str, float | None]]:
        facts = FinSkillEngine._year_facts(frame)
        result = {}
        years = sorted(facts)
        for idx, year in enumerate(years):
            previous = facts[years[idx - 1]] if idx > 0 else None
            result[year] = calculate_ratios(facts[year], previous)
        return result

    def _metric(self, route: QueryRoute) -> dict:
        company = route.companies[0]
        frame = self.graph.facts(company)
        years = sorted(frame["year"].unique())
        latest = int(years[-1])
        metric = route.metric

        if metric in METRIC_LABELS:
            row = frame[(frame["year"] == latest) & (frame["metric"] == metric)]
            if row.empty:
                answer = f"{company} {latest}년 {METRIC_LABELS[metric]} 데이터를 찾지 못했습니다."
            else:
                value = float(row.iloc[0]["value"])
                answer = f"{company}의 {latest}년 {METRIC_LABELS[metric]}은 {format_money(value)}입니다."
        else:
            ratios = self._ratio_by_year(frame)[latest]
            if metric is None:
                lines = [f"{company} {latest}년 주요 재무비율입니다."]
                for key in ["debt_ratio", "operating_margin", "roa", "roe"]:
                    value = ratios.get(key)
                    lines.append(
                        f"- {RATIO_LABELS[key]}: {value:.2f}%" if value is not None else f"- {RATIO_LABELS[key]}: N/A"
                    )
                answer = "\n".join(lines)
            else:
                value = ratios.get(metric)
                label = RATIO_LABELS.get(metric, metric)
                answer = (
                    f"{company}의 {latest}년 {label}은 {value:.2f}%입니다."
                    if value is not None
                    else f"{company}의 {latest}년 {label}을 계산할 수 없습니다."
                )

        return self._result(route, answer, self.graph.sources(company, [latest]))

    def _trend(self, route: QueryRoute) -> dict:
        company = route.companies[0]
        frame = self.graph.facts(company)
        facts = self._year_facts(frame)
        ratios = self._ratio_by_year(frame)
        years = sorted(facts)

        revenue_values = [facts[year].get("revenue") for year in years]
        revenue_values = [value for value in revenue_values if value is not None]
        margin_values = [ratios[year].get("operating_margin") for year in years]
        margin_values = [value for value in margin_values if value is not None]

        lines = [f"{company}의 {years[0]}~{years[-1]}년 재무 추세입니다."]
        if revenue_values:
            lines.append(f"- 매출 추세: {trend_direction(revenue_values)}")
            for year in years:
                value = facts[year].get("revenue")
                if value is not None:
                    lines.append(f"  - {year}: {format_money(value)}")
        if margin_values:
            lines.append(f"- 영업이익률 추세: {trend_direction(margin_values)}")
            for year in years:
                value = ratios[year].get("operating_margin")
                if value is not None:
                    lines.append(f"  - {year}: {value:.2f}%")

        return self._result(route, "\n".join(lines), self.graph.sources(company, years))

    def _risk(self, route: QueryRoute) -> dict:
        company = route.companies[0]
        frame = self.graph.facts(company)
        ratios = self._ratio_by_year(frame)
        years = sorted(ratios)
        latest = years[-1]
        margin_values = [
            ratios[year]["operating_margin"]
            for year in years
            if ratios[year]["operating_margin"] is not None
        ]
        risk = assess_financial_risk(
            ratios[latest].get("debt_ratio"),
            ratios[latest].get("operating_margin"),
            trend_direction(margin_values),
        )
        lines = [
            f"{company}의 단순 재무 Risk Signal은 {risk['level']}입니다.",
            *[f"- {reason}" for reason in risk["reasons"]],
            "- 이 값은 투자등급이나 신용등급이 아니라 프로젝트용 규칙 기반 지표입니다.",
        ]
        return self._result(route, "\n".join(lines), self.graph.sources(company, years))

    def _comparison(self, route: QueryRoute) -> dict:
        companies = route.companies[:2]
        frames = {company: self.graph.facts(company) for company in companies}
        common_years = set(frames[companies[0]]["year"]) & set(frames[companies[1]]["year"])
        if not common_years:
            return self._result(route, "두 기업의 공통 분석 연도가 없습니다.", [])
        year = int(max(common_years))

        lines = [f"{year}년 기준 {companies[0]}와 {companies[1]} 비교입니다."]
        evidence = []
        for company in companies:
            frame = frames[company]
            ratios = self._ratio_by_year(frame)[year]
            lines.append(
                f"- {company}: 영업이익률 {self._pct(ratios['operating_margin'])}, "
                f"부채비율 {self._pct(ratios['debt_ratio'])}, ROE {self._pct(ratios['roe'])}"
            )
            evidence.extend(self.graph.sources(company, [year]))

        unique_evidence = list({item["source_id"]: item for item in evidence}.values())
        return self._result(route, "\n".join(lines), unique_evidence)

    def _summary(self, route: QueryRoute) -> dict:
        company = route.companies[0]
        frame = self.graph.facts(company)
        facts = self._year_facts(frame)
        ratios = self._ratio_by_year(frame)
        years = sorted(facts)
        latest = years[-1]

        revenue = [facts[year].get("revenue") for year in years]
        revenue = [value for value in revenue if value is not None]
        margin = [ratios[year].get("operating_margin") for year in years]
        margin = [value for value in margin if value is not None]
        risk = assess_financial_risk(
            ratios[latest].get("debt_ratio"),
            ratios[latest].get("operating_margin"),
            trend_direction(margin),
        )

        lines = [
            f"{company} {latest}년 기준 재무 요약입니다.",
            f"- 매출: {format_money(facts[latest]['revenue'])}" if facts[latest].get("revenue") is not None else "- 매출: N/A",
            f"- 영업이익률: {self._pct(ratios[latest].get('operating_margin'))}",
            f"- �채비율: {self._pct(ratios[latest].get('debt_ratio'))}",
            f"- ROE: {self._pct(ratios[latest].get('roe'))}",
            f"- 매출 추세: {trend_direction(revenue)}",
            f"- 영업이익률 추세: {trend_direction(margin)}",
            f"- Risk Signal: {risk['level']}",
        ]
        return self._result(route, "\n".join(lines), self.graph.sources(company, years))

    @staticmethod
    def _pct(value: float | None) -> str:
        return "N/A" if value is None else f"{value:.2f}%"

    @staticmethod
    def _result(route: QueryRoute, answer: str, evidence: list[dict]) -> dict:
        return {
            "intent": route.intent,
            "target_skill": route.target_skill,
            "skill_plan": list(route.plan),
            "companies": list(route.companies),
            "metric": route.metric,
            "answer": answer,
            "evidence": evidence,
        }
