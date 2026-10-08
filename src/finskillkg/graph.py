from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import pandas as pd

from .normalize import METRIC_LABELS
from .skills import SkillRegistry


class DualKnowledgeGraph:
    def __init__(self):
        self.graph = nx.MultiDiGraph()

    def _add_edge(self, source: str, target: str, relation: str) -> None:
        existing = self.graph.get_edge_data(source, target, default={})
        if any(attrs.get("relation") == relation for attrs in existing.values()):
            return
        self.graph.add_edge(source, target, relation=relation)

    @staticmethod
    def _company_id(code: str) -> str:
        return f"company:{code}"

    @staticmethod
    def _metric_id(metric: str) -> str:
        return f"metric:{metric}"

    def add_financial_data(self, frame: pd.DataFrame) -> None:
        for row in frame.to_dict("records"):
            company_id = self._company_id(str(row["company_code"]))
            metric_id = self._metric_id(str(row["metric"]))
            period_id = f"period:{int(row['year'])}"
            report_id = f"report:{row['source_id']}"
            fact_id = (
                f"fact:{row['company_code']}:{int(row['year'])}:{row['metric']}"
            )

            self.graph.add_node(
                company_id,
                node_type="Company",
                graph="financial",
                code=str(row["company_code"]),
                name=str(row["company_name"]),
            )
            self.graph.add_node(
                metric_id,
                node_type="Metric",
                graph="financial",
                metric=str(row["metric"]),
                name=METRIC_LABELS[str(row["metric"])],
            )
            self.graph.add_node(
                period_id,
                node_type="Period",
                graph="financial",
                year=int(row["year"]),
                name=str(int(row["year"])),
            )
            self.graph.add_node(
                report_id,
                node_type="Report",
                graph="financial",
                source_id=str(row["source_id"]),
                name=str(row["source_name"]),
                source_url=str(row.get("source_url", "")),
            )
            self.graph.add_node(
                fact_id,
                node_type="FinancialFact",
                graph="financial",
                value=float(row["value"]),
                unit=str(row["unit"]),
                year=int(row["year"]),
                metric=str(row["metric"]),
                source_id=str(row["source_id"]),
            )

            self._add_edge(company_id, fact_id, "HAS_FINANCIAL_FACT")
            self._add_edge(fact_id, metric_id, "OF_METRIC")
            self._add_edge(fact_id, period_id, "FOR_PERIOD")
            self._add_edge(fact_id, report_id, "EXTRACTED_FROM")
            self._add_edge(company_id, report_id, "HAS_REPORT")

    def add_skill_registry(self, registry: SkillRegistry) -> None:
        for skill in registry.skills.values():
            skill_node = f"skill:{skill.skill_id}"
            self.graph.add_node(
                skill_node,
                node_type="Skill",
                graph="skill",
                skill_id=skill.skill_id,
                name=skill.name,
                description=skill.description,
                path=str(skill.path),
            )

            for dependency in skill.requires:
                self._add_edge(skill_node, f"skill:{dependency}", "REQUIRES")

            for item in skill.consumes:
                node_id = f"datatype:{item}"
                self.graph.add_node(
                    node_id,
                    node_type="DataType",
                    graph="skill",
                    name=item,
                )
                self._add_edge(skill_node, node_id, "CONSUMES")

            for item in skill.produces:
                node_id = f"output:{item}"
                self.graph.add_node(
                    node_id,
                    node_type="OutputType",
                    graph="skill",
                    name=item,
                )
                self._add_edge(skill_node, node_id, "PRODUCES")

            for item in skill.tools:
                node_id = f"tool:{item}"
                self.graph.add_node(
                    node_id,
                    node_type="Tool",
                    graph="skill",
                    name=item,
                )
                self._add_edge(skill_node, node_id, "USES_TOOL")

            for item in skill.validation:
                node_id = f"rule:{item}"
                self.graph.add_node(
                    node_id,
                    node_type="ValidationRule",
                    graph="skill",
                    name=item,
                )
                self._add_edge(skill_node, node_id, "VALIDATED_BY")

            for metric in skill.required_metrics:
                metric_id = self._metric_id(metric)
                if metric_id not in self.graph:
                    self.graph.add_node(
                        metric_id,
                        node_type="Metric",
                        graph="financial",
                        metric=metric,
                        name=METRIC_LABELS.get(metric, metric),
                    )
                self._add_edge(skill_node, metric_id, "REQUIRES_METRIC")

    def company_names(self) -> list[str]:
        names = [
            attrs["name"]
            for _, attrs in self.graph.nodes(data=True)
            if attrs.get("node_type") == "Company"
        ]
        return sorted(names)

    def company_code(self, company_name: str) -> str:
        for _, attrs in self.graph.nodes(data=True):
            if attrs.get("node_type") == "Company" and attrs.get("name") == company_name:
                return str(attrs["code"])
        raise KeyError(f"등록되지 않은 기업입니다: {company_name}")

    def facts(self, company_name: str) -> pd.DataFrame:
        code = self.company_code(company_name)
        company_id = self._company_id(code)
        rows = []
        for _, fact_id, edge in self.graph.out_edges(company_id, data=True):
            if edge.get("relation") != "HAS_FINANCIAL_FACT":
                continue
            fact = self.graph.nodes[fact_id]
            rows.append(
                {
                    "company_code": code,
                    "company_name": company_name,
                    "year": int(fact["year"]),
                    "metric": str(fact["metric"]),
                    "value": float(fact["value"]),
                    "unit": str(fact["unit"]),
                    "source_id": str(fact["source_id"]),
                }
            )
        return pd.DataFrame(rows).sort_values(["year", "metric"]).reset_index(drop=True)

    def sources(self, company_name: str, years: list[int] | None = None) -> list[dict]:
        frame = self.facts(company_name)
        if years:
            frame = frame[frame["year"].isin(years)]
        result = []
        for source_id in frame["source_id"].drop_duplicates():
            report = self.graph.nodes.get(f"report:{source_id}", {})
            result.append(
                {
                    "source_id": source_id,
                    "source_name": report.get("name", "Unknown source"),
                    "source_url": report.get("source_url", ""),
                }
            )
        return result

    def summary(self) -> dict:
        node_types: dict[str, int] = {}
        relation_types: dict[str, int] = {}
        for _, attrs in self.graph.nodes(data=True):
            node_type = str(attrs.get("node_type", "Unknown"))
            node_types[node_type] = node_types.get(node_type, 0) + 1
        for _, _, attrs in self.graph.edges(data=True):
            relation = str(attrs.get("relation", "Unknown"))
            relation_types[relation] = relation_types.get(relation, 0) + 1
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "companies": node_types.get("Company", 0),
            "facts": node_types.get("FinancialFact", 0),
            "skills": node_types.get("Skill", 0),
            "bridges": relation_types.get("REQUIRES_METRIC", 0),
            "node_types": node_types,
            "relation_types": relation_types,
        }

    def export_json(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = nx.node_link_data(self.graph, edges="edges")
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def from_json(cls, path: str | Path) -> "DualKnowledgeGraph":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        instance = cls()
        instance.graph = nx.node_link_graph(payload, edges="edges", directed=True, multigraph=True)
        return instance
