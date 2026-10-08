---
skill_id: financial_metric_calculation
name: Financial Metric Calculation
description: 검증된 재무 수치로 부채비율, 영업이익률, ROA, ROE, 매출성장률을 계산한다.
trigger_keywords:
  - 부채비율
  - 영업이익률
  - ROA
  - ROE
  - 성장률
requires:
  - financial_fact_validation
consumes:
  - ValidatedFinancialFact
produces:
  - FinancialRatio
tools:
  - Python
validation:
  - denominator_nonzero
  - formula_check
required_metrics:
  - revenue
  - operating_income
  - net_income
  - assets
  - liabilities
  - equity
---
# Objective

LLM이 수치를 직접 암산하지 않도록 정해진 공식으로 재무비율을 계산한다.

# Procedure

1. 계산에 필요한 원본 Financial Fact를 확인한다.
2. 분모가 0이거나 필요한 값이 없으면 N/A로 반환한다.
3. 부채비율은 `부채 / 자본 × 100`으로 계산한다.
4. 영업이익률은 `영업이익 / 매출 × 100`으로 계산한다.
5. ROA는 `당기순이익 / 자산 × 100`, ROE는 `당기순이익 / 자본 × 100`으로 계산한다.
6. 매출성장률은 전년 매출이 있을 때만 계산한다.

# Constraints

- 계산 결과는 소수점 값과 사용한 원본 수치를 함께 추적할 수 있어야 한다.
- 계산할 수 없는 값을 0으로 대체하지 않는다.
