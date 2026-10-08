---
skill_id: financial_summary_generation
name: Financial Summary Generation
description: 계산된 재무비율, 추세, Risk Signal과 근거를 한 번에 정리한다.
trigger_keywords:
  - 분석
  - 요약
  - 재무상태
requires:
  - financial_metric_calculation
  - financial_trend_analysis
  - financial_risk_analysis
consumes:
  - FinancialFact
  - FinancialRatio
  - TrendSignal
  - RiskSignal
produces:
  - FinancialSummary
tools:
  - TemplateRenderer
validation:
  - evidence_required
required_metrics:
  - revenue
  - operating_income
  - net_income
  - assets
  - liabilities
  - equity
---
# Objective

여러 SKILL의 결과를 한 번에 읽을 수 있도록 재무 요약으로 정리한다.

# Procedure

1. 최신 사업연도의 핵심 수치와 비율을 정리한다.
2. 최근 기간의 매출과 수익성 추세를 붙인다.
3. Risk Signal을 이유와 함께 정리한다.
4. 분석에 사용된 report/source를 evidence로 제시한다.
5. 데이터가 없는 항목은 N/A로 표시한다.

# Constraints

- 원본 수치와 계산 결과를 섞어서 새로운 사실을 만들지 않는다.
- evidence가 없는 판단은 최종 요약에 넣지 않는다.
