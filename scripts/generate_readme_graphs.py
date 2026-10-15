from __future__ import annotations

from html import escape
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.finskillkg.graph import DualKnowledgeGraph
from src.finskillkg.metrics import format_money
from src.finskillkg.normalize import METRIC_LABELS, load_financial_csv
from src.finskillkg.skills import SkillRegistry


ASSET_DIR = Path("docs/assets")


def svg_start(width: int, height: int) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<defs>",
        '<marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">',
        '<path d="M0,0 L8,4 L0,8 z" fill="#94a3b8"/>',
        "</marker>",
        '<style>text{font-family:Arial,"Noto Sans KR",sans-serif}.title{font-size:24px;font-weight:700;fill:#0f172a}.label{font-size:15px;font-weight:700;fill:#0f172a}.small{font-size:12px;fill:#475569}.edge{font-size:11px;fill:#64748b}.box{rx:12;ry:12;stroke-width:1.5}.line{stroke:#94a3b8;stroke-width:1.5;fill:none;marker-end:url(#arrow)}</style>',
        "</defs>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]


def box(
    lines: list[str],
    x: int,
    y: int,
    w: int,
    h: int,
    title: str,
    subtitle: str = "",
    fill: str = "#f8fafc",
    stroke: str = "#64748b",
) -> None:
    lines.append(
        f'<rect class="box" x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}"/>'
    )
    lines.append(
        f'<text class="label" x="{x + 14}" y="{y + 26}">{escape(title)}</text>'
    )
    if subtitle:
        lines.append(
            f'<text class="small" x="{x + 14}" y="{y + 47}">{escape(subtitle)}</text>'
        )


def arrow(
    lines: list[str],
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    label: str,
) -> None:
    lines.append(
        f'<path class="line" d="M{x1},{y1} L{x2},{y2}"/>'
    )
    mx = (x1 + x2) // 2
    my = (y1 + y2) // 2 - 7
    lines.append(
        f'<text class="edge" x="{mx}" y="{my}" text-anchor="middle">{escape(label)}</text>'
    )


def financial_kg_svg(graph: DualKnowledgeGraph) -> str:
    company = graph.company_names()[0]
    frame = graph.facts(company)
    year = int(frame["year"].max())
    year_frame = frame[frame["year"] == year].copy()
    year_frame = year_frame.head(4)
    source = graph.sources(company, [year])[0]

    lines = svg_start(1500, 760)
    lines.append('<text class="title" x="48" y="52">Financial KG Sample</text>')
    lines.append(
        '<text class="small" x="48" y="78">Company, FinancialFact, Metric, Period, Report 관계의 실제 sample graph</text>'
    )

    box(lines, 60, 300, 190, 82, company, "Company", "#e0f2fe", "#0284c7")
    box(lines, 1210, 120, 210, 80, f"{year}", "Period", "#f1f5f9", "#64748b")
    box(
        lines,
        1180,
        500,
        250,
        96,
        "Annual Report",
        str(source["source_id"]),
        "#fef3c7",
        "#d97706",
    )

    fact_y = [135, 270, 405, 540]
    for idx, row in enumerate(year_frame.itertuples(index=False)):
        metric_name = METRIC_LABELS.get(str(row.metric), str(row.metric))
        value = format_money(float(row.value), str(row.unit))
        fy = fact_y[idx]
        box(
            lines,
            400,
            fy,
            270,
            82,
            metric_name,
            value,
            "#ecfeff",
            "#0891b2",
        )
        box(
            lines,
            820,
            fy,
            230,
            82,
            str(row.metric),
            "Metric",
            "#f0fdf4",
            "#16a34a",
        )
        arrow(lines, 250, 341, 400, fy + 41, "HAS_FINANCIAL_FACT")
        arrow(lines, 670, fy + 41, 820, fy + 41, "OF_METRIC")
        arrow(lines, 670, fy + 41, 1210, 160, "FOR_PERIOD")
        arrow(lines, 670, fy + 41, 1180, 548, "EXTRACTED_FROM")

    arrow(lines, 250, 360, 1180, 570, "HAS_REPORT")
    lines.append("</svg>")
    return "\n".join(lines)


def skill_kg_svg(registry: SkillRegistry) -> str:
    lines = svg_start(1600, 760)
    lines.append('<text class="title" x="48" y="52">Skill KG Sample</text>')
    lines.append(
        '<text class="small" x="48" y="78">SKILL dependency와 Financial KG metric bridge를 함께 표현</text>'
    )

    chain = [
        "financial_statement_extraction",
        "financial_fact_validation",
        "financial_metric_calculation",
        "financial_trend_analysis",
        "financial_risk_analysis",
        "financial_summary_generation",
    ]
    xs = [55, 305, 555, 805, 1055, 1305]

    for idx, skill_id in enumerate(chain):
        skill = registry.skills[skill_id]
        fill = "#dbeafe" if skill_id == "financial_summary_generation" else "#f8fafc"
        stroke = "#2563eb" if skill_id == "financial_summary_generation" else "#64748b"
        box(lines, xs[idx], 230, 205, 88, skill.name, skill_id, fill, stroke)
        if idx > 0:
            arrow(lines, xs[idx], 274, xs[idx - 1] + 205, 274, "REQUIRES")

    compare = registry.skills["company_comparison"]
    box(
        lines,
        805,
        390,
        205,
        88,
        compare.name,
        compare.skill_id,
        "#f8fafc",
        "#64748b",
    )
    arrow(lines, 805, 434, 760, 274, "REQUIRES")

    metric_x = [250, 470, 690, 910, 1130, 1350]
    metrics = registry.skills["financial_summary_generation"].required_metrics
    for idx, metric in enumerate(metrics):
        box(
            lines,
            metric_x[idx],
            600,
            170,
            62,
            metric,
            "Financial KG Metric",
            "#f0fdf4",
            "#16a34a",
        )
        arrow(lines, 1408, 318, metric_x[idx] + 85, 600, "REQUIRES_METRIC")

    lines.append("</svg>")
    return "\n".join(lines)


def skill_anatomy_svg(registry: SkillRegistry) -> str:
    skill = registry.skills["financial_metric_calculation"]
    lines = svg_start(1500, 760)
    lines.append('<text class="title" x="48" y="52">SKILL.md Anatomy</text>')
    lines.append(
        '<text class="small" x="48" y="78">하나의 SKILL은 metadata와 실행 지침을 함께 가진다.</text>'
    )

    box(
        lines,
        560,
        120,
        380,
        92,
        skill.name,
        skill.skill_id,
        "#dbeafe",
        "#2563eb",
    )

    metadata = [
        ("requires", ", ".join(skill.requires) or "-"),
        ("consumes", ", ".join(skill.consumes) or "-"),
        ("produces", ", ".join(skill.produces) or "-"),
        ("tools", ", ".join(skill.tools) or "-"),
        ("validation", ", ".join(skill.validation) or "-"),
    ]
    for idx, (key, value) in enumerate(metadata):
        y = 270 + idx * 82
        box(lines, 100, y, 480, 64, key, value, "#f8fafc", "#64748b")
        arrow(lines, 560, 165, 580, y + 32, key.upper())

    instructions = [
        ("Objective", "무엇을 수행하는 Skill인지 정의"),
        ("Procedure", "입력 확인 → 공식 계산 → 결과 반환"),
        ("Constraints", "없는 값을 만들지 않고 N/A 처리"),
        ("required_metrics", ", ".join(skill.required_metrics)),
    ]
    for idx, (key, value) in enumerate(instructions):
        y = 270 + idx * 100
        box(lines, 950, y, 430, 72, key, value, "#fff7ed", "#ea580c")
        arrow(lines, 940, 165, 950, y + 36, key.upper())

    lines.append("</svg>")
    return "\n".join(lines)


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    frame = load_financial_csv("data/sample_financials.csv")
    registry = SkillRegistry.load("skills")
    graph = DualKnowledgeGraph()
    graph.add_financial_data(frame)
    graph.add_skill_registry(registry)

    assets = {
        "financial_kg_sample.svg": financial_kg_svg(graph),
        "skill_kg_sample.svg": skill_kg_svg(registry),
        "skill_anatomy.svg": skill_anatomy_svg(registry),
    }
    for name, content in assets.items():
        path = ASSET_DIR / name
        path.write_text(content, encoding="utf-8")
        print(f"saved: {path}")


if __name__ == "__main__":
    main()
