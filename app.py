from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st

from src.finskillkg.cohort import load_dart_cohort
from src.finskillkg.engine import FinSkillEngine
from src.finskillkg.evaluation import load_evaluation_tasks
from src.finskillkg.graph import DualKnowledgeGraph
from src.finskillkg.llm import LLMClient
from src.finskillkg.normalize import METRIC_LABELS, load_financial_csv
from src.finskillkg.skills import SkillRegistry
from src.finskillkg.visualize import (
    financial_kg_dot,
    skill_detail_dot,
    skill_kg_dot,
)


def _setting(name: str, default: str = "") -> str:
    value = os.getenv(name, "").strip()
    if value:
        return value
    try:
        return str(st.secrets.get(name, default)).strip()
    except Exception:
        return default


def default_data_path() -> Path:
    configured = _setting("FINSKILL_DATA")
    if configured:
        return Path(configured)
    dart_path = Path("data/dart_financials.csv")
    return dart_path if dart_path.exists() else Path("data/sample_financials.csv")


def build_llm_client() -> LLMClient | None:
    api_url = _setting("LLM_API_URL")
    api_key = _setting("LLM_API_KEY")
    model = _setting("LLM_MODEL")
    if not api_url or not api_key or not model:
        return None
    return LLMClient(api_url, api_key, model)


def analyze_query(
    query: str,
    engine: FinSkillEngine,
    registry: SkillRegistry,
    llm_client: LLMClient | None,
    use_llm: bool,
) -> dict:
    result = engine.answer(query)
    answer = result["answer"]
    llm_error = None

    if use_llm and llm_client is not None:
        try:
            answer = llm_client.render(query, result, registry)
        except Exception as exc:
            llm_error = str(exc)

    return {
        "query": query,
        "answer": answer,
        "result": result,
        "llm_error": llm_error,
    }


def render_evidence(evidence: list[dict]) -> None:
    if not evidence:
        st.caption("표시할 근거가 없습니다.")
        return

    view = pd.DataFrame(evidence)
    st.dataframe(view, hide_index=True, use_container_width=True)

    for item in evidence:
        url = str(item.get("source_url", "")).strip()
        if url:
            st.markdown(
                f"- [{item.get('source_name', 'DART source')} "
                f"({item.get('source_id', '')})]({url})"
            )


def render_chat_result(item: dict, registry: SkillRegistry) -> None:
    result = item["result"]

    with st.chat_message("user"):
        st.write(item["query"])

    with st.chat_message("assistant"):
        st.text(item["answer"])
        if item["llm_error"]:
            st.caption(
                "LLM 문장 생성에 실패해 deterministic 결과를 표시했습니다: "
                f"{item['llm_error']}"
            )

        with st.expander("이 답변이 만들어진 과정"):
            left, right = st.columns(2)
            with left:
                st.markdown("**실행된 SKILL**")
                for idx, skill_id in enumerate(result["skill_plan"], 1):
                    skill = registry.skills[skill_id]
                    st.write(f"{idx}. {skill_id}")
                    st.caption(skill.description)
            with right:
                st.markdown("**Evidence**")
                render_evidence(result["evidence"])


st.set_page_config(page_title="FinSKILL-KG", page_icon="📊", layout="wide")
st.title("FinSKILL-KG")
st.caption(
    "Financial KG + Skill KG 기반 근거 추적형 재무분석 데모와 3-system benchmark"
)

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
llm_client = build_llm_client()
summary = graph.summary()

loaded_companies = set(graph.company_names())
companies = graph.company_names()
is_sample = data_path.name == "sample_financials.csv"

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("현재 데이터 기업", summary["companies"])
c2.metric("Financial Fact", summary["facts"])
c3.metric("SKILL", summary["skills"])
c4.metric("DART Cohort", len(cohort.companies))
c5.metric("Evaluation Task", len(evaluation_tasks))

if is_sample:
    st.warning(
        "현재 데모는 실행 확인용 sample data를 사용 중입니다. "
        "data/dart_financials.csv를 생성하면 같은 UI가 실제 OpenDART 데이터로 전환됩니다."
    )
else:
    st.success(f"OpenDART 데이터 사용 중: {data_path}")

(
    overview_tab,
    chat_tab,
    kg_tab,
    skill_explorer_tab,
    evaluation_tab,
    cohort_tab,
) = st.tabs(
    [
        "Overview",
        "Chat Demo",
        "Knowledge Graph",
        "SKILL Explorer",
        "Evaluation",
        "DART Cohort",
    ]
)

with overview_tab:
    left, right = st.columns([1.15, 1])
    with left:
        st.subheader("System Flow")
        st.code(
            "User Question\n"
            "   ↓\n"
            "Skill Router\n"
            "   ↓\n"
            "Skill KG → SKILL.md\n"
            "   ↓           ↘\n"
            "Financial KG ← REQUIRES_METRIC\n"
            "   ↓\n"
            "Python Metric / Trend / Risk\n"
            "   ↓\n"
            "Evidence-based Answer\n"
            "   ↓\n"
            "Optional LLM Rendering",
            language="text",
        )
        st.write(
            "Financial KG는 **무엇을 알고 있는지**, Skill KG는 **어떤 업무를 "
            "어떤 순서로 수행하는지**를 관리합니다. 실제 계산 가능한 수치는 "
            "LLM 대신 Python에서 처리합니다."
        )

    with right:
        st.subheader("Evaluation Design")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "system": "LLM Only",
                        "Financial KG": "X",
                        "Skill KG": "X",
                        "calculation": "LLM",
                    },
                    {
                        "system": "LLM + Financial KG",
                        "Financial KG": "O",
                        "Skill KG": "X",
                        "calculation": "LLM",
                    },
                    {
                        "system": "LLM + Skill KG + Financial KG",
                        "Financial KG": "O",
                        "Skill KG": "O",
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

    st.subheader("Current Dual KG")
    st.json(summary)

with chat_tab:
    st.subheader("Financial KG + SKILL 기반 질문 데모")
    first_company = companies[0]
    second_company = companies[1] if len(companies) > 1 else companies[0]
    examples = [
        f"{first_company} 최근 3년 재무상태 분석해줘",
        f"{first_company} 부채비율 알려줘",
        f"{first_company} 영업이익률 변화 알려줘",
        f"{first_company}와 {second_company} 비교해줘",
    ]
    st.caption("예시: " + " / ".join(examples))

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    option_left, option_right = st.columns([3, 1])
    with option_right:
        use_llm = st.checkbox(
            "LLM 문장화",
            value=False,
            disabled=llm_client is None,
            help="계산 결과와 evidence는 그대로 두고 최종 문장만 LLM이 정리합니다.",
        )
    with option_left:
        if llm_client is None:
            st.caption(
                "LLM 설정이 없어도 KG 조회, 재무 계산, SKILL routing은 모두 동작합니다."
            )
        else:
            st.caption("LLM 연결됨. 필요할 때만 최종 문장화를 켤 수 있습니다.")

    for history_item in st.session_state.chat_history:
        render_chat_result(history_item, registry)

    with st.form("question_form", clear_on_submit=True):
        query = st.text_input(
            "질문 입력",
            placeholder=f"예: {examples[0]}",
        )
        submitted = st.form_submit_button("질문하기", type="primary")

    if submitted:
        query = query.strip()
        if not query:
            st.warning("질문을 입력해 주세요.")
        else:
            item = analyze_query(query, engine, registry, llm_client, use_llm)
            st.session_state.chat_history.append(item)
            st.rerun()

    if st.session_state.chat_history and st.button("대화 초기화"):
        st.session_state.chat_history = []
        st.rerun()

with kg_tab:
    financial_tab, skill_tab = st.tabs(["Financial KG", "Skill KG"])

    with financial_tab:
        st.subheader("Financial KG Sample")
        selected_company = st.selectbox(
            "기업",
            companies,
            key="financial_graph_company",
        )
        company_frame = graph.facts(selected_company)
        available_years = sorted(
            int(value) for value in company_frame["year"].unique()
        )
        selected_year = st.selectbox(
            "사업연도",
            available_years,
            index=len(available_years) - 1,
            key="financial_graph_year",
        )
        st.graphviz_chart(
            financial_kg_dot(graph, selected_company, selected_year),
            use_container_width=True,
        )
        st.caption(
            "Company → FinancialFact → Metric/Period/Report 관계를 실제 로드된 "
            "Financial Fact 기준으로 표시합니다."
        )

        view = company_frame[company_frame["year"] == selected_year].copy()
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
        st.subheader("Skill KG Sample")
        skill_ids = sorted(registry.skills)
        focus_index = (
            skill_ids.index("financial_summary_generation")
            if "financial_summary_generation" in skill_ids
            else 0
        )
        focus_skill = st.selectbox(
            "중심 SKILL",
            skill_ids,
            index=focus_index,
            key="skill_graph_focus",
        )
        st.graphviz_chart(
            skill_kg_dot(registry, focus_skill),
            use_container_width=True,
        )
        st.caption(
            "SKILL 간 REQUIRES dependency와 선택한 SKILL이 필요로 하는 "
            "Financial KG Metric을 함께 표시합니다."
        )

with skill_explorer_tab:
    st.subheader("SKILL Explorer")
    selected_skill_id = st.selectbox(
        "SKILL",
        sorted(registry.skills),
        key="skill_explorer_select",
    )
    selected_skill = registry.skills[selected_skill_id]

    st.graphviz_chart(
        skill_detail_dot(registry, selected_skill_id),
        use_container_width=True,
    )

    metadata_col, instruction_col = st.columns([1, 1.35])
    with metadata_col:
        st.markdown("#### Metadata")
        st.json(
            {
                "skill_id": selected_skill.skill_id,
                "name": selected_skill.name,
                "description": selected_skill.description,
                "requires": list(selected_skill.requires),
                "consumes": list(selected_skill.consumes),
                "produces": list(selected_skill.produces),
                "tools": list(selected_skill.tools),
                "validation": list(selected_skill.validation),
                "required_metrics": list(selected_skill.required_metrics),
            }
        )

    with instruction_col:
        st.markdown("#### SKILL.md")
        st.markdown(selected_skill.body)

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
            "python scripts/run_evaluation.py를 실행하면 이 탭에 결과가 표시됩니다."
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

st.caption(
    "Risk Signal은 프로젝트용 단순 규칙이며 투자 판단이나 신용등급을 의미하지 않습니다."
)
