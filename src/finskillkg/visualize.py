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
        return 'digraph G { label="No financial facts"; }'

    available_years = sorted(int(value) for value in frame["year"].unique())
    selected_year = int(year) if year in available_years else available_years[-1]
    year_frame = frame[frame["year"] == selected_year].copy()
    year_frame["_order"] = year_frame["metric"].map(
        {metric: idx for idx, metric in enumerate(_METRIC_ORDER)}
    )
    year_frame = year_frame.sort_values("_order")

    source_rows = graph.sources(company_name, [selected_year])
    source_id = source_rows[0]["source_id"] if source_rows else "unknown"

    lines = [
        "digraph FinancialKG {",
        '  graph [rankdir=LR, bgcolor="transparent", pad="0.35", nodesep="0.22", ranksep="0.95", splines=polyline, newrank=true];',
        '  node [fontname="Arial", fontsize=10.5, shape=box, style="rounded,filled", margin="0.14,0.10", color="#CBD5E1", fillcolor="#FFFFFF", fontcolor="#0F172A", penwidth=1.2];',
        '  edge [fontname="Arial", fontsize=8.5, color="#94A3B8", fontcolor="#64748B", arrowsize=0.65, penwidth=1.1];',
        '  subgraph cluster_company { label="COMPANY"; labelloc="t"; labeljust="l"; fontsize=9; fontcolor="#64748B"; color="#E2E8F0"; style="rounded"; bgcolor="#F8FAFC";',
        f'    company [label="{_escape(company_name)}\nCompany", fillcolor="#EFF6FF", color="#2563EB", penwidth=1.5];',
        "  }",
        '  subgraph cluster_facts { label="FINANCIAL FACTS"; labelloc="t"; labeljust="l"; fontsize=9; fontcolor="#64748B"; color="#E2E8F0"; style="rounded"; bgcolor="#FCFCFD";',
    ]

    fact_ids = []
    metric_ids = []
    for idx, row in enumerate(year_frame.itertuples(index=False)):
        metric = str(row.metric)
        metric_name = METRIC_LABELS.get(metric, metric)
        value_text = format_money(float(row.value), str(row.unit))
        fact_id = f"fact_{idx}"
        metric_id = f"metric_{idx}"
        fact_ids.append(fact_id)
        metric_ids.append(metric_id)
        lines.append(
            f'    {fact_id} [label="{_escape(metric_name)}\n{_escape(value_text)}", fillcolor="#ECFEFF", color="#0891B2"];'
        )
    lines.append("  }")

    lines.extend(
        [
            '  subgraph cluster_context { label="CONTEXT"; labelloc="t"; labeljust="l"; fontsize=9; fontcolor="#64748B"; color="#E2E8F0"; style="rounded"; bgcolor="#FCFCFD";',
            f'    period [label="{selected_year}\nPeriod", fillcolor="#F8FAFC", color="#94A3B8"];',
        ]
    )
    for idx, row in enumerate(year_frame.itertuples(index=False)):
        metric = str(row.metric)
        metric_id = f"metric_{idx}"
        lines.append(
            f'    {metric_id} [label="{_escape(metric)}\nMetric", fillcolor="#F0FDF4", color="#16A34A"];'
        )
    lines.append("  }")

    lines.extend(
        [
            '  subgraph cluster_source { label="PROVENANCE"; labelloc="t"; labeljust="l"; fontsize=9; fontcolor="#64748B"; color="#E2E8F0"; style="rounded"; bgcolor="#FCFCFD";',
            f'    report [label="OpenDART 사업보고서\n{_escape(source_id)}", shape=note, fillcolor="#FFFBEB", color="#D97706"];',
            "  }",
            '  company -> report [label="HAS_REPORT", style=dashed, color="#CBD5E1"];',
        ]
    )

    for idx, fact_id in enumerate(fact_ids):
        lines.extend(
            [
                f'  company -> {fact_id} [label="HAS_FINANCIAL_FACT"];',
                f'  {fact_id} -> {metric_ids[idx]} [label="OF_METRIC", color="#86B99A"];',
                f'  {fact_id} -> period [label="FOR_PERIOD", color="#CBD5E1"];',
                f'  {fact_id} -> report [label="EXTRACTED_FROM", color="#D6B56D"];',
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
        '  graph [rankdir=TB, bgcolor="transparent", pad="0.35", nodesep="0.35", ranksep="0.55", splines=polyline, newrank=true];',
        '  node [fontname="Arial", fontsize=10.5, shape=box, style="rounded,filled", margin="0.16,0.11", color="#CBD5E1", fillcolor="#FFFFFF", fontcolor="#0F172A", penwidth=1.2];',
        '  edge [fontname="Arial", fontsize=8.5, color="#94A3B8", fontcolor="#64748B", arrowsize=0.65, penwidth=1.1];',
        '  subgraph cluster_skills { label="SKILL DEPENDENCY"; labelloc="t"; labeljust="l"; fontsize=9; fontcolor="#64748B"; color="#E2E8F0"; style="rounded"; bgcolor="#FCFCFD";',
    ]

    for skill in registry.skills.values():
        fill = "#EFF6FF" if skill.skill_id == focus_skill else "#FFFFFF"
        color = "#2563EB" if skill.skill_id == focus_skill else "#CBD5E1"
        penwidth = "1.7" if skill.skill_id == focus_skill else "1.2"
        lines.append(
            f'    "skill:{_escape(skill.skill_id)}" '
            f'[label="{_escape(skill.name)}\n{_escape(skill.skill_id)}", '
            f'fillcolor="{fill}", color="{color}", penwidth={penwidth}];'
        )
    lines.append("  }")

    for skill in registry.skills.values():
        for dependency in skill.requires:
            lines.append(
                f'  "skill:{_escape(skill.skill_id)}" -> "skill:{_escape(dependency)}" '
                '[label="REQUIRES"];'
            )

    if focus_skill in registry.skills:
        skill = registry.skills[focus_skill]
        if skill.required_metrics:
            lines.append(
                '  subgraph cluster_metrics { label="FINANCIAL KG BRIDGE"; labelloc="t"; labeljust="l"; fontsize=9; fontcolor="#64748B"; color="#DCFCE7"; style="rounded"; bgcolor="#FBFEFC";'
            )
            for metric in skill.required_metrics:
                metric_id = f"metric:{metric}"
                lines.append(
                    f'    "{_escape(metric_id)}" [label="{_escape(metric)}\nMetric", '
                    'shape=box, fillcolor="#F0FDF4", color="#16A34A"];'
                )
            lines.append("  }")
            for metric in skill.required_metrics:
                metric_id = f"metric:{metric}"
                lines.append(
                    f'  "skill:{_escape(focus_skill)}" -> "{_escape(metric_id)}" '
                    '[label="REQUIRES_METRIC", color="#16A34A", fontcolor="#15803D", style=dashed];'
                )

    lines.append("}")
    return "\n".join(lines)


def skill_detail_dot(registry: SkillRegistry, skill_id: str) -> str:
    skill = registry.skills[skill_id]
    lines = [
        "digraph SkillDetail {",
        '  graph [rankdir=LR, bgcolor="transparent", pad="0.35", nodesep="0.32", ranksep="0.9", splines=polyline, newrank=true];',
        '  node [fontname="Arial", fontsize=10, shape=box, style="rounded,filled", margin="0.15,0.10", color="#CBD5E1", fillcolor="#FFFFFF", fontcolor="#0F172A", penwidth=1.2];',
        '  edge [fontname="Arial", fontsize=8.5, color="#94A3B8", fontcolor="#64748B", arrowsize=0.65, penwidth=1.1];',
        '  subgraph cluster_input { label="INPUT / DEPENDENCY"; labelloc="t"; labeljust="l"; fontsize=9; fontcolor="#64748B"; color="#E2E8F0"; style="rounded"; bgcolor="#FCFCFD";',
    ]

    left_groups = [
        ("requires", skill.requires, "REQUIRES", "#FEF2F2", "#DC2626"),
        ("consumes", skill.consumes, "CONSUMES", "#F8FAFC", "#64748B"),
        ("metrics", skill.required_metrics, "REQUIRES_METRIC", "#F0FDF4", "#16A34A"),
    ]
    right_groups = [
        ("produces", skill.produces, "PRODUCES", "#ECFDF5", "#059669"),
        ("tools", skill.tools, "USES_TOOL", "#FFF7ED", "#EA580C"),
        ("validation", skill.validation, "VALIDATED_BY", "#F5F3FF", "#7C3AED"),
    ]

    left_nodes = []
    right_nodes = []

    for group_name, values, relation, fill, color in left_groups:
        for idx, value in enumerate(values):
            node_id = f"{group_name}_{idx}"
            left_nodes.append((node_id, relation, color))
            lines.append(
                f'    {node_id} [label="{_escape(value)}", fillcolor="{fill}", color="{color}"];'
            )
    lines.append("  }")

    lines.extend(
        [
            f'  skill [label="{_escape(skill.name)}\n{_escape(skill.skill_id)}", fillcolor="#EFF6FF", color="#2563EB", penwidth=1.7];',
            '  subgraph cluster_output { label="OUTPUT / RULE"; labelloc="t"; labeljust="l"; fontsize=9; fontcolor="#64748B"; color="#E2E8F0"; style="rounded"; bgcolor="#FCFCFD";',
        ]
    )

    for group_name, values, relation, fill, color in right_groups:
        for idx, value in enumerate(values):
            node_id = f"{group_name}_{idx}"
            right_nodes.append((node_id, relation, color))
            lines.append(
                f'    {node_id} [label="{_escape(value)}", fillcolor="{fill}", color="{color}"];'
            )
    lines.append("  }")

    for node_id, relation, color in left_nodes:
        lines.append(
            f'  skill -> {node_id} [label="{relation}", color="{color}", fontcolor="{color}"];'
        )
    for node_id, relation, color in right_nodes:
        lines.append(
            f'  skill -> {node_id} [label="{relation}", color="{color}", fontcolor="{color}"];'
        )

    lines.append("}")
    return "\n".join(lines)
