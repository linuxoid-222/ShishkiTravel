from __future__ import annotations

from typing import Dict, Any, List

from .base import BaseAgent, AgentResult
from travel_bot.services.rag import retrieve_advanced
from travel_bot.services.knowledge_base import find_country_key
from travel_bot.services.gigachat_api import gigachat
from travel_bot.services.external_apis import get_weather


class TouristAgent(BaseAgent):
    name = "tourism"

    def answer(self, query: str, context: Dict[str, Any]) -> AgentResult:
        # 1) Канонизация географии (страна/город из контекста; если страны нет — угадаем из запроса)
        country = context.get("country") or find_country_key(query or "")
        city = context.get("city")

        result = AgentResult(type=self.name, content="")
        parts: List[str] = []
        sources: List[str] = []

        if not country and not city:
            return result

        # 2) Формируем запрос + фильтры для RAG, фокус на туристические секции
        section_filter = ["culture", "attractions"]

        if country and city:
            rag_query = f"{country} {city} культура достопримечательности для туриста"
            filt = {"country": country, "city": city}
        elif country:
            rag_query = f"{country} культура достопримечательности для туриста"
            filt = {"country": country}
        else:
            rag_query = f"{city} культура достопримечательности для туриста"
            filt = None  

        docs = retrieve_advanced(
            rag_query,
            k=6,
            fetch_k=20,
            mmr=True,
            metadata_filter=filt,
            section_filter=section_filter,
        )

        if not docs:
            result["content"] = "Данных по запросу в локальной базе не найдено."
            return result


        for d in docs:
            parts.append(d.page_content.strip())
            meta = d.metadata or {}
            m_country = meta.get("country")
            m_city = meta.get("city")
            m_section = meta.get("section")
            src = " / ".join([x for x in [m_country, m_city, m_section] if x])
            if src:
                sources.append(src)
                
         if city:
             try:
                w = get_weather(city)
                 if w:
                     parts.append(f"Погода в {city}: {w}")
                     sources.append(f"{country or ''} / {city} / weather")
             except Exception:
                 pass

        # Уникальные источники
        uniq_sources = []
        seen = set()
        for s in sources:
            if s not in seen:
                seen.add(s)
                uniq_sources.append(s)
        if uniq_sources:
            parts.append("Источники:\n- " + "\n- ".join(uniq_sources))

        raw_text = "\n\n".join(parts)

        # 4) LLM 
        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "Ты — туристический ассистент. Используй ТОЛЬКО предоставленный CONTEXT. "
                        "Ничего не выдумывай. Разрешено структурировать и переформатировать, "
                        "но НЕ удаляй факты и НЕ сокращай смысл."
                    ),
                },
                {"role": "user", "content": f"[CONTEXT]\n{raw_text}"},
            ]
            summary = gigachat.chat(messages, temperature=0.2, max_tokens=1200)
            result["content"] = summary.strip() if isinstance(summary, str) and summary.strip() else raw_text
        except Exception:
            result["content"] = raw_text

        return result
