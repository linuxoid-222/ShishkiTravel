"""Responder agent for the travel bot.

This agent orchestrates the final call to the GigaChat LLM.  It
combines the user's original question with evidence gathered from
other agents (legal, tourism, route, verifier) and crafts a prompt
designed to produce a concise, informative answer.  If no LLM token
is configured, the agent returns a fallback response built directly
from the evidence.
"""

from __future__ import annotations

from typing import Dict, Any, List

from travel_bot.services.gigachat_api import gigachat
from .base import BaseAgent

# Import the RAG retriever if available.  If optional dependencies
# (langchain, chromadb, sentence-transformers) are not installed, the
# import will fail and `RAG_RETRIEVER` will remain None.  This
# conditional import allows the bot to function without RAG support.
try:
    from travel_bot.services.rag import retrieve as _rag_retrieve
    RAG_RETRIEVER = _rag_retrieve  # type: ignore
except Exception:
    RAG_RETRIEVER = None  # type: ignore


SYSTEM_PROMPT = (
    "Ты — умный ассистент-проводник для путешественников. "
    "Опирайся на предоставленные факты. Если чего-то нет — скажи об этом честно. "
    "Отвечай кратко, структурировано, на русском."
)


class ResponderAgent(BaseAgent):
    """Generate the final user-facing answer using GigaChat.

    The responder agent is not called via the standard ``answer``
    method because it does not accept context in the same way.  Instead
    the orchestrator calls ``generate`` after collecting evidence from
    other agents.  This method builds a prompt containing the user
    query, the concatenated evidence and then calls the GigaChat API.
    If the API credentials are missing, it falls back to returning the
    evidence as a plain concatenation.
    """

    name = "responder"

    def generate(self, user_query: str, evidence: Dict[str, str]) -> str:
        # Build prompt messages for the chat completion.
        # The LLM will see the system prompt first, then a user message
        # containing the original query, followed by another user message
        # with the evidence.  Finally we instruct the model to produce a
        # final answer.
        #
        # Evidence sections are labelled by the type of agent so the LLM
        # can interpret them.
        messages: List[Dict[str, str]] = []
        # System prompt defines the persona and guidelines for the LLM
        messages.append({"role": "system", "content": SYSTEM_PROMPT})
        # Original user query
        messages.append({"role": "user", "content": f"Вопрос пользователя: {user_query}"})

        # Retrieve additional context via RAG if available.  We wrap the call
        # in a try/except to gracefully handle missing dependencies.  The
        # retrieved text is labelled [RAG] so the model knows its origin.
        rag_context = None
        if RAG_RETRIEVER:
            try:
                rag_text = RAG_RETRIEVER(user_query)
                if rag_text:
                    rag_context = f"[RAG]\n{rag_text}"
            except Exception:
                rag_context = None

        # Build context blob from evidence provided by agents.  Each piece is
        # labelled with the agent type (uppercased) for clarity.
        context_sections = []
        if evidence:
            for key, text in evidence.items():
                if text:
                    label = key.upper()
                    context_sections.append(f"[{label}]\n{text}")
        # Prepend RAG context if present
        if rag_context:
            context_sections.insert(0, rag_context)
        # If no context available, use a placeholder
        context_blob = "\n\n".join(context_sections) if context_sections else "—"
        messages.append({"role": "user", "content": f"Контекстные данные:\n{context_blob}"})
        # Final instruction to the model
        messages.append({"role": "user", "content": "Сформируй финальный ответ пользователю."})

        try:
            # Attempt to call the GigaChat API.  If the credentials
            # aren't set or the request fails, an exception will be
            # thrown.  We'll catch it and return the evidence as-is.
            completion = gigachat.chat(messages, temperature=0.2, max_tokens=900)
            return completion
        except Exception:
            # Fallback: just concatenate the evidence.  This ensures the
            # user still receives some information if the LLM call
            # fails.  We do not attempt to paraphrase or translate here.
            if evidence:
                return "\n\n".join(f"{k.upper()}: {v}" for k, v in evidence.items() if v)
            return "Извините, я не могу сформировать ответ."