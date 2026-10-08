---
skill_id: company_comparison
name: Company Comparison
description: 두 기업의 동일 사업연도 재무비율을 같은 기준으로 비교한다.
trigger_keywords:
  - 비교
  - 대비
  - vs
requires:
  - financial_metric_calculation
consumes:
  - FinancialRatio
produces:
  - CompanyComparison
tools:
  - Python
validation:
  - common_period_check
required_metrics:
  - revenue
  - operating_income
  - net_income
  - liabilities
  - equity
---
# Objective

기업별 계산 기준이 달라지지 않도록 같은 연도의 동일 재무비율을 비교한다.

# Procedure

1. 질문에서 비교할 두 기업을 확인한다.
2. 두 기업 모두 데이터가 있는 가장 최근 사업연도를 찾는다.
3. 영업이익률, 부채비율, ROE를 동일 공식으로 계산한다.
4. 기업별 값을 나란히 제시한다.
5. 사용한 사업연도와 출처를 함께 반환한다.

# Constraints

- 공통 사업연도가 없으면 임의로 다른 연도를 비교하지 않는다.
- 단일 지표만으로 어느 기업이 더 우수하다고 단정하지 않는다.
