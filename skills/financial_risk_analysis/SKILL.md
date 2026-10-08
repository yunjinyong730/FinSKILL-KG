---
skill_id: financial_risk_analysis
name: Financial Risk Analysis
description: 부채비율과 영업이익률 수준 및 추세를 이용해 단순 Risk Signal을 만든다.
trigger_keywords:
  - 위험
  - 리스크
  - 건전성
  - 안정성
  - 악화
requires:
  - financial_trend_analysis
consumes:
  - FinancialRatio
  - TrendSignal
produces:
  - RiskSignal
tools:
  - Python
validation:
  - rule_trace
required_metrics:
  - revenue
  - operating_income
  - liabilities
  - equity
---
# Objective

재무지표의 수준과 최근 추세를 이용해 프로젝트 데모용 Risk Signal을 계산한다.

# Procedure

1. 최신 부채비율을 확인한다.
2. 최신 영업이익률을 확인한다.
3. 영업이익률의 최근 추세를 확인한다.
4. 사전에 정의한 규칙으로 LOW, MEDIUM, HIGH를 반환한다.
5. 어떤 규칙 때문에 결과가 나왔는지 이유를 같이 반환한다.

# Constraints

- 이 결과를 신용등급이나 투자등급으로 표현하지 않는다.
- 정성적 사업위험, 시장위험, 현금흐름 분석을 수행한 것처럼 과장하지 않는다.
