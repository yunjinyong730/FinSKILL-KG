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
from src.finskillkg.metrics import calculate_ratios, format_money
from src.finskillkg.normalize import METRIC_LABELS, load_financial_csv
from src.finskillkg.skills import SkillRegistry
from src.finskillkg.visualize import (
    financial_kg_dot,
    skill_detail_dot,
    skill_kg_dot,
)


APP_TITLE = "FinSKILL-KG"


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
    title: str,
    description: str,
    label: str | None = None,
) -> None:
    label_html = (
        f'<div class="page-label">{escape_text(label)}</div>'
        if label
        else ""
    )
    st.markdown(
        f"""
        <div class="page-header">
            {label_html}
            <div class="page-title-row">
                <h1>{escape_text(title)}</h1>
            </div>
            <p>{escape_text(description)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi(label: str, value: object, note: str = "") -> None:
    note_html = (
        f'<div class="kpi-note">{escape_text(note)}</div>'
        if note
        else ""
    )
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-label">{escape_text(label)}</div>
            <div class="kpi-value">{escape_text(value)}</div>
            {note_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_title(title: str, description: str = "") -> None:
    desc_html = (
        f'<span>{escape_text(description)}</span>'
        if description
        else ""
    )
    st.markdown(
        f"""
        <div class="section-head">
            <strong>{escape_text(title)}</strong>
            {desc_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_pipeline_step(index: str, title: str, description: str) -> None:
    st.markdown(
        f"""
        <div class="pipeline-step">
            <div class="pipeline-index">{escape_text(index)}</div>
            <div class="pipeline-copy">
                <div class="pipeline-title">{escape_text(title)}</div>
                <div class="pipeline-desc">{escape_text(description)}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_status_row(label: str, value: str, status: str = "neutral") -> None:
    st.markdown(
        f"""
        <div class="status-row">
            <span class="status-label">{escape_text(label)}</span>
            <span class="status-value status-{escape_text(status)}">{escape_text(value)}</span>
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
            f'<a href="{escape_text(source_url)}" target="_blank">원문</a>'
            if source_url
            else ""
        )
        st.markdown(
            f"""
            <div class="source-row">
                <div>
                    <div class="source-name">{source_name}</div>
                    <div class="source-id">{source_id}</div>
                </div>
                <div class="source-link">{link}</div>
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
                <div class="trace-index">{idx}</div>
                <div class="trace-copy">
                    <div class="trace-title">{escape_text(skill.name)}</div>
                    <div class="trace-id">{escape_text(skill_id)}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_research_result(item: dict, registry: SkillRegistry) -> None:
    result = item["result"]
    answer_html = escape_text(item["answer"]).replace(chr(10), "<br>")

    st.markdown(
        f"""
        <div class="research-result">
            <div class="research-query-label">Query</div>
            <div class="research-query">{escape_text(item["query"])}</div>
            <div class="result-rule"></div>
            <div class="research-result-label">Result</div>
            <div class="research-answer">{answer_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if item["llm_error"]:
        st.caption(
            "LLM 문장 생성에 실패해 deterministic 결과를 표시했습니다: "
            f"{item['llm_error']}"
        )

    detail_left, detail_right = st.columns([1, 1])
    with detail_left:
        st.markdown('<div class="detail-panel">', unsafe_allow_html=True)
        render_section_title("Execution trace", "실행된 SKILL 순서")
        render_skill_trace(result, registry)
        st.markdown("</div>", unsafe_allow_html=True)

    with detail_right:
        st.markdown('<div class="detail-panel">', unsafe_allow_html=True)
        render_section_title("Evidence", "답변에 사용한 공시 근거")
        render_evidence(result.get("evidence", []))
        st.markdown("</div>", unsafe_allow_html=True)


def latest_company_snapshot(
    graph: DualKnowledgeGraph,
    company_name: str,
) -> tuple[int, pd.DataFrame, dict[str, float | None]]:
    company_frame = graph.facts(company_name)
    latest_year = int(company_frame["year"].max())
    latest_frame = company_frame[company_frame["year"] == latest_year].copy()
    latest_facts = {
        row.metric: float(row.value)
        for row in latest_frame.itertuples(index=False)
    }

    previous_frame = company_frame[company_frame["year"] < latest_year]
    previous_facts: dict[str, float] = {}
    if not previous_frame.empty:
        previous_year = int(previous_frame["year"].max())
        previous_facts = {
            row.metric: float(row.value)
            for row in previous_frame[previous_frame["year"] == previous_year].itertuples(
                index=False
            )
        }

    ratios = calculate_ratios(latest_facts, previous_facts)
    return latest_year, latest_frame, ratios


def metric_value(
    frame: pd.DataFrame,
    metric: str,
) -> tuple[float | None, str]:
    rows = frame[frame["metric"] == metric]
    if rows.empty:
        return None, "KRW"
    row = rows.iloc[0]
    return float(row["value"]), str(row["unit"])


def format_ratio(value: float | None) -> str:
    return "—" if value is None else f"{value:,.1f}%"


st.set_page_config(
    page_title=APP_TITLE,
    page_icon="F",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    :root {
        --canvas: #F6F7F9;
        --surface: #FFFFFF;
        --surface-subtle: #FAFBFC;
        --ink: #18202A;
        --ink-strong: #10161D;
        --muted: #66717F;
        --muted-2: #8A94A3;
        --line: #E2E6EA;
        --line-strong: #D5DAE0;
        --nav: #101820;
        --nav-soft: #17222D;
        --nav-text: #D7DEE6;
        --nav-muted: #7F8C9A;
        --accent: #315FBA;
        --accent-soft: #EEF3FB;
        --positive: #247B5A;
        --warning: #9A6700;
    }

    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans KR",
            sans-serif;
        color: var(--ink);
    }

    [data-testid="stAppViewContainer"] {
        background: var(--canvas);
    }

    [data-testid="stHeader"] {
        background: rgba(246, 247, 249, 0.92);
        backdrop-filter: blur(8px);
        border-bottom: 1px solid rgba(226, 230, 234, 0.7);
    }

    [data-testid="stSidebar"] {
        background: var(--nav);
        border-right: 1px solid #0B1117;
    }

    [data-testid="stSidebar"] > div:first-child {
        padding-top: 1.3rem;
    }

    [data-testid="stSidebar"] * {
        color: var(--nav-text);
    }

    [data-testid="stSidebar"] .stRadio > label {
        display: none;
    }

    [data-testid="stSidebar"] .stRadio div[role="radiogroup"] {
        gap: 0.18rem;
    }

    [data-testid="stSidebar"] .stRadio label {
        min-height: 38px;
        padding: 0.45rem 0.65rem;
        border-radius: 6px;
        transition: background 120ms ease;
    }

    [data-testid="stSidebar"] .stRadio label:hover {
        background: var(--nav-soft);
    }

    [data-testid="stSidebar"] .stRadio label p {
        font-size: 0.82rem;
        font-weight: 540;
    }

    .block-container {
        max-width: 1440px;
        padding-top: 2.4rem;
        padding-bottom: 4rem;
    }

    .brand {
        padding: 0.1rem 0.25rem 1.3rem 0.25rem;
        border-bottom: 1px solid rgba(255,255,255,0.08);
        margin-bottom: 1rem;
    }

    .brand-row {
        display: flex;
        align-items: center;
        gap: 0.62rem;
    }

    .brand-mark {
        width: 28px;
        height: 28px;
        border: 1px solid rgba(255,255,255,0.24);
        border-radius: 5px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #FFFFFF;
        font-size: 0.78rem;
        font-weight: 760;
    }

    .brand-name {
        color: #F4F7FA;
        font-size: 0.96rem;
        font-weight: 680;
        letter-spacing: -0.01em;
    }

    .brand-caption {
        margin-top: 0.42rem;
        color: var(--nav-muted);
        font-size: 0.69rem;
        line-height: 1.45;
    }

    .sidebar-label {
        margin: 1rem 0.25rem 0.4rem;
        color: var(--nav-muted);
        font-size: 0.62rem;
        font-weight: 700;
        letter-spacing: 0.09em;
        text-transform: uppercase;
    }

    .sidebar-status {
        margin-top: 1.2rem;
        padding: 0.8rem 0.78rem;
        border-top: 1px solid rgba(255,255,255,0.08);
    }

    .sidebar-status-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.75rem;
        padding: 0.27rem 0;
        font-size: 0.68rem;
    }

    .sidebar-status-key {
        color: var(--nav-muted);
    }

    .sidebar-status-value {
        color: #E9EEF3;
        font-weight: 600;
        text-align: right;
    }

    .page-header {
        padding-bottom: 1.3rem;
        margin-bottom: 1.5rem;
        border-bottom: 1px solid var(--line);
    }

    .page-label {
        margin-bottom: 0.45rem;
        color: var(--accent);
        font-size: 0.64rem;
        font-weight: 760;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .page-title-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
    }

    .page-header h1 {
        margin: 0;
        color: var(--ink-strong);
        font-size: 1.8rem;
        line-height: 1.2;
        font-weight: 690;
        letter-spacing: -0.032em;
    }

    .page-header p {
        margin: 0.5rem 0 0 0;
        max-width: 820px;
        color: var(--muted);
        font-size: 0.86rem;
        line-height: 1.65;
    }

    .toolbar {
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 0.45rem;
        margin-bottom: 1.1rem;
    }

    .toolbar-chip {
        display: inline-flex;
        align-items: center;
        min-height: 28px;
        padding: 0 0.62rem;
        border: 1px solid var(--line);
        border-radius: 5px;
        background: var(--surface);
        color: #4C5867;
        font-size: 0.69rem;
        font-weight: 560;
    }

    .toolbar-chip strong {
        color: var(--ink);
        margin-left: 0.28rem;
        font-weight: 650;
    }

    .kpi-card {
        min-height: 92px;
        padding: 0.88rem 0.95rem;
        border: 1px solid var(--line);
        border-radius: 7px;
        background: var(--surface);
    }

    .kpi-label {
        color: var(--muted);
        font-size: 0.69rem;
        font-weight: 600;
    }

    .kpi-value {
        margin-top: 0.33rem;
        color: var(--ink-strong);
        font-size: 1.43rem;
        font-weight: 680;
        letter-spacing: -0.025em;
        line-height: 1.15;
    }

    .kpi-note {
        margin-top: 0.25rem;
        color: var(--muted-2);
        font-size: 0.64rem;
    }

    .workspace-panel,
    .detail-panel {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 7px;
    }

    .workspace-panel {
        padding: 1rem 1.05rem;
    }

    .detail-panel {
        padding: 0.95rem 1rem;
        min-height: 100%;
    }

    .section-head {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 1rem;
        margin: 0 0 0.78rem 0;
        padding-bottom: 0.58rem;
        border-bottom: 1px solid #EDF0F2;
    }

    .section-head strong {
        color: var(--ink-strong);
        font-size: 0.82rem;
        font-weight: 680;
    }

    .section-head span {
        color: var(--muted-2);
        font-size: 0.65rem;
        text-align: right;
    }

    .pipeline-step {
        display: flex;
        align-items: flex-start;
        gap: 0.72rem;
        padding: 0.76rem 0;
        border-bottom: 1px solid #EDF0F2;
    }

    .pipeline-step:last-child {
        border-bottom: 0;
    }

    .pipeline-index {
        width: 24px;
        min-width: 24px;
        height: 24px;
        border: 1px solid #C9D5E7;
        border-radius: 4px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--accent);
        background: #F7F9FC;
        font-size: 0.62rem;
        font-weight: 760;
    }

    .pipeline-title {
        color: var(--ink);
        font-size: 0.78rem;
        font-weight: 650;
    }

    .pipeline-desc {
        margin-top: 0.16rem;
        color: var(--muted);
        font-size: 0.68rem;
        line-height: 1.5;
    }

    .status-row {
        display: flex;
        justify-content: space-between;
        gap: 0.8rem;
        padding: 0.62rem 0;
        border-bottom: 1px solid #EDF0F2;
        font-size: 0.72rem;
    }

    .status-row:last-child {
        border-bottom: 0;
    }

    .status-label {
        color: var(--muted);
    }

    .status-value {
        font-weight: 650;
    }

    .status-neutral {
        color: var(--ink);
    }

    .status-good {
        color: var(--positive);
    }

    .status-warning {
        color: var(--warning);
    }

    .research-shell {
        max-width: 1040px;
        margin: 0 auto;
    }

    .research-intro {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 7px;
        padding: 1rem 1.05rem;
        margin-bottom: 0.8rem;
    }

    .research-intro strong {
        display: block;
        color: var(--ink-strong);
        font-size: 0.8rem;
        margin-bottom: 0.24rem;
    }

    .research-intro span {
        color: var(--muted);
        font-size: 0.72rem;
        line-height: 1.55;
    }

    .research-result {
        margin-top: 1rem;
        padding: 1.05rem 1.1rem;
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 7px;
    }

    .research-query-label,
    .research-result-label {
        color: var(--muted-2);
        font-size: 0.62rem;
        font-weight: 760;
        letter-spacing: 0.07em;
        text-transform: uppercase;
    }

    .research-query {
        margin-top: 0.3rem;
        color: var(--ink-strong);
        font-size: 0.94rem;
        font-weight: 610;
        line-height: 1.55;
    }

    .result-rule {
        height: 1px;
        background: #EDF0F2;
        margin: 0.85rem 0;
    }

    .research-answer {
        margin-top: 0.38rem;
        color: #2C3642;
        font-size: 0.86rem;
        line-height: 1.78;
    }

    .trace-row {
        display: flex;
        gap: 0.62rem;
        align-items: flex-start;
        padding: 0.56rem 0;
        border-bottom: 1px solid #EDF0F2;
    }

    .trace-row:last-child {
        border-bottom: 0;
    }

    .trace-index {
        width: 22px;
        min-width: 22px;
        height: 22px;
        border-radius: 4px;
        background: var(--accent-soft);
        color: var(--accent);
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.61rem;
        font-weight: 760;
    }

    .trace-title {
        color: var(--ink);
        font-size: 0.73rem;
        font-weight: 650;
    }

    .trace-id {
        margin-top: 0.1rem;
        color: var(--muted-2);
        font-size: 0.61rem;
        line-height: 1.4;
    }

    .source-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.7rem;
        padding: 0.58rem 0;
        border-bottom: 1px solid #EDF0F2;
    }

    .source-row:last-child {
        border-bottom: 0;
    }

    .source-name {
        color: var(--ink);
        font-size: 0.72rem;
        font-weight: 620;
    }

    .source-id {
        margin-top: 0.1rem;
        color: var(--muted-2);
        font-size: 0.61rem;
    }

    .source-link a {
        color: var(--accent);
        font-size: 0.66rem;
        font-weight: 650;
        text-decoration: none;
    }

    .company-heading {
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        gap: 1rem;
        margin-bottom: 0.8rem;
    }

    .company-name {
        color: var(--ink-strong);
        font-size: 1.08rem;
        font-weight: 680;
        letter-spacing: -0.02em;
    }

    .company-meta {
        margin-top: 0.18rem;
        color: var(--muted-2);
        font-size: 0.66rem;
    }

    .company-year {
        color: var(--muted);
        font-size: 0.68rem;
        white-space: nowrap;
    }

    [data-testid="stGraphVizChart"] {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 7px;
        padding: 0.75rem;
    }

    [data-testid="stDataFrame"] {
        border: 1px solid var(--line);
        border-radius: 7px;
        overflow: hidden;
        background: var(--surface);
    }

    [data-testid="stExpander"] {
        border: 1px solid var(--line);
        border-radius: 7px;
        background: var(--surface);
    }

    [data-testid="stSelectbox"] label,
    [data-testid="stTextInput"] label,
    [data-testid="stCheckbox"] label {
        color: var(--muted);
        font-size: 0.7rem;
        font-weight: 600;
    }

    .stButton > button,
    .stFormSubmitButton > button {
        min-height: 38px;
        border-radius: 6px;
        box-shadow: none;
        font-size: 0.78rem;
        font-weight: 650;
    }

    .stButton > button[kind="primary"],
    .stFormSubmitButton > button[kind="primary"] {
        background: #244F95;
        border-color: #244F95;
    }

    div[data-testid="stMetric"] {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 7px;
        padding: 0.7rem 0.85rem;
    }

    .stAlert {
        border-radius: 7px;
    }

    footer {
        visibility: hidden;
    }


    .cover-shell {
        background: var(--surface);
        border: 1px solid var(--line);
        border-radius: 10px;
        overflow: hidden;
        margin-bottom: 1.05rem;
    }

    .cover-grid {
        display: grid;
        grid-template-columns: minmax(0, 1.18fr) minmax(380px, 0.82fr);
        min-height: 520px;
    }

    .cover-copy {
        padding: 4.3rem 4.2rem 3.8rem 4.2rem;
        display: flex;
        flex-direction: column;
        justify-content: center;
        border-right: 1px solid var(--line);
    }

    .cover-label {
        color: var(--accent);
        font-size: 0.66rem;
        font-weight: 760;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-bottom: 1.05rem;
    }

    .cover-title {
        margin: 0;
        max-width: 760px;
        color: #111820;
        font-size: clamp(2.7rem, 4.6vw, 4.8rem);
        line-height: 1.04;
        letter-spacing: -0.055em;
        font-weight: 690;
    }

    .cover-title em {
        font-style: normal;
        color: #244F95;
    }

    .cover-description {
        margin-top: 1.55rem;
        max-width: 680px;
        color: #5E6977;
        font-size: 0.98rem;
        line-height: 1.78;
        word-break: keep-all;
    }

    .cover-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 2rem;
    }

    .cover-meta span {
        min-height: 30px;
        display: inline-flex;
        align-items: center;
        padding: 0 0.68rem;
        border: 1px solid var(--line);
        border-radius: 5px;
        color: #576372;
        background: #FAFBFC;
        font-size: 0.68rem;
        font-weight: 600;
    }

    .cover-preview {
        background: #F1F4F7;
        padding: 2rem;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .product-window {
        width: 100%;
        max-width: 480px;
        background: #FFFFFF;
        border: 1px solid #D8DEE5;
        border-radius: 8px;
        box-shadow: 0 18px 45px rgba(16, 24, 32, 0.08);
        overflow: hidden;
    }

    .product-window-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.8rem;
        min-height: 42px;
        padding: 0 0.8rem;
        border-bottom: 1px solid #E7EAEE;
        background: #FAFBFC;
    }

    .window-dots {
        display: flex;
        gap: 5px;
    }

    .window-dots i {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: #C8CED6;
        display: block;
    }

    .window-title {
        color: #6F7B89;
        font-size: 0.62rem;
        font-weight: 650;
    }

    .product-window-body {
        padding: 1.05rem;
    }

    .preview-query {
        padding: 0.8rem 0.85rem;
        border: 1px solid #E1E6EA;
        border-radius: 6px;
        background: #FFFFFF;
    }

    .preview-kicker {
        color: #8A94A3;
        font-size: 0.58rem;
        font-weight: 760;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .preview-question {
        margin-top: 0.35rem;
        color: #18202A;
        font-size: 0.79rem;
        font-weight: 620;
        line-height: 1.55;
    }

    .preview-flow {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 0.45rem;
        margin: 0.8rem 0;
    }

    .preview-node {
        padding: 0.58rem 0.4rem;
        border: 1px solid #E1E6EA;
        border-radius: 5px;
        background: #F9FAFB;
        text-align: center;
    }

    .preview-node b {
        display: block;
        color: #293340;
        font-size: 0.62rem;
        font-weight: 680;
    }

    .preview-node span {
        display: block;
        margin-top: 0.12rem;
        color: #8A94A3;
        font-size: 0.52rem;
    }

    .preview-answer {
        border-left: 2px solid #315FBA;
        padding: 0.78rem 0.8rem;
        background: #F7F9FC;
    }

    .preview-answer strong {
        display: block;
        color: #27313D;
        font-size: 0.67rem;
        margin-bottom: 0.3rem;
    }

    .preview-answer p {
        margin: 0;
        color: #596575;
        font-size: 0.64rem;
        line-height: 1.55;
    }

    .preview-sources {
        display: flex;
        justify-content: space-between;
        gap: 0.7rem;
        margin-top: 0.75rem;
        padding-top: 0.68rem;
        border-top: 1px solid #EDF0F2;
        color: #8A94A3;
        font-size: 0.54rem;
    }

    .home-actions {
        margin: 0.15rem 0 1.7rem;
    }

    .home-actions [data-testid="stButton"] button {
        min-height: 42px;
    }

    .home-strip {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--surface);
        overflow: hidden;
        margin: 1.1rem 0 1.4rem;
    }

    .home-strip-item {
        padding: 1.25rem 1.35rem;
        border-right: 1px solid var(--line);
    }

    .home-strip-item:last-child {
        border-right: 0;
    }

    .home-strip-index {
        color: #8A94A3;
        font-size: 0.6rem;
        font-weight: 760;
        letter-spacing: 0.08em;
    }

    .home-strip-title {
        margin-top: 0.48rem;
        color: #18202A;
        font-size: 0.86rem;
        font-weight: 670;
    }

    .home-strip-desc {
        margin-top: 0.3rem;
        color: #6D7886;
        font-size: 0.7rem;
        line-height: 1.55;
    }

    .home-section {
        margin-top: 2.4rem;
    }

    .home-section-head {
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        gap: 1rem;
        padding-bottom: 0.8rem;
        margin-bottom: 0.9rem;
        border-bottom: 1px solid var(--line);
    }

    .home-section-head h2 {
        margin: 0;
        color: #111820;
        font-size: 1.24rem;
        font-weight: 680;
        letter-spacing: -0.025em;
    }

    .home-section-head p {
        margin: 0;
        color: #7B8592;
        font-size: 0.69rem;
    }

    .entry-card {
        min-height: 182px;
        padding: 1.2rem 1.2rem 1.1rem;
        border: 1px solid var(--line);
        border-radius: 7px;
        background: var(--surface);
    }

    .entry-eyebrow {
        color: var(--accent);
        font-size: 0.6rem;
        font-weight: 760;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .entry-title {
        margin-top: 1rem;
        color: #18202A;
        font-size: 1rem;
        font-weight: 680;
        letter-spacing: -0.015em;
    }

    .entry-desc {
        margin-top: 0.42rem;
        color: #697482;
        font-size: 0.72rem;
        line-height: 1.6;
    }

    .entry-meta {
        margin-top: 1.15rem;
        padding-top: 0.7rem;
        border-top: 1px solid #EDF0F2;
        color: #8A94A3;
        font-size: 0.62rem;
    }

    .home-architecture {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        border: 1px solid var(--line);
        border-radius: 8px;
        overflow: hidden;
        background: #FFFFFF;
    }

    .home-architecture-item {
        position: relative;
        padding: 1.3rem 1.1rem;
        border-right: 1px solid var(--line);
        min-height: 142px;
    }

    .home-architecture-item:last-child {
        border-right: 0;
    }

    .home-architecture-item b {
        display: block;
        color: #1D2732;
        font-size: 0.78rem;
        font-weight: 680;
    }

    .home-architecture-item span {
        display: block;
        margin-top: 0.35rem;
        color: #7A8592;
        font-size: 0.65rem;
        line-height: 1.5;
    }

    .home-architecture-item small {
        position: absolute;
        left: 1.1rem;
        bottom: 1rem;
        color: #A0A8B2;
        font-size: 0.56rem;
        font-weight: 700;
        letter-spacing: 0.06em;
    }

    .home-footer-band {
        margin-top: 2.4rem;
        padding: 1.5rem 1.55rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 1rem;
        border-top: 1px solid var(--line);
        border-bottom: 1px solid var(--line);
    }

    .home-footer-band strong {
        color: #18202A;
        font-size: 0.86rem;
    }

    .home-footer-band span {
        color: #7A8592;
        font-size: 0.68rem;
    }

    [data-testid="stToolbar"] {
        visibility: hidden;
        height: 0;
    }

    #MainMenu {
        visibility: hidden;
    }

    @media (max-width: 900px) {
        .block-container {
            padding-top: 1.6rem;
        }

        .page-header h1 {
            font-size: 1.5rem;
        }

        .kpi-value {
            font-size: 1.18rem;
        }

        .cover-grid {
            grid-template-columns: 1fr;
        }

        .cover-copy {
            padding: 2.6rem 1.7rem 2.2rem;
            border-right: 0;
            border-bottom: 1px solid var(--line);
        }

        .cover-preview {
            padding: 1.5rem;
        }

        .cover-title {
            font-size: 2.55rem;
        }

        .home-strip,
        .home-architecture {
            grid-template-columns: 1fr;
        }

        .home-strip-item,
        .home-architecture-item {
            border-right: 0;
            border-bottom: 1px solid var(--line);
        }

        .home-strip-item:last-child,
        .home-architecture-item:last-child {
            border-bottom: 0;
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
data_label = "Sample" if is_sample else "OpenDART"
llm_label = "Connected" if llm_client is not None else "Off"


with st.sidebar:
    st.markdown(
        """
        <div class="brand">
            <div class="brand-row">
                <div class="brand-mark">F</div>
                <div class="brand-name">FinSKILL-KG</div>
            </div>
            <div class="brand-caption">Financial research workspace</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="sidebar-label">Research</div>', unsafe_allow_html=True)
    page = st.radio(
        "Navigation",
        [
            "Home",
            "Overview",
            "Ask",
            "Knowledge Graph",
            "SKILL Explorer",
            "Evaluation",
            "Dataset",
        ],
        key="nav_page",
        label_visibility="collapsed",
    )

    st.markdown(
        f"""
        <div class="sidebar-status">
            <div class="sidebar-status-row">
                <span class="sidebar-status-key">Data</span>
                <span class="sidebar-status-value">{escape_text(data_label)}</span>
            </div>
            <div class="sidebar-status-row">
                <span class="sidebar-status-key">LLM</span>
                <span class="sidebar-status-value">{escape_text(llm_label)}</span>
            </div>
            <div class="sidebar-status-row">
                <span class="sidebar-status-key">Companies</span>
                <span class="sidebar-status-value">{summary["companies"]}</span>
            </div>
            <div class="sidebar-status-row">
                <span class="sidebar-status-key">SKILLs</span>
                <span class="sidebar-status-value">{summary["skills"]}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


if page == "Home":
    st.markdown(
        f"""
        <div class="cover-shell">
            <div class="cover-grid">
                <section class="cover-copy">
                    <div class="cover-label">Financial intelligence, grounded in disclosure data</div>
                    <h1 class="cover-title">공시 데이터에서<br><em>근거 있는 재무 분석</em>까지.</h1>
                    <div class="cover-description">
                        OpenDART 재무정보를 Financial KG로 구조화하고, 분석 업무는 SKILL 단위로 분리했습니다.
                        질문에 필요한 데이터와 계산 과정을 추적할 수 있어 결과뿐 아니라 근거까지 함께 확인할 수 있습니다.
                    </div>
                    <div class="cover-meta">
                        <span>{summary["companies"]} companies loaded</span>
                        <span>{summary["facts"]} financial facts</span>
                        <span>{summary["skills"]} reusable SKILLs</span>
                        <span>{len(evaluation_tasks)} evaluation tasks</span>
                    </div>
                </section>
                <aside class="cover-preview">
                    <div class="product-window">
                        <div class="product-window-top">
                            <div class="window-dots"><i></i><i></i><i></i></div>
                            <div class="window-title">FinSKILL-KG / Research Query</div>
                        </div>
                        <div class="product-window-body">
                            <div class="preview-query">
                                <div class="preview-kicker">Query</div>
                                <div class="preview-question">삼성전자 2025년 부채비율과 근거를 보여줘</div>
                            </div>
                            <div class="preview-flow">
                                <div class="preview-node"><b>Route</b><span>intent</span></div>
                                <div class="preview-node"><b>Skill KG</b><span>plan</span></div>
                                <div class="preview-node"><b>Financial KG</b><span>facts</span></div>
                                <div class="preview-node"><b>Python</b><span>compute</span></div>
                            </div>
                            <div class="preview-answer">
                                <strong>Evidence-based result</strong>
                                <p>공시에서 확인된 부채와 자본 값을 사용해 부채비율을 계산하고, 사용한 사업보고서 출처를 함께 반환합니다.</p>
                            </div>
                            <div class="preview-sources">
                                <span>Source · OpenDART</span>
                                <span>Trace · 3 SKILLs</span>
                            </div>
                        </div>
                    </div>
                </aside>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    action_left, action_mid, action_right, action_space = st.columns([1.25, 1.05, 1.15, 4.1])
    with action_left:
        st.button(
            "재무 질문 시작",
            type="primary",
            use_container_width=True,
            on_click=lambda: st.session_state.update(nav_page="Ask"),
        )
    with action_mid:
        st.button(
            "기업 대시보드",
            use_container_width=True,
            on_click=lambda: st.session_state.update(nav_page="Overview"),
        )
    with action_right:
        st.button(
            "KG 살펴보기",
            use_container_width=True,
            on_click=lambda: st.session_state.update(nav_page="Knowledge Graph"),
        )

    st.markdown(
        """
        <div class="home-strip">
            <div class="home-strip-item">
                <div class="home-strip-index">01 / DATA</div>
                <div class="home-strip-title">확인된 재무 수치만 사용</div>
                <div class="home-strip-desc">Financial Fact를 기업, 연도, 지표, 공시 출처와 함께 저장해 숫자의 출처를 다시 확인할 수 있습니다.</div>
            </div>
            <div class="home-strip-item">
                <div class="home-strip-index">02 / PROCESS</div>
                <div class="home-strip-title">분석 절차를 SKILL로 분리</div>
                <div class="home-strip-desc">계산, 추세, 비교, 리스크 분석을 작은 실행 단위로 나누고 Skill KG에서 dependency를 관리합니다.</div>
            </div>
            <div class="home-strip-item">
                <div class="home-strip-index">03 / OUTPUT</div>
                <div class="home-strip-title">결과와 실행 근거를 함께 제공</div>
                <div class="home-strip-desc">최종 답변만 보여주지 않고 실행된 SKILL, 사용한 Financial Fact와 DART 출처까지 같이 남깁니다.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="home-section">
            <div class="home-section-head">
                <h2>Workspace</h2>
                <p>프로젝트에서 실제로 확인할 수 있는 기능</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    feature_cols = st.columns(3)
    feature_items = [
        (
            "RESEARCH",
            "Ask",
            "자연어 질문을 입력하고 계산 결과, 실행된 SKILL, 공시 Evidence를 한 화면에서 확인합니다.",
            "Metric · Trend · Comparison · Summary",
        ),
        (
            "GRAPH",
            "Knowledge Graph",
            "기업의 Financial Fact와 SKILL dependency를 각각 탐색하고 두 그래프가 연결되는 지점을 확인합니다.",
            "Financial KG · Skill KG",
        ),
        (
            "BENCHMARK",
            "Evaluation",
            "LLM Only와 KG 기반 시스템을 동일한 질문셋으로 비교해 수치 정확도와 근거성을 평가합니다.",
            "36 tasks · 5 metrics",
        ),
    ]
    for col, item in zip(feature_cols, feature_items):
        with col:
            st.markdown(
                f"""
                <div class="entry-card">
                    <div class="entry-eyebrow">{item[0]}</div>
                    <div class="entry-title">{item[1]}</div>
                    <div class="entry-desc">{item[2]}</div>
                    <div class="entry-meta">{item[3]}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown(
        """
        <div class="home-section">
            <div class="home-section-head">
                <h2>From question to evidence</h2>
                <p>숫자 계산은 LLM이 아니라 정해진 도구에서 처리합니다.</p>
            </div>
            <div class="home-architecture">
                <div class="home-architecture-item">
                    <b>User Question</b>
                    <span>기업, 연도, 지표와 분석 의도를 입력합니다.</span>
                    <small>INPUT</small>
                </div>
                <div class="home-architecture-item">
                    <b>Skill Router</b>
                    <span>질문에 맞는 target SKILL을 선택합니다.</span>
                    <small>ROUTE</small>
                </div>
                <div class="home-architecture-item">
                    <b>Skill KG</b>
                    <span>선행 SKILL과 필요한 재무지표를 계획합니다.</span>
                    <small>PLAN</small>
                </div>
                <div class="home-architecture-item">
                    <b>Financial KG</b>
                    <span>OpenDART에서 확인된 Financial Fact를 조회합니다.</span>
                    <small>RETRIEVE</small>
                </div>
                <div class="home-architecture-item">
                    <b>Evidence Result</b>
                    <span>Python 계산 결과와 공시 출처를 함께 반환합니다.</span>
                    <small>OUTPUT</small>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="home-footer-band">
            <div>
                <strong>Current data environment</strong><br>
                <span>{escape_text(data_label)} · {summary["companies"]} companies · 2023–2025</span>
            </div>
            <span>FinSKILL-KG research prototype</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

elif page == "Overview":
    render_page_header(
        "Financial Research Workspace",
        "OpenDART 재무정보와 분석 절차를 분리해 관리하고, 질문부터 계산 근거까지 한 흐름에서 확인합니다.",
        "Workspace",
    )

    st.markdown(
        f"""
        <div class="toolbar">
            <span class="toolbar-chip">Data <strong>{escape_text(data_label)}</strong></span>
            <span class="toolbar-chip">Companies <strong>{summary["companies"]}</strong></span>
            <span class="toolbar-chip">Financial Facts <strong>{summary["facts"]}</strong></span>
            <span class="toolbar-chip">SKILLs <strong>{summary["skills"]}</strong></span>
            <span class="toolbar-chip">Evaluation <strong>{len(evaluation_tasks)} tasks</strong></span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    selected_company = st.selectbox(
        "Company",
        companies,
        key="overview_company",
    )
    latest_year, latest_frame, ratios = latest_company_snapshot(
        graph,
        selected_company,
    )
    company_code = graph.company_code(selected_company)

    revenue, revenue_unit = metric_value(latest_frame, "revenue")
    operating_income, operating_unit = metric_value(
        latest_frame,
        "operating_income",
    )

    st.markdown(
        f"""
        <div class="company-heading">
            <div>
                <div class="company-name">{escape_text(selected_company)}</div>
                <div class="company-meta">OpenDART corp code {escape_text(company_code)}</div>
            </div>
            <div class="company-year">{latest_year} FY</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    kpi_cols = st.columns(4)
    kpi_items = [
        (
            "Revenue",
            "—" if revenue is None else format_money(revenue, revenue_unit),
            f"{latest_year} 사업연도",
        ),
        (
            "Operating income",
            "—"
            if operating_income is None
            else format_money(operating_income, operating_unit),
            f"{latest_year} 사업연도",
        ),
        (
            "Operating margin",
            format_ratio(ratios.get("operating_margin")),
            "영업이익 / 매출",
        ),
        (
            "Debt ratio",
            format_ratio(ratios.get("debt_ratio")),
            "부채 / 자본",
        ),
    ]

    for col, item in zip(kpi_cols, kpi_items):
        with col:
            render_kpi(*item)

    st.write("")
    left, right = st.columns([1.65, 1])

    with left:
        st.markdown('<div class="workspace-panel">', unsafe_allow_html=True)
        render_section_title(
            "Financial trend",
            "단위: 조원",
        )
        company_frame = graph.facts(selected_company)
        trend = company_frame[
            company_frame["metric"].isin(["revenue", "operating_income"])
        ].copy()
        if not trend.empty:
            trend["value_trillion"] = trend["value"] / 1_000_000_000_000
            trend["metric_name"] = trend["metric"].map(
                {
                    "revenue": "Revenue",
                    "operating_income": "Operating income",
                }
            )
            chart_frame = trend.pivot_table(
                index="year",
                columns="metric_name",
                values="value_trillion",
                aggfunc="first",
            ).sort_index()
            st.line_chart(chart_frame, use_container_width=True)
        else:
            st.caption("표시할 추세 데이터가 없습니다.")
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="workspace-panel">', unsafe_allow_html=True)
        render_section_title(
            "Analysis pipeline",
            "질문 처리 순서",
        )
        render_pipeline_step(
            "1",
            "Route",
            "질문에서 기업, 연도, 지표와 분석 유형을 확인합니다.",
        )
        render_pipeline_step(
            "2",
            "Plan",
            "Skill KG에서 필요한 SKILL과 선행 단계를 정합니다.",
        )
        render_pipeline_step(
            "3",
            "Retrieve",
            "Financial KG에서 필요한 수치와 공시 근거를 조회합니다.",
        )
        render_pipeline_step(
            "4",
            "Compute",
            "정해진 공식은 Python으로 계산하고 근거와 함께 반환합니다.",
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    bottom_left, bottom_right = st.columns([1.65, 1])

    with bottom_left:
        st.markdown('<div class="workspace-panel">', unsafe_allow_html=True)
        render_section_title(
            "Latest financial facts",
            f"{selected_company} {latest_year}",
        )
        fact_view = latest_frame.copy()
        fact_view["Metric"] = fact_view["metric"].map(METRIC_LABELS)
        fact_view["Value"] = [
            format_money(float(row.value), str(row.unit))
            for row in fact_view.itertuples(index=False)
        ]
        fact_view = fact_view[["Metric", "Value", "source_id"]].rename(
            columns={"source_id": "Source"}
        )
        st.dataframe(
            fact_view,
            hide_index=True,
            use_container_width=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with bottom_right:
        st.markdown('<div class="workspace-panel">', unsafe_allow_html=True)
        render_section_title(
            "Workspace status",
            "현재 로드 상태",
        )
        render_status_row(
            "Financial data",
            data_label,
            "good" if not is_sample else "warning",
        )
        render_status_row(
            "LLM rendering",
            llm_label,
            "good" if llm_client is not None else "neutral",
        )
        render_status_row(
            "Loaded companies",
            f'{summary["companies"]} / {len(cohort.companies)}',
            "good" if summary["companies"] == len(cohort.companies) else "warning",
        )
        render_status_row(
            "Evaluation tasks",
            str(len(evaluation_tasks)),
            "neutral",
        )
        st.markdown("</div>", unsafe_allow_html=True)

elif page == "Ask":
    render_page_header(
        "Research query",
        "재무 질문을 입력하면 사용한 SKILL, 계산 결과와 공시 근거를 함께 확인할 수 있습니다.",
        "Ask",
    )

    first_company = companies[0]
    second_company = companies[1] if len(companies) > 1 else companies[0]
    examples = [
        f"{first_company} 최근 3년 재무상태 분석해줘",
        f"{first_company} 2025년 부채비율 알려줘",
        f"{first_company} 영업이익률 변화 알려줘",
        f"{first_company}와 {second_company} ROE 비교해줘",
    ]

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    st.markdown('<div class="research-shell">', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="research-intro">
            <strong>Ask against verified financial facts</strong>
            <span>
                재무 수치는 Financial KG에서 조회하고, 계산식이 정해진 항목은 Python에서 처리합니다.
                LLM 연결 시 최종 문장만 별도로 정리할 수 있습니다.
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    control_left, control_right = st.columns([3, 1])
    with control_left:
        selected_example = st.selectbox(
            "예시 질문",
            ["직접 입력"] + examples,
            index=0,
        )
    with control_right:
        use_llm = st.checkbox(
            "LLM 문장화",
            value=False,
            disabled=llm_client is None,
            help="계산 결과와 evidence는 유지하고 최종 문장만 LLM이 정리합니다.",
        )

    with st.form("question_form", clear_on_submit=True):
        default_query = "" if selected_example == "직접 입력" else selected_example
        query = st.text_input(
            "질문",
            value=default_query,
            placeholder="예: 삼성전자 2025년 부채비율 알려줘",
        )
        submitted = st.form_submit_button(
            "분석 실행",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        query = query.strip()
        if not query:
            st.warning("질문을 입력해 주세요.")
        else:
            item = analyze_query(query, engine, registry, llm_client, use_llm)
            st.session_state.chat_history.append(item)
            st.rerun()

    if st.session_state.chat_history:
        latest_item = st.session_state.chat_history[-1]
        render_research_result(latest_item, registry)

        history_cols = st.columns([1, 5])
        with history_cols[0]:
            if st.button("초기화", use_container_width=True):
                st.session_state.chat_history = []
                st.rerun()
        with history_cols[1]:
            if len(st.session_state.chat_history) > 1:
                st.caption(
                    f"현재 세션에서 {len(st.session_state.chat_history)}개의 질문을 실행했습니다."
                )

    st.markdown("</div>", unsafe_allow_html=True)

elif page == "Knowledge Graph":
    render_page_header(
        "Knowledge Graph",
        "Financial KG와 Skill KG를 분리해서 보고, 데이터와 분석 절차가 어떻게 연결되는지 확인합니다.",
        "Graph",
    )

    graph_view = st.radio(
        "Graph type",
        ["Financial KG", "Skill KG"],
        index=0,
        horizontal=True,
        label_visibility="collapsed",
    )

    if graph_view == "Financial KG":
        control_left, control_right = st.columns(2)
        with control_left:
            selected_company = st.selectbox(
                "기업",
                companies,
                key="financial_graph_company",
            )
        company_frame = graph.facts(selected_company)
        available_years = sorted(
            int(value)
            for value in company_frame["year"].unique()
        )
        with control_right:
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

        render_section_title(
            "Financial facts",
            f"{selected_company} {selected_year}",
        )
        view = company_frame[company_frame["year"] == selected_year].copy()
        view["Metric"] = view["metric"].map(METRIC_LABELS)
        view["Value"] = [
            format_money(float(row.value), str(row.unit))
            for row in view.itertuples(index=False)
        ]
        view = view[
            ["Metric", "metric", "Value", "source_id"]
        ].rename(
            columns={
                "metric": "Metric ID",
                "source_id": "Source",
            }
        )
        st.dataframe(
            view,
            hide_index=True,
            use_container_width=True,
        )

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
            key="skill_graph_focus",
        )
        st.caption(registry.skills[focus_skill].description)
        st.graphviz_chart(
            skill_kg_dot(registry, focus_skill),
            use_container_width=True,
        )

elif page == "SKILL Explorer":
    render_page_header(
        "SKILL Explorer",
        "각 분석 업무의 dependency, 입력과 출력, validation 규칙과 실제 SKILL.md를 확인합니다.",
        "Library",
    )

    selected_skill_id = st.selectbox(
        "SKILL",
        sorted(registry.skills),
        key="skill_explorer_select",
    )
    selected_skill = registry.skills[selected_skill_id]

    st.markdown(
        f"""
        <div class="workspace-panel">
            <div class="company-name">{escape_text(selected_skill.name)}</div>
            <div class="company-meta">{escape_text(selected_skill.description)}</div>
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
        render_section_title("Metadata", "Skill KG attributes")
        metadata = pd.DataFrame(
            [
                ("Requires", ", ".join(selected_skill.requires) or "—"),
                ("Consumes", ", ".join(selected_skill.consumes) or "—"),
                ("Produces", ", ".join(selected_skill.produces) or "—"),
                ("Tools", ", ".join(selected_skill.tools) or "—"),
                ("Validation", ", ".join(selected_skill.validation) or "—"),
                ("Metrics", ", ".join(selected_skill.required_metrics) or "—"),
            ],
            columns=["Field", "Value"],
        )
        st.dataframe(
            metadata,
            hide_index=True,
            use_container_width=True,
        )

    with st.expander("SKILL.md 보기", expanded=True):
        st.markdown(selected_skill.body)

elif page == "Evaluation":
    render_page_header(
        "Evaluation",
        "동일한 금융 질문을 세 시스템에 적용하고 수치 정확도, 근거와 SKILL 선택 성능을 비교합니다.",
        "Benchmark",
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

    metric_cols = st.columns(5)
    metric_items = [
        ("Numerical", "Accuracy", "수치 정답"),
        ("Evidence", "F1", "공시 근거"),
        ("Skill", "Accuracy", "라우팅"),
        ("Unsupported", "Rate", "근거 없는 주장"),
        ("Latency", "ms", "처리 시간"),
    ]
    for col, item in zip(metric_cols, metric_items):
        with col:
            render_kpi(*item)

    st.write("")
    result_path = Path("outputs/evaluation/summary.csv")

    left, right = st.columns([1.55, 1])
    with left:
        render_section_title("Latest benchmark", "3-system comparison")
        if result_path.exists():
            benchmark = pd.read_csv(result_path)
            st.dataframe(
                benchmark,
                hide_index=True,
                use_container_width=True,
            )
            chart_columns = [
                column
                for column in [
                    "numeric_accuracy",
                    "evidence_f1",
                    "skill_accuracy",
                ]
                if column in benchmark.columns
            ]
            if chart_columns and "system" in benchmark.columns:
                chart_frame = benchmark.set_index("system")[chart_columns]
                st.bar_chart(chart_frame)
        else:
            st.info(
                "아직 benchmark 결과가 없습니다. 실제 DART 데이터와 LLM 설정 후 "
                "python scripts/run_evaluation.py 를 실행하면 결과가 표시됩니다."
            )

    with right:
        render_section_title("Task distribution", f"{len(evaluation_tasks)} tasks")
        count_frame = (
            task_frame["Type"]
            .value_counts()
            .rename_axis("Type")
            .reset_index(name="Tasks")
        )
        st.dataframe(
            count_frame,
            hide_index=True,
            use_container_width=True,
        )

    with st.expander("평가 질문 전체 보기"):
        st.dataframe(
            task_frame,
            hide_index=True,
            use_container_width=True,
        )

elif page == "Dataset":
    render_page_header(
        "Dataset",
        "실험에 사용하는 OpenDART 기업 cohort와 현재 데이터 적재 상태를 확인합니다.",
        "OpenDART",
    )

    cohort_rows = []
    for company in cohort.companies:
        cohort_rows.append(
            {
                "Company": company.name,
                "Ticker": company.ticker,
                "Sector": company.sector,
                "Status": (
                    "Loaded"
                    if company.name in loaded_companies
                    else "Not loaded"
                ),
            }
        )
    cohort_frame = pd.DataFrame(cohort_rows)
    loaded_count = int((cohort_frame["Status"] == "Loaded").sum())

    dataset_cols = st.columns(4)
    dataset_items = [
        ("Target companies", len(cohort.companies), "고정 cohort"),
        ("Loaded", loaded_count, data_label),
        ("Years", "2023–2025", "사업보고서"),
        ("Financial facts", summary["facts"], "현재 KG"),
    ]
    for col, item in zip(dataset_cols, dataset_items):
        with col:
            render_kpi(*item)

    st.write("")
    render_section_title(
        "Company coverage",
        "OpenDART cohort",
    )
    st.dataframe(
        cohort_frame,
        hide_index=True,
        use_container_width=True,
    )

st.caption(
    "Risk Signal은 프로젝트용 단순 규칙이며 투자 판단이나 신용등급을 의미하지 않습니다."
)
