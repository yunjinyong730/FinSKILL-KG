from __future__ import annotations

import json
from pathlib import Path

from .graph import DualKnowledgeGraph
from .normalize import load_financial_csv, validate_financial_frame
from .skills import SkillRegistry


def run_pipeline(
    data_path: str | Path = "data/sample_financials.csv",
    skills_dir: str | Path = "skills",
    output_dir: str | Path = "outputs",
) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    frame = load_financial_csv(data_path)
    validation_issues = validate_financial_frame(frame)
    registry = SkillRegistry.load(skills_dir)

    graph = DualKnowledgeGraph()
    graph.add_financial_data(frame)
    graph.add_skill_registry(registry)

    graph.export_json(output_dir / "dual_kg.json")
    frame.to_csv(output_dir / "financial_facts.csv", index=False)
    validation_issues.to_csv(output_dir / "validation_issues.csv", index=False)

    summary = graph.summary()
    summary.update(
        {
            "data_path": str(data_path),
            "skills_dir": str(skills_dir),
            "validation_issues": int(len(validation_issues)),
        }
    )
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary
