from __future__ import annotations

import json
import re

import requests

from .skills import SkillRegistry


class LLMClient:
    """OpenAI-compatible chat completions endpoint를 최소 인터페이스로 사용합니다."""

    def __init__(self, api_url: str, api_key: str, model: str, timeout: int = 30):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def complete(self, system: str, user: str) -> str:
        response = requests.post(
            self.api_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return str(payload["choices"][0]["message"]["content"]).strip()

    def complete_json(self, system: str, user: str) -> dict:
        text = self.complete(system, user)
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError(f"LLM JSON 응답을 찾지 못했습니다: {text[:200]}")
        return json.loads(match.group(0))

    def render(
        self,
        query: str,
        result: dict,
        registry: SkillRegistry,
    ) -> str:
        skill_instructions = []
        for skill_id in result["skill_plan"]:
            skill = registry.skills[skill_id]
            skill_instructions.append(f"## {skill_id}\n{skill.body}")

        skills_text = "\n\n".join(skill_instructions)
        context = {
            "base_answer": result["answer"],
            "evidence": result["evidence"],
            "companies": result["companies"],
            "metric": result["metric"],
        }
        system = (
            "금융 분석 보조 역할이다. 제공된 계산 결과와 evidence만 사용한다. "
            "새로운 재무 수치, 출처, 사건을 만들지 않는다. 계산 결과를 다시 임의 계산하지 않는다. "
            "데이터가 부족하면 부족하다고 말한다. 짧고 실무적인 한국어로 답한다."
        )
        user = (
            f"질문: {query}\n\n"
            f"실행 결과:\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
            f"적용 SKILL:\n{skills_text}"
        )
        return self.complete(system, user)
