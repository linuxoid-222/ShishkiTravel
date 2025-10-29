

from __future__ import annotations

from typing import Dict, Any

from .base import BaseAgent, AgentResult
from travel_bot.services.gigachat_api import gigachat


class VerifierAgent(BaseAgent):


    name = "verifier"

    def answer(self, query: str, context: Dict[str, Any]) -> AgentResult:
        notes: list[str] = []
        qlow = query.lower()


        if any(k in qlow for k in ["виза", "зако", "штраф", "тамож", "правил"]):
            if not context.get("country"):
                notes.append("Уточните, для какой страны интересует легальная информация.")


        if any(k in qlow for k in ["маршрут", "добрат", "доехать", "route"]):
            if context.get("origin") and not context.get("destination"):
                notes.append("Укажите конечный пункт назначения для построения маршрута.")
            if context.get("destination") and not context.get("origin"):
                notes.append("Укажите начальную точку маршрута.")

        result = AgentResult(type=self.name, content="\n".join(notes) if notes else "")

        if notes:
            raw_text = "\n".join(notes)
            try:
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "Ты — агент проверки и уточнения. Сформулируй полученные примечания "
                            "вежливо и ясно, на русском языке."
                        ),
                    },
                    {"role": "user", "content": raw_text},
                ]
                summary = gigachat.chat(messages, temperature=0.3, max_tokens=200)
                if summary and isinstance(summary, str):
                    result["content"] = summary.strip()
            except Exception:
                # Keep raw notes if summarisation fails
                result["content"] = raw_text
        return result
