from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.finskillkg.config import Neo4jConfig
from src.finskillkg.graph import DualKnowledgeGraph
from src.finskillkg.neo4j_store import sync_graph


def main() -> None:
    parser = argparse.ArgumentParser(description="Dual KG를 Neo4j로 저장")
    parser.add_argument("--graph", default="outputs/dual_kg.json")
    parser.add_argument("--clear", action="store_true")
    args = parser.parse_args()

    config = Neo4jConfig.from_env()
    graph = DualKnowledgeGraph.from_json(args.graph)
    result = sync_graph(
        graph.graph,
        uri=config.uri,
        user=config.user,
        password=config.password,
        database=config.database,
        clear=args.clear,
    )
    print(f"synced: {result['nodes']} nodes, {result['edges']} edges")


if __name__ == "__main__":
    main()
