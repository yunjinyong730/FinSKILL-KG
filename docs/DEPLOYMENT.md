# Demo Site Deployment

FinSKILL-KG의 최종 사용자 데모는 `app.py`의 Streamlit 앱입니다.

## 필요한 파일

배포 환경에는 최소한 아래 파일이 포함되어야 합니다.

```text
app.py
requirements.txt
src/
skills/
config/
data/
.streamlit/config.toml
```

실제 기업 데이터를 보여주려면 배포 전에 `data/dart_financials.csv`를 생성합니다.

```bash
export DART_API_KEY="YOUR_KEY"
python scripts/fetch_dart_data.py
```

해당 파일이 없으면 앱은 자동으로 `data/sample_financials.csv`를 사용합니다.

## Streamlit Community Cloud

1. 이 GitHub repository를 Streamlit Community Cloud에 연결합니다.
2. branch는 `main`, entrypoint는 `app.py`로 지정합니다.
3. 실제 DART snapshot을 repository에 포함한 뒤 배포합니다.
4. LLM 문장화를 사용할 경우 Secrets에 아래 값을 등록합니다.

```toml
LLM_API_URL = "YOUR_CHAT_COMPLETIONS_ENDPOINT"
LLM_API_KEY = "YOUR_KEY"
LLM_MODEL = "YOUR_MODEL"
```

LLM 설정이 없어도 Chat Demo의 KG 조회, Skill routing, 재무 계산, trend/risk 분석은 동작합니다.

## Docker

```bash
docker build -t finskill-kg .
docker run --rm -p 8501:8501 finskill-kg
```

브라우저에서 `http://localhost:8501`로 접속합니다.

실제 DART CSV를 container에 별도로 주입하려면 repository의 `data/dart_financials.csv`를 준비한 뒤 image를 다시 build하는 방식이 가장 단순합니다.

## Demo에서 확인할 기능

- 질문 입력 및 답변
- 질문에 선택된 target SKILL
- dependency를 반영한 실행 SKILL 순서
- 답변에 사용된 evidence와 DART source
- Financial KG 시각화
- Skill KG 시각화
- 개별 SKILL metadata와 `SKILL.md` 내용
- 3-system benchmark 결과
