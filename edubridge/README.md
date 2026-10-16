# EduBridge 학습 버전

EduBridge 안에서 **실제로 학습을 돌리는 용도**로 따로 정리한 실행 파일입니다.

이 프로젝트에서 Financial KG와 Skill KG 자체는 모델처럼 학습하는 대상이 아닙니다.  
Financial KG는 OpenDART 데이터를 구조화해서 만들고, Skill KG는 `SKILL.md`의 dependency를 이용해 구성합니다.

EduBridge에서 학습하는 부분은 **사용자 질문을 어떤 금융 SKILL로 보낼지 결정하는 Skill Router**입니다.

```text
사용자 질문
   ↓
학습된 Skill Router
   ↓
target SKILL 예측
   ↓
Skill KG dependency
   ↓
Financial KG 조회
   ↓
Python 재무 계산
   ↓
답변
```

## 1. 설치

저장소 루트에서 실행합니다.

```bash
pip install -r edubridge/requirements.txt
```

## 2. 학습

EduBridge에서 실제로 돌려야 하는 메인 학습 파일은 아래입니다.

```bash
python edubridge/train.py
```

기본 설정은 20 epoch입니다.

```bash
python edubridge/train.py --epochs 20
```

학습 중에는 아래 값이 epoch별로 출력됩니다.

```text
train_acc
valid_acc
valid_f1
valid_loss
```

예시:

```text
epoch=01 train_acc=...
epoch=02 train_acc=...
...
Training complete
test_accuracy=...
test_macro_f1=...
```

## 3. 학습 결과

학습이 끝나면 `edubridge/artifacts/`에 결과가 저장됩니다.

```text
edubridge/artifacts/
├── skill_router.joblib
├── metrics.json
├── history.csv
├── confusion_matrix.csv
└── dataset/
    ├── train.csv
    ├── valid.csv
    ├── test.csv
    └── manifest.json
```

각 파일은 다음 용도입니다.

| 파일 | 내용 |
| --- | --- |
| `skill_router.joblib` | 최종 학습 모델 |
| `metrics.json` | test accuracy, macro F1, 클래스별 성능 |
| `history.csv` | epoch별 학습 기록 |
| `confusion_matrix.csv` | SKILL 분류 confusion matrix |
| `dataset/*.csv` | 실제 학습, 검증, 테스트에 사용된 질문 |
| `dataset/manifest.json` | split별 건수, 클래스 분포, 중복 검사 결과 |

## 4. 어떤 것을 학습하는가

Router가 분류하는 target SKILL은 5개입니다.

```text
financial_metric_calculation
financial_trend_analysis
financial_risk_analysis
company_comparison
financial_summary_generation
```

나머지 SKILL은 직접 예측하는 대상이 아니라 Skill KG의 dependency로 실행됩니다.

예를 들어 Router가

```text
financial_summary_generation
```

을 선택하면 실제 실행 순서는

```text
financial_statement_extraction
        ↓
financial_fact_validation
        ↓
financial_metric_calculation
        ↓
financial_trend_analysis
        ↓
financial_risk_analysis
        ↓
financial_summary_generation
```

으로 확장됩니다.

## 5. 학습 데이터

별도 외부 데이터 다운로드 없이 EduBridge 안에서 재현할 수 있도록 금융 질문 template로 학습 데이터를 만듭니다.

기업명은 실제 DART cohort 15개를 사용합니다.

```text
삼성전자
SK하이닉스
현대자동차
기아
현대모비스
NAVER
카카오
LG전자
LG에너지솔루션
삼성SDI
POSCO홀딩스
셀트리온
삼성바이오로직스
SK텔레콤
KT
```

학습, 검증, 테스트는 **서로 다른 문장 template**을 사용하도록 나눴습니다.  
같은 문장을 그대로 train/test에 반복해서 넣는 방식은 사용하지 않습니다.

기본 데이터 크기는 이전보다 크게 늘렸습니다.

```text
Train : 2,000 × 5 classes = 10,000
Valid :   400 × 5 classes =  2,000
Test  :   400 × 5 classes =  2,000

Total : 14,000 questions
```

질문 수만 단순 복제하지 않고 기업, 연도, 지표, 문장 표현을 조합해 서로 다른 질문을 생성합니다.

현재 질문 조합에는 아래 항목이 들어갑니다.

```text
15개 DART 기업
11개 재무 지표
2023~2025년
학습/검증/테스트별 별도 문장 template
split별 표현 variation
```

학습, 검증, 테스트 문장은 생성 후 다시 중복을 검사합니다. 같은 질문이 서로 다른 split에 들어가면 학습을 중단하도록 했습니다.

데이터 구성 결과는 아래 파일에서 확인할 수 있습니다.

```text
edubridge/artifacts/dataset/manifest.json
```

빠르게 동작만 확인하고 싶으면 크기를 줄여 실행할 수 있습니다.

```bash
python edubridge/train.py \
  --epochs 5 \
  --train-samples-per-class 200 \
  --valid-samples-per-class 50 \
  --test-samples-per-class 50
```

기본 학습은 그대로 아래 명령을 사용하면 됩니다.

```bash
python edubridge/train.py --epochs 20
```

## 6. 학습 모델

질문 수가 크지 않고 Router 역할만 수행하면 되기 때문에 무거운 LLM을 다시 fine-tuning하지 않습니다.

현재 Router는

```text
Character TF-IDF
        ↓
SGDClassifier (log loss)
```

구조입니다.

한국어 조사나 띄어쓰기 차이에 덜 민감하도록 character n-gram을 사용하고, `partial_fit`으로 epoch 단위 학습을 수행합니다.

즉 EduBridge에서는 실제로 분류 모델 parameter가 학습되고, epoch별 validation 결과와 최종 model artifact가 남습니다.

## 7. 학습 모델로 질문 실행

학습이 끝난 뒤:

```bash
python edubridge/inference.py \
  --question "샘플전자 최근 재무상태 전체적으로 정리해줘"
```

출력 예시는 다음과 같습니다.

```text
[Router]
skill: financial_summary_generation
confidence: ...

[Answer]
...

[Skill Plan]
1. financial_statement_extraction
2. financial_fact_validation
...

[Evidence]
- DEMO001-2025
```

직접 여러 질문을 입력하려면:

```bash
python edubridge/inference.py
```

## 8. 실제 DART 데이터로 inference

OpenDART 데이터를 미리 생성한 경우:

```bash
python edubridge/inference.py \
  --model edubridge/artifacts/skill_router.joblib \
  --data data/dart_financials.csv \
  --question "삼성전자 2025년 부채비율 알려줘"
```

Router는 EduBridge에서 학습한 모델을 사용하고, 재무 수치는 Financial KG에서 가져옵니다.

## EduBridge에서 무엇을 실행하면 되는가

과제에서 **학습 실행 화면이나 학습 로그가 필요하다면** 아래 명령이 기준입니다.

```bash
python edubridge/train.py --epochs 20
```

학습 완료 후 결과 확인은:

```bash
cat edubridge/artifacts/metrics.json
```

그리고 학습된 모델까지 실제 프로젝트 흐름에 연결되는 것을 보여주려면:

```bash
python edubridge/inference.py \
  --question "샘플전자 2025년 부채비율 알려줘"
```

기존 `edubridge/main.py`는 API 없이 프로젝트 흐름만 확인하는 간단한 실행 버전이고, **학습 과제에는 `train.py`를 사용하면 됩니다.**
