from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from src.finskillkg.config import LLMConfig
from src.finskillkg.engine import FinSkillEngine
from src.finskillkg.graph import DualKnowledgeGraph
from src.finskillkg.llm import LLMClient
from src.finskillkg.normalize import METRIC_LABELS, load_financial_csv
from src.finskillkg.skills import SkillRegistry

st.set_page_config(page_title="FinSKILL-KG", layout="wide")
st.title("FinSKILL-KG")
st.caption("Financial KG + Skill KG를 이용한 근거 기반 재무분석 프로토타입")

data_path = Path(os.getenv("FINSKILL_DATA", "data/sample_financials.csv"))
skills_dir = Path("skills")

frame = load_financial_csv(data_path)
registry = SkillRegistry.load(skills_dir)
graph = DualKnowledgeGraph()
graph.add_financial_data(frame)
graph.add_skill_registry(registry)
engine = FinSkillEngine(graph, registry)
summary = graph.summary()

c1, c2, c3, c4 = st.columns(4)
c1.metric("기업", summary["companies"])
c2.metric("Financial Fact", summary["facts"])
c3.metric("SKILL", summary["skills"])
c4.metric("Skill↔Metric", summary["bridges"])

st.info(
    "기본 데이터는 실행 확인용 sample입니다. 실제 분석은 OpenDART 수집 스크립트로 생성한 CSV를 FINSKILL_DATA에 지정해서 사용합니다."
)

examples = [
    "샘플전자 최근 3년 재무상태 분석해줘",
    "샘플전자 부채비율 알려줘",
    "샘플전자 수익성 변화 알려줘",
    "샘플전자와 샘플메모리 비교해줘",
]

query = st.text_input("질문", value=examples[0])
llm_enabled = all(os.getenv(key, "").strip() for key in ["LLM_API_URL", "LLM_API_KEY", "LLM_MODEL"])
use_llm = st.checkbox("LLM 문장 생성 사용", value=False, disabled=not llm_enabled)
if not llm_enabled:
    st.caption("LLM_API_URL / LLM_API_KEY / LLM_MODEL을 설정하면 같은 근거를 이용해 최종 문장을 생성할 수 있습니다.")

if st.button("분석"):
    result = engine.answer(query)
    answer = result["answer"]
    if use_llm:
        try:
            llm_config = LLMConfig.from_env()
            client = LLMClient(
                llm_config.api_url,
                llm_config.api_key,
                llm_config.model,
                timeout=llm_config.timeout,
            )
            answer = client.render(query, result, registry)
        except Exception as exc:
            st.warning(f"LLM 생성에 실패해 규칙 기반 결과를 표시합니다: {exc}")

    st.subheader("분석 결과")
    st.text(answer)

    with st.expander("실행된 SKILL"):
        for idx, skill_id in enumerate(result["skill_plan"], 1):
            skill = registry.skills[skill_id]
            st.write(f"{idx}. `{skill_id}` — {skill.description}")

    with st.expander("근거"):
        if result["evidence"]:
            st.dataframe(pd.DataFrame(result["evidence"]), use_container_width=True)
        else:
            st.write("표시할 근거가 없습니다.")

overview_tab, financial_tab, skill_tab = st.tabs(["Overview", "Financial KG", "Skill KG"])

with overview_tab:
    st.subheader("구조")
    st.code(
        "User Query\n"
        "   ↓\n"
        "Skill Router → Skill KG → SKILL.md\n"
        "                         ↓\n"
        "                  Financial KG\n"
        "                         ↓\n"
        "                 Evidence Answer",
        language="text",
    )
    st.json(summary)

with financial_tab:
    st.subheader("Financial Fact")
    view = frame.copy()
    view["metric_name"] = view["metric"].map(METRIC_LABELS)
    st.dataframe(
        view[["company_name", "year", "metric_name", "value", "unit", "source_id"]],
        use_container_width=True,
    )

with skill_tab:
    st.subheader("Skill Dependency")
    skill_rows = []
    for skill in registry.skills.values():
        skill_rows.append(
            {
                "skill_id": skill.skill_id,
                "description": skill.description,
                "requires": ", ".join(skill.requires) or "-",
                "consumes": ", ".join(skill.consumes) or "-",
                "produces": ", ".join(skill.produces) or "-",
            }
        )
    st.dataframe(pd.DataFrame(skill_rows), use_container_width=True)

st.caption("Risk Signal은 프로젝트용 단순 규칙이며 투자 판단이나 신용등급을 의미하지 않습니다.")
