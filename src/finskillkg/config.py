from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ProjectConfig:
    data_path: Path = Path("data/sample_financials.csv")
    skills_dir: Path = Path("skills")
    output_dir: Path = Path("outputs")


@dataclass(frozen=True)
class DartConfig:
    api_key: str
    timeout: int = 20

    @classmethod
    def from_env(cls) -> "DartConfig":
        api_key = os.getenv("DART_API_KEY", "").strip()
        if not api_key:
            raise ValueError("DART_API_KEY 환경변수가 필요합니다.")
        return cls(api_key=api_key)


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str
    user: str
    password: str
    database: Optional[str] = None

    @classmethod
    def from_env(cls) -> "Neo4jConfig":
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687").strip()
        user = os.getenv("NEO4J_USER", "neo4j").strip()
        password = os.getenv("NEO4J_PASSWORD", "").strip()
        database = os.getenv("NEO4J_DATABASE", "neo4j").strip() or None
        if not password:
            raise ValueError("NEO4J_PASSWORD 환경변수가 필요합니다.")
        return cls(uri=uri, user=user, password=password, database=database)


@dataclass(frozen=True)
class LLMConfig:
    api_url: str
    api_key: str
    model: str
    timeout: int = 30

    @classmethod
    def from_env(cls) -> "LLMConfig":
        api_url = os.getenv("LLM_API_URL", "").strip()
        api_key = os.getenv("LLM_API_KEY", "").strip()
        model = os.getenv("LLM_MODEL", "").strip()
        if not api_url or not api_key or not model:
            raise ValueError("LLM_API_URL, LLM_API_KEY, LLM_MODEL 환경변수가 필요합니다.")
        return cls(api_url=api_url, api_key=api_key, model=model)
