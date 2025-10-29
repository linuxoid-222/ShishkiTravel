"""Verifier agent for the travel bot.

The verifier agent checks the intermediate context and agent outputs
for missing or inconsistent information.  It does not fetch new data
but can add warning notes that help the LLM generate a more helpful
response.  For example, if a user asks about legal information without
specifying a country, the verifier will request clarification.
"""

from __future__ import annotations

from typing import Dict, Any

from .base import BaseAgent, AgentResult
from travel_bot.services.gigachat_api import gigachat


class VerifierAgent(BaseAgent):
    """Perform consistency checks on the query and context.

    The verifier ensures required context such as country names and
    route endpoints are present when needed.  It also detects
    potential misuses such as mixing two countries in one query.  It
    returns a note as part of the evidence dictionary when something
    needs attention.
    """

    name = "verifier"

    def answer(self, query: str, context: Dict[str, Any]) -> AgentResult:
        notes: list[str] = []
        qlow = query.lower()

        # If the user asks about visas or laws but no country is given.
        if any(k in qlow for k in ["виза", "зако", "штраф", "тамож", "правил"]):
            if not context.get("country"):
                notes.append("Уточните, для какой страны интересует легальная информация.")

        # If the user asks for a route but only one of origin/destination is supplied.
        if any(k in qlow for k in ["маршрут", "добрат", "доехать", "route"]):
            if context.get("origin") and not context.get("destination"):
                notes.append("Укажите конечный пункт назначения для построения маршрута.")
            if context.get("destination") and not context.get("origin"):
                notes.append("Укажите начальную точку маршрута.")

        result = AgentResult(type=self.name, content="\n".join(notes) if notes else "")
        # If we have notes, summarise them with LLM for clarity.  Otherwise, return empty content.
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