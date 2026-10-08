# Data

프로젝트에는 두 종류의 데이터 경로가 있습니다.

## 1. sample_financials.csv

외부 API 없이 pipeline, dashboard, test가 실행되는지 확인하기 위한 synthetic data입니다.
README의 화면 캡처도 credential이 없는 CI에서 재현할 수 있도록 이 데이터를 사용합니다.

## 2. dart_financials.csv

실제 실험에서는 `config/dart_companies.yaml`에 정의한 15개 상장사를 대상으로 OpenDART 재무제표를 수집합니다.

기본 분석 연도는 2023~2025년입니다.

```bash
export DART_API_KEY="YOUR_KEY"
python scripts/fetch_dart_data.py
```

정상 수집되면 아래 두 파일이 생성됩니다.

```text
data/dart_financials.csv
data/dart_financials.manifest.json
```

manifest에는 요청 기업, 연도, OpenDART corp code, CFS/OFS 구분, 실제 수집된 metric과 접수번호가 기록됩니다.

GitHub Actions에서 갱신하려면 repository secret에 `DART_API_KEY`를 등록한 뒤
`refresh-dart` workflow를 실행하면 됩니다.

## 3. evaluation_questions.jsonl

세 시스템을 동일 조건에서 비교하기 위한 36개 평가 질문입니다.

- metric: 12
- trend: 12
- comparison: 12

평가 질문은 모두 `config/dart_companies.yaml`의 실제 기업명만 사용합니다.
정답 수치는 파일에 직접 적지 않고, 실행 시 OpenDART Financial Fact와 고정된 재무비율 공식을 이용해 계산합니다.
