from __future__ import annotations

from .graph import DualKnowledgeGraph
from .metrics import format_money
from .normalize import METRIC_LABELS
from .skills import SkillRegistry


_METRIC_ORDER = [
    "revenue",
    "operating_income",
    "net_income",
    "assets",
    "liabilities",
    "equity",
]


def _escape(value: object) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", " ")
    )


def financial_kg_dot(
    graph: DualKnowledgeGraph,
    company_name: str,
    year: int | None = None,
) -> str:
    frame = graph.facts(company_name)
    if frame.empty:
        return "digraph G { label=\"No financial facts\"; }"

    available_years = sorted(int(value) for value in frame["year"].unique())
    selected_year = int(year) if year in available_years else available_years[-1]
    year_frame = frame[frame["year"] == selected_year].copy()
    year_frame["_order"] = year_frame["metric"].map(
        {metric: idx for idx, metric in enumerate(_METRIC_ORDER)}
    )
    year_frame = year_frame.sort_values("_order")

    source_rows = graph.sources(company_name, [selected_year])
    source_id = source_rows[0]["source_id"] if source_rows else "unknown"
    report_label = f"Report\\n{source_id}"

    lines = [
        "digraph FinancialKG {",
        '  graph [rankdir=LR, bgcolor="transparent", pad="0.25", nodesep="0.28", ranksep="0.65"];',
        '  node [fontname="Arial", fontsize=11, shape=box, style="rounded,filled", color="#64748b", fillcolor="#f8fafc", fontcolor="#0f172a"];',
        '  edge [fontname="Arial", fontsize=9, color="#94a3b8", fontcolor="#475569", arrowsize=0.7];',
        f'  company [label="{_escape(company_name)}", shape=box, fillcolor="#e0f2fe", color="#0284c7", penwidth=1.5];',
        f'  period [label="Period\\n{selected_year}", shape=ellipse, fillcolor="#f1f5f9"];',
        f'  report [label="{_escape(report_label)}", shape=note, fillcolor="#fef3c7", color="#d97706"];',
        '  company -> report [label="HAS_REPORT"];',
    ]

    for idx, row in enumerate(year_frame.itertuples(index=False)):
        metric = str(row.metric)
        metric_name = METRIC_LABELS.get(metric, metric)
        fact_id = f"fact_{idx}"
        metric_id = f"metric_{idx}"
        value_text = format_money(float(row.value), str(row.unit))
        lines.extend(
            [
                f'  {fact_id} [label="{_escape(metric_name)}\\n{_escape(value_text)}", fillcolor="#ecfeff", color="#0891b2"];',
                f'  {metric_id} [label="Metric\\n{_escape(metric)}", fillcolor="#f0fdf4", color="#16a34a"];',
                f'  company -> {fact_id} [label="HAS_FINANCIAL_FACT"];',
                f'  {fact_id} -> {metric_id} [label="OF_METRIC"];',
                f'  {fact_id} -> period [label="FOR_PERIOD"];',
                f'  {fact_id} -> report [label="EXTRACTED_FROM"];',
            ]
        )

    lines.append("}")
    return "\n".join(lines)


def skill_kg_dot(
    registry: SkillRegistry,
    focus_skill: str = "financial_summary_generation",
) -> str:
    lines = [
        "digraph SkillKG {",
        '  graph [rankdir=LR, bgcolor="transparent", pad="0.25", nodesep="0.35", ranksep="0.7"];',
        '  node [fontname="Arial", fontsize=10, shape=box, style="rounded,filled", color="#64748b", fillcolor="#f8fafc", fontcolor="#0f172a"];',
        '  edge [fontname="Arial", fontsize=9, color="#94a3b8", fontcolor="#475569", arrowsize=0.7];',
    ]

    for skill in registry.skills.values():
        fill = "#dbeafe" if skill.skill_id == focus_skill else "#f8fafc"
        color = "#2563eb" if skill.skill_id == focus_skill else "#64748b"
        label = skill.name.replace(" ", "\\n", 1)
        lines.append(
            f'  "skill:{_escape(skill.skill_id)}" [label="{_escape(label)}", fillcolor="{fill}", color="{color}"];'
        )

    for skill in registry.skills.values():
        for dependency in skill.requires:
            lines.append(
                f'  "skill:{_escape(skill.skill_id)}" -> "skill:{_escape(dependency)}" '
                '[label="REQUIRES"];'
            )

    if focus_skill in registry.skills:
        skill = registry.skills[focus_skill]
        for metric in skill.required_metrics:
            metric_id = f"metric:{metric}"
            lines.append(
                f'  "{_escape(metric_id)}" [label="Metric\\n{_escape(metric)}", '
                'shape=ellipse, fillcolor="#f0fdf4", color="#16a34a"];'
            )
            lines.append(
                f'  "skill:{_escape(focus_skill)}" -> "{_escape(metric_id)}" '
                '[label="REQUIRES_METRIC", color="#16a34a", fontcolor="#15803d"];'
            )

    lines.append("}")
    return "\n".join(lines)


def skill_detail_dot(registry: SkillRegistry, skill_id: str) -> str:
    skill = registry.skills[skill_id]
    lines = [
        "digraph SkillDetail {",
        '  graph [rankdir=LR, bgcolor="transparent", pad="0.25", nodesep="0.3", ranksep="0.7"];',
        '  node [fontname="Arial", fontsize=10, shape=box, style="rounded,filled", color="#64748b", fillcolor="#f8fafc", fontcolor="#0f172a"];',
        '  edge [fontname="Arial", fontsize=9, color="#94a3b8", fontcolor="#475569", arrowsize=0.7];',
        f'  skill [label="{_escape(skill.name)}\\n{_escape(skill.skill_id)}", fillcolor="#dbeafe", color="#2563eb", penwidth=1.5];',
    ]

    groups = [
        ("requires", skill.requires, "REQUIRES", "#fef2f2", "#dc2626"),
        ("consumes", skill.consumes, "CONSUMES", "#f8fafc", "#64748b"),
        ("produces", skill.produces, "PRODUCES", "#ecfdf5", "#059669"),
        ("tools", skill.tools, "USES_TOOL", "#fff7ed", "#ea580c"),
        ("validation", skill.validation, "VALIDATED_BY", "#faf5ff", "#9333ea"),
        ("metrics", skill.required_metrics, "REQUIRES_METRIC", "#f0fdf4", "#16a34a"),
    ]

    for group_name, values, relation, fill, color in groups:
        for idx, value in enumerate(values):
            node_id = f"{group_name}_{idx}"
            lines.append(
                f'  {node_id} [label="{_escape(value)}", fillcolor="{fill}", color="{color}"];'
            )
            lines.append(
                f'  skill -> {node_id} [label="{relation}", color="{color}", fontcolor="{color}"];'
            )

    lines.append("}")
    return "\n".join(lines)
