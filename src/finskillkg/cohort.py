from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class DartCompany:
    name: str
    ticker: str
    sector: str


@dataclass(frozen=True)
class DartCohort:
    years: tuple[int, ...]
    companies: tuple[DartCompany, ...]


def load_dart_cohort(path: str | Path = "config/dart_companies.yaml") -> DartCohort:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    years = tuple(int(year) for year in payload.get("years", []))
    companies = tuple(
        DartCompany(
            name=str(item["name"]).strip(),
            ticker=str(item["ticker"]).strip(),
            sector=str(item["sector"]).strip(),
        )
        for item in payload.get("companies", [])
    )

    if not years:
        raise ValueError("DART cohort에 분석 연도가 없습니다.")
    if not companies:
        raise ValueError("DART cohort에 기업이 없습니다.")

    names = [company.name for company in companies]
    if len(names) != len(set(names)):
        raise ValueError("DART cohort에 중복 기업명이 있습니다.")

    return DartCohort(years=years, companies=companies)
