from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from src.finskillkg.cohort import load_dart_cohort
from src.finskillkg.config import LLMConfig
from src.finskillkg.engine import FinSkillEngine
from src.finskillkg.evaluation import load_evaluation_tasks
from src.finskillkg.graph import DualKnowledgeGraph
from src.finskillkg.llm import LLMClient
from src.finskillkg.normalize import METRIC_LABELS, load_financial_csv
from src.finskillkg.skills import SkillRegistry


def default_data_path() -> Path:
    configured = os.getenv("FINSKILL_DATA", "").strip()
    if configured:
        return Path(configured)
    dart_path = Path("data/dart_financials.csv")
    return dart_path if dart_path.exists() else Path("data/sample_financials.csv")


st.set_page_config(page_title="FinSKILL-KG", page_icon="📊", layout="wide")
st.title("FinSKILL-KG")
st.caption("Financial KG + Skill KG 기반 근거 추적형 재무분석 및 3-system benchmark")

data_path = default_data_path()
skills_dir = Path("skills")
cohort = load_dart_cohort()
evaluation_tasks = load_evaluation_tasks("data/evaluation_questions.jsonl")

frame = load_financial_csv(data_path)
registry = SkillRegistry.load(skills_dir)
graph = DualKnowledgeGraph()
graph.add_financial_data(frame)
graph.add_skill_registry(registry)
engine = FinSkillEngine(graph, registry)
summary = graph.summary()

loaded_companies = set(graph.company_names())
is_sample = data_path.name == "sample_financials.csv"

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("현재 데이터 기업", summary["companies"])
c2.metric("Financial Fact", summary["facts"])
c3.metric("SKILL", summary["skills"])
c4.metric("DART Cohort", len(cohort.companies))
c5.metric("Evaluation Task", len(evaluation_tasks))

if is_sample:
    st.warning(
        "현재는 실행 확인용 sample data를 사용 중입니다. "
        "`DART_API_KEY`로 15개 기업 데이터를 수집하면 같은 화면과 평가 코드가 실제 DART 데이터로 전환됩니다."
    )
else:
    st.success(f"OpenDART 데이터 사용 중: `{data_path}`")

overview_tab, analysis_tab, evaluation_tab, cohort_tab, graph_tab = st.tabs(
    ["Overview", "Analysis", "Evaluation", "DART Cohort", "KG Explorer"]
)

with overview_tab:
    left, right = st.columns([1.2, 1])
    with left:
        st.subheader("System Flow")
        st.code(
            "User Query\n"
            "   ↓\n"
            "Skill Router ────────────────┐\n"
            "   ↓                         │\n"
            "Skill KG → SKILL.md          │\n"
            "   ↓                         │\n"
            "Financial KG ← OpenDART      │\n"
            "   ↓                         │\n"
            "Python Metric / Trend / Risk │\n"
            "   ↓                         │\n"
            "Evidence-based Answer ◀──────┘",
            language="text",
        )
    with right:
        st.subheader("Evaluation Design")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "system": "LLM Only",
                        "financial_context": "없음",
                        "skill_instruction": "없음",
                        "calculation": "LLM",
                    },
                    {
                        "system": "LLM + Financial KG",
                        "financial_context": "KG fact",
                        "skill_instruction": "없음",
                        "calculation": "LLM",
                    },
                    {
                        "system": "LLM + Skill KG + Financial KG",
                        "financial_context": "KG fact",
                        "skill_instruction": "SKILL.md + dependency",
                        "calculation": "Python",
                    },
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )
        st.caption(
            "동일 질문에 대해 numerical accuracy, evidence F1, skill accuracy, "
            "unsupported rate, latency를 비교합니다."
        )

    st.subheader("Current Graph")
    st.json(summary)

with analysis_tab:
    companies = graph.company_names()
    first_company = companies[0]
    second_company = companies[1] if len(companies) > 1 else companies[0]
    examples = [
        f"{first_company} 최근 3년 재무상태 분석해줘",
        f"{first_company} 부채비율 알려줘",
        f"{first_company} 수익성 변화 알려줘",
        f"{first_company}와 {second_company} 비교해줘",
    ]

    query = st.text_input("질문", value=examples[0])
    llm_enabled = all(
        os.getenv(key, "").strip()
        for key in ["LLM_API_URL", "LLM_API_KEY", "LLM_MODEL"]
    )
    use_llm = st.checkbox(
        "LLM 문장 생성 사용",
        value=False,
        disabled=not llm_enabled,
    )
    if not llm_enabled:
        st.caption(
            "LLM_API_URL / LLM_API_KEY / LLM_MODEL을 설정하면 계산 결과를 "
            "동일한 근거 안에서 문장화할 수 있습니다."
        )

    if st.button("분석", type="primary"):
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

        skill_col, evidence_col = st.columns(2)
        with skill_col:
            st.markdown("#### 실행된 SKILL")
            for idx, skill_id in enumerate(result["skill_plan"], 1):
                skill = registry.skills[skill_id]
                st.write(f"{idx}. `{skill_id}`")
                st.caption(skill.description)
        with evidence_col:
            st.markdown("#### 근거")
            if result["evidence"]:
                st.dataframe(
                    pd.DataFrame(result["evidence"]),
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.write("표시할 근거가 없습니다.")

with evaluation_tab:
    st.subheader("LLM Only vs Financial KG vs Skill KG + Financial KG")
    st.write(
        "36개 질문을 metric, trend, comparison 세 유형으로 나누고 "
        "세 시스템에 동일하게 실행합니다."
    )

    task_frame = pd.DataFrame(
        [
            {
                "task_id": task.task_id,
                "type": task.task_type,
                "companies": ", ".join(task.companies),
                "metric": task.metric,
                "target_skill": task.target_skill,
            }
            for task in evaluation_tasks
        ]
    )
    type_counts = (
        task_frame["type"]
        .value_counts()
        .rename_axis("type")
        .reset_index(name="tasks")
    )
    st.dataframe(type_counts, hide_index=True, use_container_width=True)

    result_path = Path("outputs/evaluation/summary.csv")
    if result_path.exists():
        benchmark = pd.read_csv(result_path)
        st.markdown("#### Latest benchmark")
        st.dataframe(benchmark, hide_index=True, use_container_width=True)
        chart_frame = benchmark.set_index("system")[
            ["numeric_accuracy", "evidence_f1", "skill_accuracy"]
        ]
        st.bar_chart(chart_frame)
    else:
        st.info(
            "아직 benchmark 결과가 없습니다. 실제 DART 데이터와 LLM 설정 후 "
            "`python scripts/run_evaluation.py`를 실행하면 이 탭에 결과가 표시됩니다."
        )

    with st.expander("평가 질문 보기"):
        st.dataframe(task_frame, hide_index=True, use_container_width=True)

with cohort_tab:
    st.subheader("15-company OpenDART Cohort")
    cohort_rows = []
    for company in cohort.companies:
        cohort_rows.append(
            {
                "company": company.name,
                "ticker": company.ticker,
                "sector": company.sector,
                "loaded": "yes" if company.name in loaded_companies else "-",
            }
        )
    st.dataframe(
        pd.DataFrame(cohort_rows),
        hide_index=True,
        use_container_width=True,
    )
    st.caption(f"분석 연도: {', '.join(str(year) for year in cohort.years)}")

with graph_tab:
    financial_tab, skill_tab = st.tabs(["Financial KG", "Skill KG"])
    with financial_tab:
        st.subheader("Financial Fact")
        view = frame.copy()
        view["metric_name"] = view["metric"].map(METRIC_LABELS)
        st.dataframe(
            view[
                [
                    "company_name",
                    "year",
                    "metric_name",
                    "value",
                    "unit",
                    "source_id",
                ]
            ],
            hide_index=True,
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
        st.dataframe(
            pd.DataFrame(skill_rows),
            hide_index=True,
            use_container_width=True,
        )

st.caption(
    "Risk Signal은 프로젝트용 단순 규칙이며 투자 판단이나 신용등급을 의미하지 않습니다."
)
