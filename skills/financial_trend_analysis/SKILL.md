---
skill_id: financial_trend_analysis
name: Financial Trend Analysis
description: 기간별 재무 수치와 재무비율의 상승, 하락, 혼조 추세를 확인한다.
trigger_keywords:
  - 최근
  - 추세
  - 변화
  - 증가
  - 감소
requires:
  - financial_metric_calculation
consumes:
  - FinancialFact
  - FinancialRatio
produces:
  - TrendSignal
tools:
  - Python
validation:
  - chronological_order
required_metrics:
  - revenue
  - operating_income
---
# Objective

여러 사업연도의 값을 시간 순으로 비교해 어떤 지표가 지속적으로 변하고 있는지 확인한다.

# Procedure

1. 사업연도를 오름차순으로 정렬한다.
2. 매출과 영업이익률 등 비교 대상의 연도별 값을 준비한다.
3. 연속 상승, 연속 하락, 유지, 혼조로 구분한다.
4. 각 판단에 사용한 연도별 수치를 함께 반환한다.

# Constraints

- 두 개 미만의 시점으로 장기 추세를 단정하지 않는다.
- 중간 연도가 누락된 경우 누락 사실을 숨기지 않는다.
