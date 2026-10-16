from __future__ import annotations

import html
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


APP_TITLE = "FinSKILL-KG"
APP_SUBTITLE = "Financial Knowledge Graph × Skill Orchestration"


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
    if dart_path.exists():
        return dart_path
    return Path("data/sample_financials.csv")


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


def escape_text(value: object) -> str:
    return html.escape(str(value), quote=True)


def render_page_header(
    eyebrow: str,
    title: str,
    description: str,
    badge: str | None = None,
) -> None:
    badge_html = (
        f'<span class="page-badge">{escape_text(badge)}</span>'
        if badge
        else ""
    )
    st.markdown(
        f"""
        <div class="page-heading">
            <div class="page-heading-top">
                <div>
                    <div class="eyebrow">{escape_text(eyebrow)}</div>
                    <h1>{escape_text(title)}</h1>
                </div>
                {badge_html}
            </div>
            <p>{escape_text(description)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_stat_card(label: str, value: object, helper: str = "") -> None:
    helper_html = (
        f'<div class="stat-helper">{escape_text(helper)}</div>'
        if helper
        else ""
    )
    st.markdown(
        f"""
        <div class="stat-card">
            <div class="stat-label">{escape_text(label)}</div>
            <div class="stat-value">{escape_text(value)}</div>
            {helper_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_architecture_card(
    number: str,
    title: str,
    description: str,
    accent: str,
) -> None:
    st.markdown(
        f"""
        <div class="arch-card">
            <div class="arch-step" style="color:{accent};">{escape_text(number)}</div>
            <div class="arch-title">{escape_text(title)}</div>
            <div class="arch-desc">{escape_text(description)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_evidence(evidence: list[dict]) -> None:
    if not evidence:
        st.caption("표시할 근거가 없습니다.")
        return

    for item in evidence:
        source_id = escape_text(item.get("source_id", ""))
        source_name = escape_text(item.get("source_name", "DART source"))
        source_url = str(item.get("source_url", "")).strip()
        link = (
            f'<a href="{escape_text(source_url)}" target="_blank">원문 보기</a>'
            if source_url
            else ""
        )
        st.markdown(
            f"""
            <div class="evidence-row">
                <div>
                    <div class="evidence-name">{source_name}</div>
                    <div class="evidence-id">{source_id}</div>
                </div>
                <div>{link}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_skill_trace(result: dict, registry: SkillRegistry) -> None:
    plan = result.get("skill_plan", [])
    if not plan:
        st.caption("실행된 SKILL이 없습니다.")
        return

    for idx, skill_id in enumerate(plan, 1):
        skill = registry.skills[skill_id]
        st.markdown(
            f"""
            <div class="trace-row">
                <div class="trace-index">{idx:02d}</div>
                <div>
                    <div class="trace-title">{escape_text(skill.name)}</div>
                    <div class="trace-id">{escape_text(skill_id)}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_chat_result(item: dict, registry: SkillRegistry) -> None:
    result = item["result"]

    with st.chat_message("user"):
        st.write(item["query"])

    with st.chat_message("assistant"):
        st.markdown(
            f"""
            <div class="answer-card">
                <div class="answer-kicker">ANALYSIS RESULT</div>
                <div class="answer-body">{escape_text(item["answer"]).replace(chr(10), "<br>")}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if item["llm_error"]:
            st.caption(
                "LLM 문장 생성에 실패해 deterministic 결과를 표시했습니다: "
                f"{item['llm_error']}"
            )

        with st.expander("분석 과정과 근거 보기", expanded=False):
            left, right = st.columns([1, 1])
            with left:
                st.markdown("##### 실행 SKILL")
                render_skill_trace(result, registry)
            with right:
                st.markdown("##### Evidence")
                render_evidence(result["evidence"])


st.set_page_config(
    page_title=APP_TITLE,
    page_icon="◼",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --ink: #111827;
        --muted: #667085;
        --line: #E4E7EC;
        --panel: #FFFFFF;
        --panel-soft: #F8FAFC;
        --navy: #0B1F3A;
        --blue: #2563EB;
        --blue-soft: #EFF6FF;
        --green: #0E9384;
        --green-soft: #ECFDF3;
        --amber: #B54708;
        --amber-soft: #FFFAEB;
    }

    html, body, [class*="css"] {
        font-family: Inter, Pretendard, "Noto Sans KR", -apple-system,
            BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    [data-testid="stAppViewContainer"] {
        background: #F5F7FA;
    }

    [data-testid="stHeader"] {
        background: rgba(245, 247, 250, 0.82);
        backdrop-filter: blur(8px);
    }

    [data-testid="stSidebar"] {
        background: #0B1F3A;
        border-right: 0;
    }

    [data-testid="stSidebar"] * {
        color: #E6ECF5;
    }

    [data-testid="stSidebar"] .stRadio label {
        padding: 0.45rem 0.6rem;
        border-radius: 8px;
    }

    [data-testid="stSidebar"] .stRadio label:hover {
        background: rgba(255,255,255,0.08);
    }

    [data-testid="stSidebar"] hr {
        border-color: rgba(255,255,255,0.10);
    }

    .block-container {
        max-width: 1500px;
        padding-top: 2.2rem;
        padding-bottom: 4rem;
    }

    .brand {
        padding: 0.4rem 0 1.25rem 0;
    }

    .brand-mark {
        width: 32px;
        height: 32px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 9px;
        background: linear-gradient(135deg, #4F8CF7, #18A0AE);
        color: #fff;
        font-weight: 800;
        margin-bottom: 0.8rem;
    }

    .brand-name {
        font-size: 1.12rem;
        font-weight: 760;
        letter-spacing: -0.02em;
        color: #fff;
    }

    .brand-sub {
        font-size: 0.76rem;
        color: #AFC0D6;
        margin-top: 0.25rem;
        line-height: 1.5;
    }

    .side-section {
        font-size: 0.69rem;
        font-weight: 700;
        color: #8498B3;
        letter-spacing: 0.08em;
        margin: 1.2rem 0 0.4rem;
    }

    .side-status {
        margin-top: 1.25rem;
        padding: 0.9rem;
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 12px;
        background: rgba(255,255,255,0.04);
    }

    .status-line {
        display: flex;
        justify-content: space-between;
        gap: 0.5rem;
        font-size: 0.76rem;
        margin-bottom: 0.5rem;
    }

    .status-line:last-child {
        margin-bottom: 0;
    }

    .status-key {
        color: #93A4BA;
    }

    .status-value {
        color: #F3F6FA;
        font-weight: 600;
        text-align: right;
    }

    .page-heading {
        margin-bottom: 1.5rem;
    }

    .page-heading-top {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: flex-start;
    }

    .eyebrow {
        color: #4F6B8A;
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.12em;
        margin-bottom: 0.35rem;
    }

    .page-heading h1 {
        margin: 0;
        color: var(--navy);
        font-size: 2.05rem;
        line-height: 1.16;
        letter-spacing: -0.035em;
    }

    .page-heading p {
        margin: 0.65rem 0 0 0;
        color: var(--muted);
        font-size: 0.95rem;
        line-height: 1.65;
        max-width: 840px;
    }

    .page-badge {
        display: inline-flex;
        align-items: center;
        min-height: 30px;
        padding: 0 0.75rem;
        border-radius: 999px;
        background: #EEF4FF;
        color: #3056D3;
        font-size: 0.74rem;
        font-weight: 700;
        white-space: nowrap;
        border: 1px solid #D6E4FF;
    }

    .hero {
        padding: 2rem 2.1rem;
        border-radius: 18px;
        background:
            radial-gradient(circle at 92% 18%, rgba(91, 153, 255, 0.18), transparent 26%),
            linear-gradient(135deg, #0B1F3A 0%, #102D52 100%);
        color: #fff;
        margin-bottom: 1rem;
        box-shadow: 0 14px 30px rgba(11,31,58,0.12);
    }

    .hero-kicker {
        font-size: 0.73rem;
        font-weight: 800;
        color: #8FB8FF;
        letter-spacing: 0.12em;
    }

    .hero-title {
        margin: 0.55rem 0 0.7rem 0;
        font-size: 2rem;
        line-height: 1.25;
        font-weight: 760;
        letter-spacing: -0.035em;
    }

    .hero-desc {
        max-width: 850px;
        color: #CED9E8;
        line-height: 1.65;
        font-size: 0.94rem;
    }

    .stat-card {
        background: #fff;
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 1rem 1.05rem;
        min-height: 106px;
        box-shadow: 0 2px 6px rgba(16,24,40,0.03);
    }

    .stat-label {
        color: #667085;
        font-size: 0.76rem;
        font-weight: 650;
    }

    .stat-value {
        color: #101828;
        font-size: 1.75rem;
        font-weight: 760;
        margin-top: 0.2rem;
        letter-spacing: -0.03em;
    }

    .stat-helper {
        color: #98A2B3;
        font-size: 0.7rem;
        margin-top: 0.25rem;
    }

    .section-title {
        color: #101828;
        font-size: 1rem;
        font-weight: 760;
        margin: 1.4rem 0 0.7rem 0;
    }

    .panel {
        background: #fff;
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 1.15rem 1.2rem;
        box-shadow: 0 2px 7px rgba(16,24,40,0.03);
    }

    .arch-card {
        min-height: 154px;
        background: #fff;
        border: 1px solid var(--line);
        border-radius: 14px;
        padding: 1rem;
        box-shadow: 0 2px 6px rgba(16,24,40,0.03);
    }

    .arch-step {
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.08em;
    }

    .arch-title {
        margin-top: 0.7rem;
        color: #101828;
        font-size: 0.98rem;
        font-weight: 740;
    }

    .arch-desc {
        margin-top: 0.4rem;
        color: #667085;
        font-size: 0.78rem;
        line-height: 1.55;
    }

    .answer-card {
        background: #FFFFFF;
        border: 1px solid #DDE3EA;
        border-left: 3px solid #2563EB;
        border-radius: 12px;
        padding: 1rem 1.05rem;
    }

    .answer-kicker {
        color: #315FBA;
        font-size: 0.68rem;
        font-weight: 800;
        letter-spacing: 0.1em;
        margin-bottom: 0.45rem;
    }

    .answer-body {
        color: #1D2939;
        line-height: 1.75;
        font-size: 0.93rem;
    }

    .trace-row {
        display: flex;
        gap: 0.7rem;
        align-items: flex-start;
        padding: 0.62rem 0;
        border-bottom: 1px solid #EEF1F4;
    }

    .trace-row:last-child {
        border-bottom: 0;
    }

    .trace-index {
        min-width: 29px;
        height: 29px;
        border-radius: 8px;
        background: #EFF4FF;
        color: #315FBA;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.68rem;
        font-weight: 800;
    }

    .trace-title {
        color: #1D2939;
        font-size: 0.82rem;
        font-weight: 700;
    }

    .trace-id {
        color: #98A2B3;
        font-size: 0.68rem;
        margin-top: 0.12rem;
    }

    .evidence-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
        padding: 0.72rem 0;
        border-bottom: 1px solid #EEF1F4;
    }

    .evidence-row:last-child {
        border-bottom: 0;
    }

    .evidence-name {
        color: #344054;
        font-size: 0.78rem;
        font-weight: 650;
    }

    .evidence-id {
        color: #98A2B3;
        font-size: 0.68rem;
        margin-top: 0.12rem;
    }

    .evidence-row a {
        color: #2563EB;
        font-size: 0.74rem;
        font-weight: 650;
        text-decoration: none;
    }

    [data-testid="stGraphVizChart"] {
        background: #fff;
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 1rem;
        box-shadow: 0 2px 7px rgba(16,24,40,0.03);
    }

    [data-testid="stDataFrame"] {
        border-radius: 14px;
        overflow: hidden;
        border: 1px solid var(--line);
    }

    [data-testid="stExpander"] {
        border: 1px solid var(--line);
        border-radius: 12px;
        background: #fff;
    }

    div[data-testid="stChatMessage"] {
        background: transparent;
    }

    .stButton > button,
    .stFormSubmitButton > button {
        border-radius: 9px;
        font-weight: 700;
    }

    .footer-note {
        margin-top: 2.5rem;
        color: #98A2B3;
        font-size: 0.72rem;
        text-align: right;
    }

    @media (max-width: 900px) {
        .hero {
            padding: 1.5rem;
        }
        .hero-title {
            font-size: 1.55rem;
        }
        .page-heading h1 {
            font-size: 1.65rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
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
data_label = "Sample Data" if is_sample else "OpenDART"
llm_label = "Connected" if llm_client is not None else "Offline"

with st.sidebar:
    st.markdown(
        """
        <div class="brand">
            <div class="brand-mark">F</div>
            <div class="brand-name">FinSKILL-KG</div>
            <div class="brand-sub">Grounded financial analysis with dual knowledge graphs</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="side-section">WORKSPACE</div>', unsafe_allow_html=True)
    page = st.radio(
        "Navigation",
        [
            "Overview",
            "Ask",
            "Knowledge Graph",
            "SKILL Explorer",
            "Evaluation",
            "Dataset",
        ],
        label_visibility="collapsed",
    )

    st.markdown('<div class="side-section">ENVIRONMENT</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="side-status">
            <div class="status-line">
                <span class="status-key">Data</span>
                <span class="status-value">{escape_text(data_label)}</span>
            </div>
            <div class="status-line">
                <span class="status-key">LLM</span>
                <span class="status-value">{escape_text(llm_label)}</span>
            </div>
            <div class="status-line">
                <span class="status-key">Companies</span>
                <span class="status-value">{summary["companies"]}</span>
            </div>
            <div class="status-line">
                <span class="status-key">SKILLs</span>
                <span class="status-value">{summary["skills"]}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


if page == "Overview":
    render_page_header(
        "PROJECT OVERVIEW",
        "재무 데이터를 근거로 분석하는 Dual KG 시스템",
        "Financial KG는 재무 수치와 출처를 관리하고, Skill KG는 질문에 필요한 분석 순서를 관리합니다.",
        badge=data_label,
    )

    st.markdown(
        """
        <div class="hero">
            <div class="hero-kicker">FINANCIAL ANALYSIS COPILOT</div>
            <div class="hero-title">숫자, 분석 절차, 근거를 분리해서 관리합니다.</div>
            <div class="hero-desc">
                OpenDART 재무정보를 Financial KG로 구조화하고, 재무비율 계산과 추세 분석,
                기업 비교 같은 업무는 SKILL 단위로 나눴습니다. 질문이 들어오면 필요한 SKILL을
                선택하고, KG에서 확인된 수치만 사용해 결과를 만듭니다.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    stat_cols = st.columns(5)
    stats = [
        ("Loaded Companies", summary["companies"], "현재 분석 가능한 기업"),
        ("Financial Facts", summary["facts"], "KG에 적재된 재무 수치"),
        ("SKILLs", summary["skills"], "재사용 가능한 분석 단위"),
        ("DART Cohort", len(cohort.companies), "실험 대상 기업"),
        ("Eval Tasks", len(evaluation_tasks), "비교 평가 질문"),
    ]
    for col, (label, value, helper) in zip(stat_cols, stats):
        with col:
            render_stat_card(label, value, helper)

    st.markdown('<div class="section-title">How it works</div>', unsafe_allow_html=True)
    flow_cols = st.columns(4)
    flow = [
        ("01", "Route", "질문에서 기업, 연도, 지표와 분석 유형을 확인합니다.", "#2563EB"),
        ("02", "Plan", "Skill KG에서 필요한 SKILL과 선행 dependency를 정합니다.", "#7F56D9"),
        ("03", "Retrieve", "Financial KG에서 필요한 재무 수치와 출처를 가져옵니다.", "#0E9384"),
        ("04", "Compute", "정해진 재무 공식은 Python으로 계산하고 근거와 함께 반환합니다.", "#B54708"),
    ]
    for col, item in zip(flow_cols, flow):
        with col:
            render_architecture_card(*item)

    st.markdown('<div class="section-title">Evaluation setup</div>', unsafe_allow_html=True)
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "System": "LLM Only",
                    "Financial KG": "No",
                    "Skill KG": "No",
                    "Calculation": "LLM",
                },
                {
                    "System": "LLM + Financial KG",
                    "Financial KG": "Yes",
                    "Skill KG": "No",
                    "Calculation": "LLM",
                },
                {
                    "System": "LLM + Skill KG + Financial KG",
                    "Financial KG": "Yes",
                    "Skill KG": "Yes",
                    "Calculation": "Python",
                },
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )

elif page == "Ask":
    render_page_header(
        "INTERACTIVE DEMO",
        "재무 질문하기",
        "질문을 입력하면 선택된 SKILL, 계산 결과, 사용한 근거를 한 화면에서 확인할 수 있습니다.",
        badge="LLM optional",
    )

    first_company = companies[0]
    second_company = companies[1] if len(companies) > 1 else companies[0]

    preset_col, option_col = st.columns([3, 1])
    with preset_col:
        st.markdown(
            """
            <div class="panel">
                <div class="section-title" style="margin-top:0;">Example questions</div>
                <div style="color:#667085;font-size:0.82rem;line-height:1.9;">
                    재무상태 요약 / 부채비율 계산 / 영업이익률 추세 / 기업 비교
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with option_col:
        use_llm = st.toggle(
            "LLM 문장화",
            value=False,
            disabled=llm_client is None,
            help="계산 결과와 evidence는 유지하고 최종 문장만 LLM이 정리합니다.",
        )

    examples = [
        f"{first_company} 최근 3년 재무상태 분석해줘",
        f"{first_company} 2025년 부채비율 알려줘",
        f"{first_company} 영업이익률 변화 알려줘",
        f"{first_company}와 {second_company} ROE 비교해줘",
    ]

    selected_example = st.selectbox(
        "예시 질문",
        ["직접 입력"] + examples,
        index=0,
    )

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    for history_item in st.session_state.chat_history:
        render_chat_result(history_item, registry)

    with st.form("question_form", clear_on_submit=True):
        default_query = "" if selected_example == "직접 입력" else selected_example
        query = st.text_input(
            "질문",
            value=default_query,
            placeholder="예: 삼성전자 2025년 부채비율 알려줘",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("분석 실행", type="primary")

    if submitted:
        query = query.strip()
        if not query:
            st.warning("질문을 입력해 주세요.")
        else:
            item = analyze_query(query, engine, registry, llm_client, use_llm)
            st.session_state.chat_history.append(item)
            st.rerun()

    if st.session_state.chat_history:
        if st.button("대화 초기화"):
            st.session_state.chat_history = []
            st.rerun()

elif page == "Knowledge Graph":
    render_page_header(
        "GRAPH EXPLORER",
        "Knowledge Graph",
        "Financial KG와 Skill KG를 분리해서 보고, 두 그래프가 어떤 지점에서 연결되는지 확인합니다.",
    )

    graph_view = st.segmented_control(
        "Graph type",
        ["Financial KG", "Skill KG"],
        default="Financial KG",
        label_visibility="collapsed",
    )

    if graph_view == "Financial KG":
        control_left, control_right = st.columns(2)
        with control_left:
            selected_company = st.selectbox("기업", companies)
        company_frame = graph.facts(selected_company)
        available_years = sorted(int(value) for value in company_frame["year"].unique())
        with control_right:
            selected_year = st.selectbox(
                "사업연도",
                available_years,
                index=len(available_years) - 1,
            )

        st.graphviz_chart(
            financial_kg_dot(graph, selected_company, selected_year),
            use_container_width=True,
        )

        view = company_frame[company_frame["year"] == selected_year].copy()
        view["metric_name"] = view["metric"].map(METRIC_LABELS)
        view = view[
            [
                "metric_name",
                "metric",
                "value",
                "unit",
                "source_id",
            ]
        ]
        st.dataframe(view, hide_index=True, use_container_width=True)

    else:
        skill_ids = sorted(registry.skills)
        default_index = (
            skill_ids.index("financial_summary_generation")
            if "financial_summary_generation" in skill_ids
            else 0
        )
        focus_skill = st.selectbox(
            "중심 SKILL",
            skill_ids,
            index=default_index,
        )
        st.caption(registry.skills[focus_skill].description)
        st.graphviz_chart(
            skill_kg_dot(registry, focus_skill),
            use_container_width=True,
        )

elif page == "SKILL Explorer":
    render_page_header(
        "SKILL LIBRARY",
        "SKILL Explorer",
        "각 SKILL의 dependency, input/output, validation 규칙과 실제 SKILL.md 내용을 함께 확인합니다.",
    )

    selected_skill_id = st.selectbox(
        "SKILL",
        sorted(registry.skills),
    )
    selected_skill = registry.skills[selected_skill_id]

    st.markdown(
        f"""
        <div class="panel">
            <div class="eyebrow">SELECTED SKILL</div>
            <div style="font-size:1.15rem;font-weight:760;color:#101828;">
                {escape_text(selected_skill.name)}
            </div>
            <div style="margin-top:0.35rem;color:#667085;font-size:0.82rem;">
                {escape_text(selected_skill.description)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    graph_col, meta_col = st.columns([1.45, 1])
    with graph_col:
        st.graphviz_chart(
            skill_detail_dot(registry, selected_skill_id),
            use_container_width=True,
        )
    with meta_col:
        metadata = pd.DataFrame(
            [
                ("Requires", ", ".join(selected_skill.requires) or "-"),
                ("Consumes", ", ".join(selected_skill.consumes) or "-"),
                ("Produces", ", ".join(selected_skill.produces) or "-"),
                ("Tools", ", ".join(selected_skill.tools) or "-"),
                ("Validation", ", ".join(selected_skill.validation) or "-"),
                ("Metrics", ", ".join(selected_skill.required_metrics) or "-"),
            ],
            columns=["Field", "Value"],
        )
        st.dataframe(metadata, hide_index=True, use_container_width=True)

    with st.expander("SKILL.md 원문 보기", expanded=True):
        st.markdown(selected_skill.body)

elif page == "Evaluation":
    render_page_header(
        "BENCHMARK",
        "Evaluation",
        "동일한 금융 질문을 세 시스템에 적용하고 수치 정확도, 근거, SKILL 선택 성능을 비교합니다.",
        badge=f"{len(evaluation_tasks)} tasks",
    )

    task_frame = pd.DataFrame(
        [
            {
                "Task ID": task.task_id,
                "Type": task.task_type,
                "Companies": ", ".join(task.companies),
                "Metric": task.metric,
                "Target SKILL": task.target_skill,
            }
            for task in evaluation_tasks
        ]
    )

    count_frame = (
        task_frame["Type"]
        .value_counts()
        .rename_axis("Type")
        .reset_index(name="Tasks")
    )

    top_left, top_right = st.columns([1, 2])
    with top_left:
        st.markdown('<div class="section-title">Task distribution</div>', unsafe_allow_html=True)
        st.dataframe(count_frame, hide_index=True, use_container_width=True)
    with top_right:
        st.markdown('<div class="section-title">Evaluation metrics</div>', unsafe_allow_html=True)
        metric_cols = st.columns(5)
        metric_labels = [
            ("Numeric", "Accuracy"),
            ("Evidence", "F1"),
            ("Skill", "Accuracy"),
            ("Unsupported", "Rate"),
            ("Latency", "ms"),
        ]
        for col, (label, value) in zip(metric_cols, metric_labels):
            with col:
                render_stat_card(label, value)

    result_path = Path("outputs/evaluation/summary.csv")
    st.markdown('<div class="section-title">Latest benchmark</div>', unsafe_allow_html=True)

    if result_path.exists():
        benchmark = pd.read_csv(result_path)
        st.dataframe(benchmark, hide_index=True, use_container_width=True)
        chart_frame = benchmark.set_index("system")[
            ["numeric_accuracy", "evidence_f1", "skill_accuracy"]
        ]
        st.bar_chart(chart_frame)
    else:
        st.info(
            "아직 benchmark 결과가 없습니다. 실제 DART 데이터와 LLM 설정 후 "
            "python scripts/run_evaluation.py 를 실행하면 결과가 표시됩니다."
        )

    with st.expander("평가 질문 전체 보기"):
        st.dataframe(task_frame, hide_index=True, use_container_width=True)

elif page == "Dataset":
    render_page_header(
        "DATASET",
        "OpenDART Cohort",
        "실험에 사용하는 15개 기업과 현재 로드된 데이터 상태를 확인합니다.",
        badge="2023–2025",
    )

    cohort_rows = []
    for company in cohort.companies:
        cohort_rows.append(
            {
                "Company": company.name,
                "Ticker": company.ticker,
                "Sector": company.sector,
                "Loaded": "Loaded" if company.name in loaded_companies else "Not loaded",
            }
        )
    cohort_frame = pd.DataFrame(cohort_rows)

    loaded_count = int((cohort_frame["Loaded"] == "Loaded").sum())
    dataset_cols = st.columns(4)
    dataset_stats = [
        ("Target Companies", len(cohort.companies), "고정 cohort"),
        ("Loaded", loaded_count, data_label),
        ("Years", "2023–2025", "사업보고서"),
        ("Financial Facts", summary["facts"], "현재 KG 기준"),
    ]
    for col, item in zip(dataset_cols, dataset_stats):
        with col:
            render_stat_card(*item)

    st.write("")
    st.dataframe(cohort_frame, hide_index=True, use_container_width=True)

st.markdown(
    """
    <div class="footer-note">
        FinSKILL-KG demo · Risk Signal은 프로젝트용 규칙이며 투자 판단이나 신용등급을 의미하지 않습니다.
    </div>
    """,
    unsafe_allow_html=True,
)
