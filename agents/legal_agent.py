"""Legal agent for the travel bot.

This agent answers questions about visas, entry requirements and laws in a
given country.  It consults the internal knowledge base where such
information is stored.  If no information is found for a particular
country, the agent returns an empty result.  The orchestrator will
combine results from multiple agents before handing them to the LLM.

The knowledge base is expected to store data in a nested dictionary
with keys for each country and values containing sections like
``"visa"`` and ``"laws"``.  See ``data/knowledge_base.json`` for an
example.
"""

from __future__ import annotations

from typing import Dict, Any

from .base import BaseAgent, AgentResult
from travel_bot.services.knowledge_base import get_country_sections, find_country_key
from travel_bot.services.gigachat_api import gigachat


class LegalAgent(BaseAgent):
    """Return legal and visa information for the requested country.

    This agent uses simple heuristics to extract the country name from
    either the provided context or the user query.  It then queries
    the knowledge base for 'visa' and 'laws' sections.  If data is
    found, it's returned as a single string.  Otherwise an empty
    ``AgentResult`` is returned.
    """

    name = "legal"

    def answer(self, query: str, context: Dict[str, Any]) -> AgentResult:
        # Determine the country from context or query using fuzzy matching.
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
            # Join the raw parts into a single text
            raw_text = "\n".join(parts)
            # Use the LLM to summarise the legal information into a concise
            # explanation.  Wrap the call in a try/except so that if
            # credentials are missing or the API is unavailable, we fall
            # back to returning the raw text.  This pattern keeps the
            # agent self-contained and independent of downstream logic.
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
                # If the summary is non-empty, use it.  Otherwise, use the raw text.
                if summary and isinstance(summary, str):
                    result["content"] = summary.strip()
                else:
                    result["content"] = raw_text
            except Exception:
                result["content"] = raw_text
        return result