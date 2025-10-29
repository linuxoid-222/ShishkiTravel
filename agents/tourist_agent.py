
from __future__ import annotations

from typing import Dict, Any

from .base import BaseAgent, AgentResult
from travel_bot.services.knowledge_base import (
    get_country_sections,
    get_city_sections,
    find_country_key,
)
from travel_bot.services.external_apis import get_weather
from travel_bot.services.gigachat_api import gigachat


try:
    from travel_bot.services.rag import retrieve as _rag_retrieve
    RAG_RETRIEVER = _rag_retrieve 
except Exception:
    RAG_RETRIEVER = None  


class TouristAgent(BaseAgent):
    """Provide cultural and tourism information."""

    name = "tourism"

    def answer(self, query: str, context: Dict[str, Any]) -> AgentResult:

        country = context.get("country") or find_country_key(query or "")
        city = context.get("city")
        result = AgentResult(type=self.name, content="")
        parts: list[str] = []

        # -----------------------------
        # 1) Полные разделы по СТРАНЕ (если страна определена)
        # -----------------------------
        if country:
            sections = get_country_sections(country, ["culture", "attractions"])
            if sections.get("culture"):
                parts.append(f"Культура: {sections['culture']}")
            if sections.get("attractions"):
                parts.append(f"Что посмотреть: {sections['attractions']}")

        # -----------------------------
        # 2) Полные разделы по ГОРОДУ (если город определён)
        # -----------------------------
        if country and city:
            city_secs = get_city_sections(country, city, ["culture", "attractions"])
            if city_secs.get("culture"):
                parts.append(f"Город {city} — культура: {city_secs['culture']}")
            if city_secs.get("attractions"):
                parts.append(f"Город {city} — что посмотреть: {city_secs['attractions']}")

        # -----------------------------
        # 3) Погода по городу 
        # -----------------------------
        if city:
            weather = get_weather(city)
            if weather:
                parts.append(f"Погода в {city}: {weather}")

        # -----------------------------
        # 4) RAG
        # -----------------------------
        if parts:
            # Дополнить локальным RAG (если доступен)
            if RAG_RETRIEVER and country:
                try:
                    rag_query = f"{country} {city} культура достопримечательности" if city else f"{country} культура достопримечательности"
                    rag_text = RAG_RETRIEVER(rag_query, k=2)
                    if rag_text:
                        parts.append(f"Дополнительная информация: {rag_text}")
                except Exception:
                    pass

            raw_text = "\n".join(parts)


            try:
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "Ты — туристический агент. Сохрани все факты из предоставленного текста, "
                            "не сокращай и ничего не опускай. Можно переформатировать и упорядочить, "
                            "но содержательно текст должен остаться полным."
                        ),
                    },
                    {"role": "user", "content": raw_text},
                ]
                summary = gigachat.chat(messages, temperature=0.2, max_tokens=900)
                if summary and isinstance(summary, str):
                    result["content"] = summary.strip()
                else:
                    result["content"] = raw_text
            except Exception:
                result["content"] = raw_text

        return result
