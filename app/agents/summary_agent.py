from __future__ import annotations
from langchain_core.prompts import ChatPromptTemplate
from ..llm_factory import make_llm

class SummaryAgent:
    """Сжимает историю диалога до короткой "памяти" для следующих запросов."""

    def __init__(self):
        self.llm = make_llm(temperature=0.0, max_tokens=220)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system",
             "Ты модуль памяти для туристического бота. "
             "Обнови краткое резюме контекста поездки. "
             "Пиши 1-3 предложения, без лишнего. "
             "Сохраняй факты: направление, даты, интересы, бюджет, стиль, ограничения. "
             "Если новых данных нет — верни старое резюме как есть."),
            ("human",
             "СТАРОЕ РЕЗЮМЕ:\n{old_summary}\n\n"
             "ПОСЛЕДНИЕ СООБЩЕНИЯ:\n{recent}\n\n"
             "Новое резюме:")
        ])

    def update(self, old_summary: str, recent: str) -> str:
        return self.llm.invoke(self.prompt.format_messages(old_summary=old_summary or "", recent=recent or "")).content.strip()
