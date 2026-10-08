from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class SkillSpec:
    skill_id: str
    name: str
    description: str
    trigger_keywords: tuple[str, ...]
    requires: tuple[str, ...]
    consumes: tuple[str, ...]
    produces: tuple[str, ...]
    tools: tuple[str, ...]
    validation: tuple[str, ...]
    required_metrics: tuple[str, ...]
    body: str
    path: Path


def load_skill(path: str | Path) -> SkillSpec:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"SKILL front matter가 없습니다: {path}")

    _, front, body = text.split("---", 2)
    meta = yaml.safe_load(front) or {}
    skill_id = str(meta.get("skill_id", "")).strip()
    name = str(meta.get("name", "")).strip()
    if not skill_id or not name:
        raise ValueError(f"skill_id/name이 없습니다: {path}")

    def values(key: str) -> tuple[str, ...]:
        raw = meta.get(key) or []
        if isinstance(raw, str):
            raw = [raw]
        return tuple(str(v).strip() for v in raw if str(v).strip())

    return SkillSpec(
        skill_id=skill_id,
        name=name,
        description=str(meta.get("description", "")).strip(),
        trigger_keywords=values("trigger_keywords"),
        requires=values("requires"),
        consumes=values("consumes"),
        produces=values("produces"),
        tools=values("tools"),
        validation=values("validation"),
        required_metrics=values("required_metrics"),
        body=body.strip(),
        path=path,
    )


class SkillRegistry:
    def __init__(self, skills: dict[str, SkillSpec]):
        self.skills = skills
        self._validate_dependencies()

    @classmethod
    def load(cls, skills_dir: str | Path) -> "SkillRegistry":
        skills_dir = Path(skills_dir)
        skills = {}
        for path in sorted(skills_dir.glob("*/SKILL.md")):
            spec = load_skill(path)
            if spec.skill_id in skills:
                raise ValueError(f"중복 skill_id: {spec.skill_id}")
            skills[spec.skill_id] = spec
        if not skills:
            raise ValueError(f"SKILL 파일을 찾지 못했습니다: {skills_dir}")
        return cls(skills)

    def _validate_dependencies(self) -> None:
        for skill in self.skills.values():
            missing = [item for item in skill.requires if item not in self.skills]
            if missing:
                raise ValueError(f"{skill.skill_id}의 dependency가 없습니다: {missing}")

    def plan(self, skill_id: str) -> list[str]:
        if skill_id not in self.skills:
            raise KeyError(f"등록되지 않은 skill입니다: {skill_id}")

        result: list[str] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(current: str) -> None:
            if current in visited:
                return
            if current in visiting:
                raise ValueError(f"Skill dependency cycle이 있습니다: {current}")
            visiting.add(current)
            for dependency in self.skills[current].requires:
                visit(dependency)
            visiting.remove(current)
            visited.add(current)
            result.append(current)

        visit(skill_id)
        return result
