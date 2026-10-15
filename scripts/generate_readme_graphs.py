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

NAVY = "#0F172A"
SLATE = "#475569"
MUTED = "#64748B"
LINE = "#CBD5E1"
PANEL = "#F8FAFC"
BLUE = "#2563EB"
BLUE_BG = "#EFF6FF"
CYAN = "#0891B2"
CYAN_BG = "#ECFEFF"
GREEN = "#16A34A"
GREEN_BG = "#F0FDF4"
AMBER = "#D97706"
AMBER_BG = "#FFFBEB"
PURPLE = "#7C3AED"
PURPLE_BG = "#F5F3FF"


def svg_start(width: int, height: int, title: str, subtitle: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        "<defs>",
        '<marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">',
        f'<path d="M0,0 L8,4 L0,8 z" fill="{MUTED}"/>',
        "</marker>",
        "<filter id=\"soft\" x=\"-10%\" y=\"-10%\" width=\"120%\" height=\"120%\">",
        '<feDropShadow dx="0" dy="2" stdDeviation="4" flood-color="#0F172A" flood-opacity="0.08"/>',
        "</filter>",
        '<style>',
        'text{font-family:Arial,"Noto Sans KR",sans-serif}',
        f'.title{{font-size:28px;font-weight:700;fill:{NAVY}}}',
        f'.subtitle{{font-size:13px;fill:{MUTED}}}',
        f'.section{{font-size:12px;font-weight:700;fill:{MUTED};letter-spacing:.08em}}',
        f'.label{{font-size:15px;font-weight:700;fill:{NAVY}}}',
        f'.small{{font-size:12px;fill:{SLATE}}}',
        f'.tiny{{font-size:10.5px;fill:{MUTED}}}',
        f'.edge{{font-size:10px;fill:{MUTED}}}',
        f'.line{{stroke:{LINE};stroke-width:1.5;fill:none;marker-end:url(#arrow)}}',
        f'.dash{{stroke:{LINE};stroke-width:1.5;stroke-dasharray:5 5;fill:none;marker-end:url(#arrow)}}',
        "</style>",
        "</defs>",
        '<rect width="100%" height="100%" fill="#FFFFFF"/>',
        f'<text class="title" x="52" y="54">{escape(title)}</text>',
        f'<text class="subtitle" x="52" y="82">{escape(subtitle)}</text>',
    ]


def rounded_rect(
    lines: list[str],
    x: int,
    y: int,
    w: int,
    h: int,
    fill: str = PANEL,
    stroke: str = LINE,
    radius: int = 16,
    shadow: bool = False,
) -> None:
    filter_attr = ' filter="url(#soft)"' if shadow else ""
    lines.append(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1.3"{filter_attr}/>'
    )


def card(
    lines: list[str],
    x: int,
    y: int,
    w: int,
    h: int,
    title: str,
    subtitle: str = "",
    fill: str = PANEL,
    stroke: str = LINE,
    tag: str | None = None,
    shadow: bool = True,
) -> None:
    rounded_rect(lines, x, y, w, h, fill, stroke, 16, shadow)
    if tag:
        lines.append(
            f'<text class="tiny" x="{x + 16}" y="{y + 20}">{escape(tag.upper())}</text>'
        )
        title_y = y + 43
        subtitle_y = y + 62
    else:
        title_y = y + 30
        subtitle_y = y + 50

    lines.append(
        f'<text class="label" x="{x + 16}" y="{title_y}">{escape(title)}</text>'
    )
    if subtitle:
        lines.append(
            f'<text class="small" x="{x + 16}" y="{subtitle_y}">{escape(subtitle)}</text>'
        )


def arrow(
    lines: list[str],
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    label: str = "",
    dashed: bool = False,
    bend: int | None = None,
) -> None:
    klass = "dash" if dashed else "line"
    if bend is None:
        path = f"M{x1},{y1} L{x2},{y2}"
        lx = (x1 + x2) // 2
        ly = (y1 + y2) // 2 - 8
    else:
        mid_x = (x1 + x2) // 2
        path = f"M{x1},{y1} C{mid_x},{y1 + bend} {mid_x},{y2 - bend} {x2},{y2}"
        lx = mid_x
        ly = (y1 + y2) // 2 - 8

    lines.append(f'<path class="{klass}" d="{path}"/>')
    if label:
        lines.append(
            f'<text class="edge" x="{lx}" y="{ly}" text-anchor="middle">{escape(label)}</text>'
        )


def financial_kg_svg(graph: DualKnowledgeGraph) -> str:
    company = graph.company_names()[0]
    frame = graph.facts(company)
    year = int(frame["year"].max())
    order = {
        "revenue": 0,
        "operating_income": 1,
        "net_income": 2,
        "assets": 3,
        "liabilities": 4,
        "equity": 5,
    }
    year_frame = frame[frame["year"] == year].copy()
    year_frame["_order"] = year_frame["metric"].map(order).fillna(99)
    year_frame = year_frame.sort_values("_order").head(6)
    sources = graph.sources(company, [year])
    source = sources[0] if sources else {"source_id": "sample-report"}

    lines = svg_start(
        1560,
        900,
        "Financial KG",
        "한 개의 재무 수치가 기업, 지표, 기간, 공시 근거와 어떻게 연결되는지 보여주는 예시",
    )

    lines.append('<text class="section" x="60" y="138">COMPANY</text>')
    lines.append('<text class="section" x="360" y="138">FINANCIAL FACTS</text>')
    lines.append('<text class="section" x="860" y="138">CONTEXT</text>')
    lines.append('<text class="section" x="1190" y="138">PROVENANCE</text>')

    card(
        lines,
        60,
        330,
        220,
        110,
        company,
        "분석 대상 기업",
        BLUE_BG,
        BLUE,
        "Company",
    )

    fact_positions: list[tuple[int, int, str]] = []
    start_y = 165
    for idx, row in enumerate(year_frame.itertuples(index=False)):
        y = start_y + idx * 104
        metric = str(row.metric)
        metric_name = METRIC_LABELS.get(metric, metric)
        value = format_money(float(row.value), str(row.unit))
        card(
            lines,
            360,
            y,
            330,
            82,
            metric_name,
            value,
            CYAN_BG,
            CYAN,
            "FinancialFact",
            shadow=False,
        )
        fact_positions.append((360, y, metric))
        arrow(lines, 280, 385, 360, y + 41)

    card(
        lines,
        840,
        215,
        260,
        92,
        str(year),
        "사업연도",
        PANEL,
        LINE,
        "Period",
    )
    card(
        lines,
        840,
        455,
        260,
        92,
        "Metric",
        "revenue / equity / ...",
        GREEN_BG,
        GREEN,
        "Metric",
    )
    card(
        lines,
        1190,
        330,
        300,
        124,
        "OpenDART 사업보고서",
        str(source["source_id"]),
        AMBER_BG,
        AMBER,
        "Report",
    )

    for _, y, metric in fact_positions:
        fact_right_x = 690
        fact_center_y = y + 41
        arrow(lines, fact_right_x, fact_center_y, 840, 261, "FOR_PERIOD", bend=-35)
        arrow(lines, fact_right_x, fact_center_y, 840, 501, "OF_METRIC", bend=30)
        arrow(lines, fact_right_x, fact_center_y, 1190, 392, "EXTRACTED_FROM", bend=45)

    arrow(lines, 280, 405, 1190, 420, "HAS_REPORT", dashed=True, bend=80)

    rounded_rect(lines, 60, 800, 1430, 58, "#F8FAFC", "#E2E8F0", 14, False)
    lines.append('<text class="small" x="84" y="835">핵심 포인트</text>')
    lines.append(
        '<text class="small" x="190" y="835">답변의 숫자는 FinancialFact에서 끝나지 않고 Report까지 다시 추적할 수 있도록 저장한다.</text>'
    )

    lines.append("</svg>")
    return "\n".join(lines)


def skill_kg_svg(registry: SkillRegistry) -> str:
    chain = [
        "financial_statement_extraction",
        "financial_fact_validation",
        "financial_metric_calculation",
        "financial_trend_analysis",
        "financial_risk_analysis",
        "financial_summary_generation",
    ]
    labels = {
        "financial_statement_extraction": "재무정보 추출",
        "financial_fact_validation": "재무정보 검증",
        "financial_metric_calculation": "재무비율 계산",
        "financial_trend_analysis": "추세 분석",
        "financial_risk_analysis": "Risk Signal",
        "financial_summary_generation": "최종 요약",
    }

    lines = svg_start(
        1640,
        900,
        "Skill KG",
        "질문을 처리하기 위해 어떤 SKILL이 먼저 실행되어야 하는지 dependency로 관리한다.",
    )

    lines.append('<text class="section" x="60" y="140">ANALYSIS WORKFLOW</text>')
    step_x = [60, 320, 580, 840, 1100, 1360]
    for idx, skill_id in enumerate(chain):
        fill = BLUE_BG if skill_id == "financial_summary_generation" else "#FFFFFF"
        stroke = BLUE if skill_id == "financial_summary_generation" else LINE
        card(
            lines,
            step_x[idx],
            200,
            220,
            118,
            labels[skill_id],
            skill_id,
            fill,
            stroke,
            f"Step {idx + 1}",
        )
        if idx > 0:
            arrow(
                lines,
                step_x[idx],
                259,
                step_x[idx - 1] + 220,
                259,
                "REQUIRES",
            )

    lines.append('<text class="section" x="60" y="430">FINANCIAL KG BRIDGE</text>')
    rounded_rect(lines, 60, 458, 1520, 260, "#FBFEFC", "#DCFCE7", 18, False)

    metric_skill = registry.skills["financial_metric_calculation"]
    metric_names = list(metric_skill.required_metrics)
    metric_x = [105, 345, 585, 825, 1065, 1305]
    for idx, metric in enumerate(metric_names[:6]):
        card(
            lines,
            metric_x[idx],
            540,
            190,
            88,
            metric,
            "Financial KG Metric",
            GREEN_BG,
            GREEN,
            "Metric",
            shadow=False,
        )

    arrow(lines, 690, 318, 690, 540, "REQUIRES_METRIC", dashed=True)

    card(
        lines,
        1150,
        745,
        370,
        88,
        "company_comparison",
        "비교 질문에서는 동일 연도 지표를 두 기업에서 조회",
        PURPLE_BG,
        PURPLE,
        "Alternative path",
        shadow=False,
    )
    arrow(lines, 1260, 318, 1330, 745, "REUSES", dashed=True, bend=60)

    lines.append("</svg>")
    return "\n".join(lines)


def skill_anatomy_svg(registry: SkillRegistry) -> str:
    skill = registry.skills["financial_metric_calculation"]

    lines = svg_start(
        1560,
        900,
        "SKILL.md",
        "Prompt 문장 하나가 아니라, 실행 순서와 입출력 조건을 함께 저장하는 작은 작업 단위",
    )

    card(
        lines,
        60,
        140,
        1440,
        112,
        skill.name,
        skill.description,
        BLUE_BG,
        BLUE,
        skill.skill_id,
    )

    lines.append('<text class="section" x="60" y="318">METADATA</text>')
    rounded_rect(lines, 60, 340, 620, 450, "#FFFFFF", "#E2E8F0", 18, True)

    metadata = [
        ("requires", ", ".join(skill.requires) or "-"),
        ("consumes", ", ".join(skill.consumes) or "-"),
        ("produces", ", ".join(skill.produces) or "-"),
        ("tools", ", ".join(skill.tools) or "-"),
        ("validation", ", ".join(skill.validation) or "-"),
        ("required_metrics", ", ".join(skill.required_metrics) or "-"),
    ]

    for idx, (key, value) in enumerate(metadata):
        y = 382 + idx * 62
        lines.append(f'<text class="tiny" x="92" y="{y}">{escape(key.upper())}</text>')
        lines.append(f'<text class="small" x="245" y="{y}">{escape(value)}</text>')
        if idx < len(metadata) - 1:
            lines.append(
                f'<line x1="92" y1="{y + 19}" x2="648" y2="{y + 19}" stroke="#E2E8F0"/>'
            )

    lines.append('<text class="section" x="760" y="318">INSTRUCTION</text>')
    rounded_rect(lines, 760, 340, 740, 450, "#0F172A", "#0F172A", 18, True)

    code_lines = [
        ("Objective", "재무비율을 동일한 공식으로 계산한다."),
        ("Procedure", "1. 필요한 Financial Fact 확인"),
        ("", "2. Python 공식으로 계산"),
        ("", "3. 사용한 source_id와 함께 반환"),
        ("Constraints", "없는 값은 만들지 않고 N/A 처리"),
        ("", "분모가 0이면 계산하지 않음"),
    ]
    y = 390
    for key, text_value in code_lines:
        if key:
            lines.append(
                f'<text x="800" y="{y}" font-family="monospace" font-size="12" font-weight="700" fill="#93C5FD">{escape(key)}</text>'
            )
            lines.append(
                f'<text x="930" y="{y}" font-family="monospace" font-size="12" fill="#E2E8F0">{escape(text_value)}</text>'
            )
        else:
            lines.append(
                f'<text x="930" y="{y}" font-family="monospace" font-size="12" fill="#E2E8F0">{escape(text_value)}</text>'
            )
        y += 48

    lines.append(
        '<text x="800" y="735" font-family="monospace" font-size="11" fill="#94A3B8">SKILL.md = metadata + procedure + constraint</text>'
    )

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

    for name, svg in assets.items():
        path = ASSET_DIR / name
        path.write_text(svg, encoding="utf-8")
        print(f"saved: {path}")


if __name__ == "__main__":
    main()
