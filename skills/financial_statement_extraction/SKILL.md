---
skill_id: financial_statement_extraction
name: Financial Statement Extraction
description: OpenDART 또는 정형 재무제표에서 핵심 재무항목을 추출하고 표준 metric으로 변환한다.
trigger_keywords:
  - 재무제표
  - 공시
  - 추출
requires: []
consumes:
  - FinancialReport
produces:
  - FinancialFact
tools:
  - OpenDART
validation:
  - numeric_amount
  - source_required
required_metrics:
  - revenue
  - operating_income
  - net_income
  - assets
  - liabilities
  - equity
---
# Objective

공시나 재무제표에서 분석에 필요한 핵심 재무항목을 가져와 Financial Fact 형태로 정리한다.

# Procedure

1. 기업, 사업연도, 연결/별도 재무제표 여부를 확인한다.
2. 매출액, 영업이익, 당기순이익, 자산, 부채, 자본을 찾는다.
3. 계정명을 프로젝트의 canonical metric으로 변환한다.
4. 금액, 단위, 사업연도, 공시 식별자를 함께 저장한다.
5. 동일 기업·연도·metric이 중복되면 임의로 합치지 않고 확인 대상으로 남긴다.

# Constraints

- 문서에 없는 값을 추정하지 않는다.
- 수치는 계산 가능한 numeric 값으로 변환할 수 있을 때만 저장한다.
- 출처 식별자가 없는 값은 KG에 넣지 않는다.
