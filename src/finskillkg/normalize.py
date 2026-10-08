from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd


METRIC_LABELS = {
    "revenue": "매출액",
    "operating_income": "영업이익",
    "net_income": "당기순이익",
    "assets": "자산총계",
    "liabilities": "부채총계",
    "equity": "자본총계",
}

METRIC_ALIASES = {
    "revenue": ["매출액", "매출", "수익(매출액)", "영업수익", "revenue", "sales"],
    "operating_income": ["영업이익", "영업이익(손실)", "operating income", "operating profit"],
    "net_income": ["당기순이익", "당기순이익(손실)", "분기순이익", "net income"],
    "assets": ["자산총계", "총자산", "assets"],
    "liabilities": ["부채총계", "총부채", "liabilities"],
    "equity": ["자본총계", "자본", "equity"],
}

EXPECTED_STATEMENT = {
    "revenue": {"IS", "CIS"},
    "operating_income": {"IS", "CIS"},
    "net_income": {"IS", "CIS"},
    "assets": {"BS"},
    "liabilities": {"BS"},
    "equity": {"BS"},
}

REQUIRED_COLUMNS = {
    "company_code",
    "company_name",
    "year",
    "metric",
    "value",
    "unit",
    "source_id",
    "source_name",
}


def normalize_metric_name(name: str) -> str | None:
    text = str(name).strip().lower()
    for metric, aliases in METRIC_ALIASES.items():
        if text in {alias.lower() for alias in aliases}:
            return metric
    return None


def parse_amount(value) -> float | None:
    if value is None:
        return None
    text = str(value).replace(",", "").strip()
    if not text or text in {"-", "None", "nan"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def normalize_dart_records(
    records: Iterable[dict],
    company_code: str,
    company_name: str,
    year: int,
    default_source_id: str,
) -> pd.DataFrame:
    selected: dict[str, dict] = {}

    for record in records:
        metric = normalize_metric_name(record.get("account_nm", ""))
        if not metric:
            continue

        statement = str(record.get("sj_div", "")).strip().upper()
        if statement and statement not in EXPECTED_STATEMENT[metric]:
            continue

        amount = parse_amount(record.get("thstrm_amount"))
        if amount is None:
            continue

        if metric in selected:
            continue

        source_id = str(record.get("rcept_no") or default_source_id)
        source_url = (
            f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={source_id}"
            if source_id.isdigit()
            else ""
        )
        selected[metric] = {
            "company_code": company_code,
            "company_name": company_name,
            "year": int(year),
            "metric": metric,
            "value": amount,
            "unit": "KRW",
            "source_id": source_id,
            "source_name": "OpenDART annual report",
            "source_url": source_url,
        }

    return pd.DataFrame(
        selected.values(),
        columns=sorted(REQUIRED_COLUMNS | {"source_url"}),
    )


def load_financial_csv(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"company_code": str, "source_id": str})
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"필수 컬럼이 없습니다: {sorted(missing)}")

    frame = frame.copy()
    frame["company_code"] = frame["company_code"].astype(str).str.strip()
    frame["company_name"] = frame["company_name"].astype(str).str.strip()
    frame["metric"] = frame["metric"].astype(str).str.strip()
    frame["year"] = pd.to_numeric(frame["year"], errors="raise").astype(int)
    frame["value"] = pd.to_numeric(frame["value"], errors="raise").astype(float)

    unknown = sorted(set(frame["metric"]) - set(METRIC_LABELS))
    if unknown:
        raise ValueError(f"지원하지 않는 metric입니다: {unknown}")

    duplicated = frame.duplicated(["company_code", "year", "metric"], keep=False)
    if duplicated.any():
        rows = frame.loc[duplicated, ["company_code", "year", "metric"]]
        raise ValueError(f"기업/연도/metric 중복이 있습니다:\n{rows.to_string(index=False)}")

    return frame.sort_values(["company_name", "year", "metric"]).reset_index(drop=True)


def validate_financial_frame(frame: pd.DataFrame, relative_tolerance: float = 0.02) -> pd.DataFrame:
    issues = []

    for row in frame.itertuples(index=False):
        if not str(row.source_id).strip():
            issues.append({
                "company_name": row.company_name,
                "year": int(row.year),
                "rule": "source_required",
                "detail": f"{row.metric}: source_id가 비어 있습니다.",
            })

    for (company_name, year), group in frame.groupby(["company_name", "year"]):
        values = {row.metric: float(row.value) for row in group.itertuples(index=False)}
        if {"assets", "liabilities", "equity"}.issubset(values):
            assets = values["assets"]
            expected = values["liabilities"] + values["equity"]
            scale = max(abs(assets), abs(expected), 1.0)
            error = abs(assets - expected) / scale
            if error > relative_tolerance:
                issues.append({
                    "company_name": company_name,
                    "year": int(year),
                    "rule": "accounting_equation",
                    "detail": f"자산과 부채+자본 차이가 {error:.2%}입니다.",
                })

    return pd.DataFrame(issues, columns=["company_name", "year", "rule", "detail"])
