from __future__ import annotations

from typing import Iterable


RATIO_LABELS = {
    "debt_ratio": "부채비율",
    "operating_margin": "영업이익률",
    "roa": "ROA",
    "roe": "ROE",
    "revenue_growth": "매출성장률",
}


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return float(numerator) / float(denominator) * 100.0


def calculate_ratios(
    facts: dict[str, float],
    previous_facts: dict[str, float] | None = None,
) -> dict[str, float | None]:
    previous_facts = previous_facts or {}
    return {
        "debt_ratio": _safe_ratio(facts.get("liabilities"), facts.get("equity")),
        "operating_margin": _safe_ratio(facts.get("operating_income"), facts.get("revenue")),
        "roa": _safe_ratio(facts.get("net_income"), facts.get("assets")),
        "roe": _safe_ratio(facts.get("net_income"), facts.get("equity")),
        "revenue_growth": _safe_ratio(
            None
            if facts.get("revenue") is None or previous_facts.get("revenue") is None
            else facts["revenue"] - previous_facts["revenue"],
            previous_facts.get("revenue"),
        ),
    }


def trend_direction(values: Iterable[float], tolerance: float = 1e-9) -> str:
    values = list(values)
    if len(values) < 2:
        return "판단불가"

    diff = [b - a for a, b in zip(values[:-1], values[1:])]
    if all(abs(v) <= tolerance for v in diff):
        return "유지"
    if all(v >= -tolerance for v in diff) and any(v > tolerance for v in diff):
        return "상승"
    if all(v <= tolerance for v in diff) and any(v < -tolerance for v in diff):
        return "하락"
    return "혼조"


def assess_financial_risk(
    debt_ratio: float | None,
    operating_margin: float | None,
    operating_margin_trend: str,
) -> dict:
    score = 0
    reasons: list[str] = []

    if debt_ratio is None:
        reasons.append("부채비율 계산에 필요한 값이 부족합니다.")
    elif debt_ratio >= 200:
        score += 2
        reasons.append(f"부채비율이 {debt_ratio:.1f}%로 높은 편입니다.")
    elif debt_ratio >= 100:
        score += 1
        reasons.append(f"부채비율이 {debt_ratio:.1f}%로 확인됩니다.")
    else:
        reasons.append(f"부채비율은 {debt_ratio:.1f}%입니다.")

    if operating_margin is None:
        reasons.append("영업이익률 계산에 필요한 값이 부족합니다.")
    elif operating_margin < 0:
        score += 2
        reasons.append(f"영업이익률이 {operating_margin:.1f}%로 적자 구간입니다.")
    elif operating_margin < 5:
        score += 1
        reasons.append(f"영업이익률이 {operating_margin:.1f}%로 낮은 편입니다.")
    else:
        reasons.append(f"영업이익률은 {operating_margin:.1f}%입니다.")

    if operating_margin_trend == "하락":
        score += 1
        reasons.append("영업이익률이 최근 기간 동안 하락했습니다.")

    level = "LOW" if score <= 1 else "MEDIUM" if score <= 3 else "HIGH"
    return {"score": score, "level": level, "reasons": reasons}


def format_money(value: float, unit: str = "KRW") -> str:
    if unit != "KRW":
        return f"{value:,.2f} {unit}"
    trillion = value / 1_000_000_000_000
    if abs(trillion) >= 1:
        return f"{trillion:,.2f}조원"
    billion = value / 100_000_000
    return f"{billion:,.1f}억원"
