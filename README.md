# FinSKILL-KG

금융 데이터를 저장하는 **Financial Knowledge Graph**와 LLM이 어떤 업무를 어떤 순서로 수행해야 하는지 관리하는 **Skill Knowledge Graph**를 함께 구성하고, 재사용 가능한 `SKILL.md`를 이용해 기업 재무분석을 수행하는 프로토타입입니다.

이 프로젝트에서 세 요소의 역할은 분리되어 있습니다.

```text
Financial KG = 무엇을 알고 있는가
Skill KG     = 어떤 업무를 어떤 순서로 수행하는가
SKILL.md     = 각 업무를 어떻게 수행하는가
```

LLM에게 재무제표 전체를 한 번에 넘기고 답을 생성하게 하는 대신, 재무 수치와 출처는 KG에서 가져오고 계산은 Python에서 처리합니다. LLM은 선택적으로 최종 문장을 정리하는 단계에만 사용할 수 있습니다.

## System Overview

```text
OpenDART / Financial CSV
          |
          v
Financial Fact Normalization
          |
          v
     Financial KG
          ^
          | REQUIRES_METRIC
          |
       Skill KG <---- SKILL.md
          ^
          |
      Skill Router
          ^
          |
      User Query
          |
          v
Metric / Trend / Risk / Comparison
          |
          v
Evidence-based Answer
```

현재 구현은 한 학기 기업연계 프로젝트 범위를 기준으로 구성했습니다. 복잡한 multi-agent 구조나 대규모 금융 ontology를 먼저 넣기보다, **SKILL 정의 → Skill KG 구성 → Financial KG 연결 → 질의 실행 → 근거 확인** 흐름이 실제로 동작하는지 확인하는 데 초점을 맞췄습니다.

## Why this project

금융 분석에서 LLM을 그대로 사용할 경우 다음 문제가 있습니다.

1. 필요한 재무 수치를 잘못 선택할 수 있습니다.
2. 부채비율, 영업이익률 같은 계산을 문장 생성 과정에서 잘못 수행할 수 있습니다.
3. 동일한 질문이라도 분석 절차가 달라질 수 있습니다.
4. 답변에 사용된 원본 데이터와 출처를 다시 확인하기 어렵습니다.

FinSKILL-KG는 이 문제를 다음과 같이 나눠서 처리합니다.

- **Financial KG**: 기업, 연도, 재무지표, Financial Fact, Report를 연결
- **Skill KG**: Skill dependency, input/output, tool, validation rule을 연결
- **SKILL.md**: 실제 업무 절차와 제약조건을 파일 단위로 관리
- **Python calculation**: 재무비율과 trend를 코드로 계산
- **Evidence**: 결과에 사용한 source를 함께 반환

## Main Features

- OpenDART 단일회사 전체 재무제표 수집
- 매출액, 영업이익, 당기순이익, 자산, 부채, 자본 정규화
- Financial KG 구축
- 7개 금융 SKILL 정의 및 Skill KG 구축
- Skill dependency 기반 실행 순서 생성
- Skill과 Financial KG를 `REQUIRES_METRIC` 관계로 연결
- 부채비율, 영업이익률, ROA, ROE, 매출성장률 계산
- 기간별 추세 분석
- 단순 규칙 기반 Risk Signal
- 동일 연도 기준 기업 비교
- source 기반 evidence 반환
- NetworkX JSON 저장
- Neo4j export
- Streamlit demo
- 선택적 LLM 문장 생성
- pytest 및 GitHub Actions

## Financial KG

Financial KG는 분석 대상이 되는 금융 지식을 저장합니다.

```text
Company
  |
  +-- HAS_REPORT ----------> Report
  |
  +-- HAS_FINANCIAL_FACT --> FinancialFact
                              |
                              +-- OF_METRIC ------> Metric
                              +-- FOR_PERIOD -----> Period
                              +-- EXTRACTED_FROM -> Report
```

`FinancialFact`에는 값만 저장하지 않고 다음 정보를 같이 둡니다.

```text
value
unit
year
metric
source_id
```

따라서 최종 답변에서 어떤 report/source가 사용됐는지 다시 확인할 수 있습니다.

## Skill KG

Skill KG는 금융 지식이 아니라 업무 수행 관계를 저장합니다.

```text
Skill
  +-- REQUIRES --------> Skill
  +-- CONSUMES --------> DataType
  +-- PRODUCES --------> OutputType
  +-- USES_TOOL -------> Tool
  +-- VALIDATED_BY ----> ValidationRule
  +-- REQUIRES_METRIC -> Metric
```

예를 들어 `financial_risk_analysis`는 바로 실행하지 않고 아래 dependency를 먼저 따라갑니다.

```text
financial_statement_extraction
        |
        v
financial_fact_validation
        |
        v
financial_metric_calculation
        |
        v
financial_trend_analysis
        |
        v
financial_risk_analysis
```

`REQUIRES_METRIC` 관계가 Skill KG와 Financial KG 사이의 bridge 역할을 합니다.

## SKILL.md

현재 7개의 SKILL을 정의했습니다.

| Skill | 역할 |
| --- | --- |
| `financial_statement_extraction` | 공시/재무제표에서 핵심 Financial Fact 정리 |
| `financial_fact_validation` | 중복, provenance, 회계식 확인 |
| `financial_metric_calculation` | 주요 재무비율 계산 |
| `financial_trend_analysis` | 기간별 변화 분석 |
| `financial_risk_analysis` | 단순 Risk Signal 계산 |
| `company_comparison` | 동일 기간 두 기업 비교 |
| `financial_summary_generation` | 계산 결과와 근거를 하나의 요약으로 정리 |

각 `SKILL.md`는 YAML metadata와 실제 수행 절차를 같이 가지고 있습니다.

```yaml
---
skill_id: financial_metric_calculation
name: Financial Metric Calculation
requires:
  - financial_fact_validation
consumes:
  - ValidatedFinancialFact
produces:
  - FinancialRatio
required_metrics:
  - revenue
  - operating_income
  - net_income
  - assets
  - liabilities
  - equity
---
```

Skill KG는 metadata를 읽어 관계를 만들고, Markdown 본문은 LLM을 사용할 때 해당 업무의 실행 지침으로 전달합니다.

## Financial Metrics

현재 계산하는 지표는 아래와 같습니다.

```text
부채비율     = 부채 / 자본 × 100
영업이익률   = 영업이익 / 매출 × 100
ROA          = 당기순이익 / 자산 × 100
ROE          = 당기순이익 / 자본 × 100
매출성장률   = (당기 매출 - 전기 매출) / 전기 매출 × 100
```

계산은 LLM에 맡기지 않고 Python 함수에서 수행합니다. 필요한 값이 없거나 분모가 0이면 임의의 숫자를 만들지 않고 `N/A`로 처리합니다.

## Risk Signal

현재 `financial_risk_analysis`는 프로젝트 흐름 검증을 위한 단순 규칙입니다.

- 최신 부채비율
- 최신 영업이익률
- 영업이익률의 최근 추세

위 값을 이용해 `LOW`, `MEDIUM`, `HIGH`를 반환합니다.

이 값은 **신용등급, 투자등급, 투자 추천 결과가 아닙니다.** 실제 금융 리스크 모델로 확장할 경우 산업별 기준, 현금흐름, 이자보상배율, 시장 데이터 등을 추가해야 합니다.

## Repository Structure

```text
.
├── app.py
├── run_pipeline.py
├── data/
│   ├── README.md
│   └── sample_financials.csv
├── scripts/
│   ├── fetch_dart_data.py
│   └── export_neo4j.py
├── skills/
│   ├── financial_statement_extraction/SKILL.md
│   ├── financial_fact_validation/SKILL.md
│   ├── financial_metric_calculation/SKILL.md
│   ├── financial_trend_analysis/SKILL.md
│   ├── financial_risk_analysis/SKILL.md
│   ├── company_comparison/SKILL.md
│   └── financial_summary_generation/SKILL.md
├── src/finskillkg/
│   ├── config.py
│   ├── dart.py
│   ├── normalize.py
│   ├── metrics.py
│   ├── skills.py
│   ├── graph.py
│   ├── router.py
│   ├── engine.py
│   ├── llm.py
│   ├── neo4j_store.py
│   └── pipeline.py
├── tests/
│   └── test_core.py
└── .github/workflows/test.yml
```

## Installation

Python 3.10 이상을 기준으로 작성했습니다.

```bash
git clone https://github.com/yunjinyong730/FinSKILL-KG.git
cd FinSKILL-KG

python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Linux / macOS:

```bash
source .venv/bin/activate
```

패키지 설치:

```bash
pip install -r requirements.txt
```

## Quick Start

repository에는 외부 API 없이 전체 흐름을 확인할 수 있도록 synthetic sample data를 포함했습니다.

Dual KG 생성:

```bash
python run_pipeline.py
```

정상 실행되면 아래 파일이 생성됩니다.

```text
outputs/
├── dual_kg.json
├── financial_facts.csv
├── validation_issues.csv
└── summary.json
```

Streamlit 실행:

```bash
streamlit run app.py
```

예시 질문:

```text
샘플전자 최근 3년 재무상태 분석해줘
샘플전자 부채비율 알려줘
샘플전자 수익성 변화 알려줘
샘플전자와 샘플메모리 비교해줘
```

화면에서는 결과뿐 아니라 실제 선택된 Skill plan과 사용된 source를 같이 확인할 수 있습니다.

## OpenDART Data

실제 기업 데이터는 OpenDART API를 이용해 수집할 수 있습니다.

환경변수 설정:

Linux / macOS:

```bash
export DART_API_KEY="YOUR_KEY"
```

Windows PowerShell:

```powershell
$env:DART_API_KEY="YOUR_KEY"
```

예시:

```bash
python scripts/fetch_dart_data.py \
  --companies 삼성전자 SK하이닉스 \
  --years 2023 2024 2025 \
  --output data/dart_financials.csv
```

연결재무제표(`CFS`)를 먼저 조회하고 데이터가 없는 경우 별도재무제표(`OFS`)를 확인합니다.

생성한 CSV로 pipeline을 다시 실행합니다.

```bash
python run_pipeline.py --data data/dart_financials.csv
```

Dashboard에서도 사용하려면:

Linux / macOS:

```bash
export FINSKILL_DATA="data/dart_financials.csv"
streamlit run app.py
```

Windows PowerShell:

```powershell
$env:FINSKILL_DATA="data/dart_financials.csv"
streamlit run app.py
```

## Neo4j Export

기본 실행은 별도 서버 없이 NetworkX 기반으로 동작합니다. 그래프 탐색과 시각화가 필요하면 생성된 graph를 Neo4j에 저장할 수 있습니다.

```bash
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="YOUR_PASSWORD"
export NEO4J_DATABASE="neo4j"

python scripts/export_neo4j.py --graph outputs/dual_kg.json --clear
```

모든 노드는 공통 `KGNode` label을 가지고, `Company`, `FinancialFact`, `Metric`, `Skill` 등 node type별 label을 추가로 가집니다.

## Optional LLM Rendering

프로젝트의 기본 분석은 LLM API 없이 실행됩니다. LLM은 최종 문장을 자연스럽게 정리할 때만 선택적으로 사용할 수 있습니다.

OpenAI-compatible chat completions endpoint를 기준으로 아래 환경변수를 설정합니다.

```bash
export LLM_API_URL="YOUR_CHAT_COMPLETIONS_ENDPOINT"
export LLM_API_KEY="YOUR_KEY"
export LLM_MODEL="YOUR_MODEL"
```

Dashboard에서 **LLM 문장 생성 사용**을 체크하면 계산된 결과, evidence, 선택된 `SKILL.md`만 LLM에 전달합니다.

LLM에게 원본 수치를 다시 계산하게 하거나 새로운 financial fact를 생성하도록 두지 않는 것이 현재 구조의 핵심입니다.

## Validation

Financial Fact를 KG에 넣기 전 다음 항목을 확인합니다.

- company / year / metric 중복
- 숫자 변환 가능 여부
- source_id 존재 여부
- 자산 ≈ 부채 + 자본 회계식

회계식 검증은 표시 단위나 반올림 차이를 고려해 기본 2% 상대오차를 허용합니다. 문제가 발견되면 `outputs/validation_issues.csv`에 남깁니다.

## Test

```bash
python -m pytest -q
```

현재 test에서는 다음을 확인합니다.

- 재무비율 계산식
- 상승 / 하락 / 혼조 trend 판정
- Skill dependency 순서
- OpenDART record normalization
- sample data에서 Dual KG 생성
- 회계식 및 provenance validation
- 기업 요약과 기업 비교 end-to-end 실행

GitHub Actions에서도 동일하게 `pytest`를 실행합니다.

## Current Scope

현재 구현은 프로젝트의 핵심 가설을 빠르게 검증하기 위한 범위입니다.

- Financial KG는 핵심 재무항목 6개 중심입니다.
- Skill KG는 실제 실행에 필요한 dependency와 입출력 관계 중심입니다.
- Router는 결과 재현성을 보기 위해 규칙 기반입니다.
- Event extraction, 공시 원문 GraphRAG, multi-agent는 초기 범위에서 제외했습니다.
- sample data는 실행 검증용 synthetic data이며 실제 기업 분석 결과가 아닙니다.

다음 단계에서는 동일한 평가 질문을 대상으로 `LLM only`, `LLM + Financial KG`, `LLM + Skill KG + Financial KG`를 비교해 numerical accuracy, evidence accuracy, skill routing accuracy를 평가할 수 있습니다.
