---
skill_id: financial_fact_validation
name: Financial Fact Validation
description: 추출된 재무 수치의 누락, 중복, 기본 회계식과 provenance를 확인한다.
trigger_keywords:
  - 검증
  - 오류
  - 확인
requires:
  - financial_statement_extraction
consumes:
  - FinancialFact
produces:
  - ValidatedFinancialFact
tools:
  - Python
validation:
  - accounting_equation
  - duplicate_check
  - provenance_check
required_metrics:
  - assets
  - liabilities
  - equity
---
# Objective

Financial KG에 들어가기 전 재무 수치가 최소한의 검증 조건을 만족하는지 확인한다.

# Procedure

1. 기업·연도·metric 기준 중복을 확인한다.
2. 값과 단위가 비어 있지 않은지 확인한다.
3. 자산, 부채, 자본이 모두 있으면 `자산 ≈ 부채 + 자본`을 확인한다.
4. source_id가 있는지 확인한다.
5. 검증에 실패한 값은 자동 보정하지 않고 실패 이유를 남긴다.

# Constraints

- 회계식 오차가 있다고 값을 임의 수정하지 않는다.
- 검증 규칙은 데이터 품질 확인용이며 감사 의견을 대신하지 않는다.
