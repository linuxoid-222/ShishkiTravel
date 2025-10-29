

from __future__ import annotations

from typing import Dict, Any, List

from travel_bot.services.gigachat_api import gigachat
from .base import BaseAgent

try:
    from travel_bot.services.rag import retrieve as _rag_retrieve
    RAG_RETRIEVER = _rag_retrieve  
except Exception:
    RAG_RETRIEVER = None  


SYSTEM_PROMPT = (
    "Ты — умный ассистент-проводник для путешественников. "
    "Опирайся на предоставленные факты. Если чего-то нет — скажи об этом честно. "
    "Отвечай кратко, структурировано, на русском."
)


class ResponderAgent(BaseAgent):


    name = "responder"

    def generate(self, user_query: str, evidence: Dict[str, str]) -> str:

        messages: List[Dict[str, str]] = []
       
        messages.append({"role": "system", "content": SYSTEM_PROMPT})
        
        messages.append({"role": "user", "content": f"Вопрос пользователя: {user_query}"})

        rag_context = None
        if RAG_RETRIEVER:
            try:
                rag_text = RAG_RETRIEVER(user_query)
                if rag_text:
                    rag_context = f"[RAG]\n{rag_text}"
            except Exception:
                rag_context = None

        context_sections = []
        if evidence:
            for key, text in evidence.items():
                if text:
                    label = key.upper()
                    context_sections.append(f"[{label}]\n{text}")

        if rag_context:
            context_sections.insert(0, rag_context)

        context_blob = "\n\n".join(context_sections) if context_sections else "—"
        messages.append({"role": "user", "content": f"Контекстные данные:\n{context_blob}"})

        messages.append({"role": "user", "content": "Сформируй финальный ответ пользователю."})

        try:

            completion = gigachat.chat(messages, temperature=0.2, max_tokens=900)
            return completion
        except Exception:

            if evidence:
                return "\n\n".join(f"{k.upper()}: {v}" for k, v in evidence.items() if v)
            return "Извините, я не могу сформировать ответ."
