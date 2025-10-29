
from __future__ import annotations

from typing import Dict, Any

from .base import BaseAgent, AgentResult
from travel_bot.services.knowledge_base import get_country_sections, find_country_key
from travel_bot.services.gigachat_api import gigachat


class LegalAgent(BaseAgent):


    name = "legal"

    def answer(self, query: str, context: Dict[str, Any]) -> AgentResult:
        
        country = context.get("country") or find_country_key(query or "")
        result = AgentResult(type=self.name, content="")
        if not country:
            return result

        sections = get_country_sections(country, ["visa", "laws"])
        parts = []
        visa_info = sections.get("visa")
        if visa_info:
            parts.append(f"Виза: {visa_info}")
        laws_info = sections.get("laws")
        if laws_info:
            parts.append(f"Законы: {laws_info}")
        if parts:
            
            raw_text = "\n".join(parts)
           
            try:
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "Ты — юридический агент, помогающий путешественникам. "
                            "Переформулируй приведённую ниже информацию в краткий, "
                            "ясный ответ на русском."
                        ),
                    },
                    {"role": "user", "content": raw_text},
                ]
                summary = gigachat.chat(messages, temperature=0.3, max_tokens=400)
                
                if summary and isinstance(summary, str):
                    result["content"] = summary.strip()
                else:
                    result["content"] = raw_text
            except Exception:
                result["content"] = raw_text
        return result
