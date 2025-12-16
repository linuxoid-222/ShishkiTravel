from __future__ import annotations
from langchain_core.prompts import ChatPromptTemplate

from ..llm_factory import make_llm
from ..models import LegalResult
from ..rag.legal_rag import LegalRAG
from .json_utils import safe_pydantic_call

class LegalAgent:
    def __init__(self, rag: LegalRAG | None = None):
        self.rag = rag or LegalRAG()
        # Give the model enough room to output full structured info
        self.llm = make_llm(temperature=0.0, max_tokens=1400)

        self.prompt = ChatPromptTemplate.from_messages([
            ("system",
             "Ты юридический помощник для путешественников.\n"
             "КРИТИЧНО: отвечай ТОЛЬКО на основе КОНТЕКСТА ниже (локальная база).\n"
             "НЕ добавляй факты, которых нет в контексте.\n"
             "\n"
             "Как заполнять поля LegalResult:\n"
             "- visa_required: true/false/null (если в контексте нет ответа — null)\n"
             "- visa: конкретные требования к визе / тип визы / сроки / документы (если есть)\n"
             "- entry_and_registration: правила въезда, сроки пребывания, регистрация, миграционные требования (если есть)\n"
             "- prohibitions_and_fines: запреты, ограничения, штрафы, важные риски (если есть)\n"
             "- recommendations: практические советы/что взять/куда обратиться (если есть)\n"
             "- sources: ИМЕНА ФАЙЛОВ из контекста (обязательно)\n"
             "- missing_info: заполняй, если база не содержит нужного (и тогда visa_required=null)\n"
             "\n"
             "ВАЖНО:\n"
             "- Если в контексте есть информация, НЕ оставляй соответствующие списки пустыми.\n"
             "- Переноси формулировки близко к оригиналу (можно слегка сократить).\n"
             "- Верни ТОЛЬКО JSON-объект LegalResult (данные). НЕ возвращай JSON Schema.\n"
             "{format_instructions}"),
            ("human",
             "Страна/город: {country}, {city}\n"
             "Вопрос: {question}\n\n"
             "КОНТЕКСТ:\n{context}\n\n"
             "Верни только JSON LegalResult.")
        ])

    def run(self, country: str | None, city: str | None, question: str) -> LegalResult:
        # Make query "dense" for retrieval: destination + explicit legal intent
        base_q = ", ".join([x for x in [city, country] if x]).strip()
        query = f"{base_q} визы законы правила въезда штрафы {question}".strip()
        chunks = self.rag.retrieve(query, country=country, k=10)

        if not chunks:
            return LegalResult(
                visa_required=None,
                missing_info="Локальная база пуста или индекс не построен. Добавьте документы в kb/legal и запустите: py -m scripts.build_legal_index",
                sources=[],
            )

        context = "\n\n".join([f"[{c.source}]\n{c.chunk}" for c in chunks])
        sources = sorted({c.source for c in chunks})

        variables = {
            "country": country or "не указано",
            "city": city or "не указано",
            "question": question,
            "context": context,
            "human_hint": f"Источники: {', '.join(sources)}. Верни только JSON LegalResult. Не оставляй поля пустыми если в контексте есть информация."
        }

        result = safe_pydantic_call(
            llm=self.llm,
            model=LegalResult,
            prompt=self.prompt,
            variables=variables,
            repair_system=(
                "Ты исправляешь формат. Верни только JSON-объект LegalResult (данные). "
                "Строго опирайся на контекст. НЕ возвращай JSON Schema."
            ),
            max_retries=2,
        )

        # Always include sources from retrieved chunks
        if not result.sources:
            result.sources = sources

        # If the model answered only visa_required but left everything empty, try a light second pass (still constrained)
        if (result.visa_required is not None) and not (result.visa or result.entry_and_registration or result.prohibitions_and_fines or result.recommendations) and not result.missing_info:
            variables2 = dict(variables)
            variables2["question"] = "Собери из контекста максимально подробные пункты по визе/въезду/штрафам."
            result2 = safe_pydantic_call(
                llm=self.llm,
                model=LegalResult,
                prompt=self.prompt,
                variables=variables2,
                repair_system=(
                    "Верни только JSON LegalResult. Заполни списки пунктами из контекста. "
                    "НЕ добавляй факты вне контекста."
                ),
                max_retries=1,
            )
            if not result2.sources:
                result2.sources = sources
            result = result2

        return result
