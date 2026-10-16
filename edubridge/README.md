# EduBridge 실행 버전

EduBridge에서 프로젝트 흐름만 바로 실행할 수 있도록 따로 정리한 버전입니다.

기존 Streamlit, NetworkX, pandas, Neo4j를 설치하지 않아도 되도록 Python 표준 라이브러리만 사용합니다.

## 실행

가장 간단한 방법은 아래 한 줄입니다.

```bash
python edubridge/main.py
```

자동으로 기본 예시만 실행하려면:

```bash
python edubridge/main.py --demo
```

질문 한 개만 실행하려면:

```bash
python edubridge/main.py --question "샘플전자 2025년 부채비율 알려줘"
```

## 지원 기능

```text
1. 질문하기
2. Financial KG 보기
3. Skill KG 보기
4. SKILL 보기
5. 기본 데모 실행
```

질문 예시:

```text
샘플전자 2025년 부채비율 알려줘
샘플전자 2023~2025년 매출 추세 알려줘
샘플전자와 샘플메모리 ROE 비교해줘
샘플전자 최근 재무상태 분석해줘
```

## 이 버전에서 뺀 것

EduBridge 실행 환경에서 바로 돌리는 것을 우선해서 아래 기능은 제외했습니다.

- Streamlit 웹 화면
- OpenDART API 호출
- Neo4j
- 외부 LLM API
- pandas / networkx / PyYAML

대신 Financial KG, Skill KG, SKILL dependency, 재무 계산, 질문 routing 흐름은 한 파일에서 확인할 수 있습니다.

실제 OpenDART와 웹 데모까지 확인할 때는 저장소 루트의 app.py를 사용합니다.

## 파일

```text
edubridge/
├── main.py
└── README.md
```

별도 패키지 설치가 필요하지 않습니다.
