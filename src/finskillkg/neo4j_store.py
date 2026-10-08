from __future__ import annotations

import re

import networkx as nx
from neo4j import GraphDatabase


_SAFE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def _safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]", "_", value)
    if not _SAFE.match(value):
        raise ValueError(f"Neo4j label/relation으로 사용할 수 없습니다: {value}")
    return value


def sync_graph(
    graph: nx.MultiDiGraph,
    uri: str,
    user: str,
    password: str,
    database: str | None = None,
    clear: bool = False,
) -> dict:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    session_args = {"database": database} if database else {}

    with driver.session(**session_args) as session:
        session.run(
            "CREATE CONSTRAINT finskillkg_id IF NOT EXISTS "
            "FOR (n:KGNode) REQUIRE n.id IS UNIQUE"
        )
        if clear:
            session.run("MATCH (n:KGNode) DETACH DELETE n")

        for node_id, attrs in graph.nodes(data=True):
            label = _safe_name(str(attrs.get("node_type", "KGNode")))
            props = {k: v for k, v in attrs.items() if v is not None}
            props["id"] = str(node_id)
            session.run(
                f"MERGE (n:KGNode:{label} {{id: $id}}) SET n += $props",
                id=str(node_id),
                props=props,
            )

        for source, target, attrs in graph.edges(data=True):
            relation = _safe_name(str(attrs.get("relation", "RELATED_TO")))
            session.run(
                "MATCH (a:KGNode {id: $source}), (b:KGNode {id: $target}) "
                f"MERGE (a)-[r:{relation}]->(b)",
                source=str(source),
                target=str(target),
            )

    driver.close()
    return {"nodes": graph.number_of_nodes(), "edges": graph.number_of_edges()}
