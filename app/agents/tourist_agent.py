from __future__ import annotations
from langchain_core.prompts import ChatPromptTemplate

from ..llm_factory import make_llm
from ..models import TourismResult
from .json_utils import safe_pydantic_call

class TouristAgent:
    def __init__(self):
        self.llm = make_llm(temperature=0.7, max_tokens=1800)

        self.prompt = ChatPromptTemplate.from_messages([
            ("system",
             "Ты туристический гид. Сформируй структурированный результат для Telegram-бота.\n"
             "КРИТИЧНО:\n"
             "- Верни ТОЛЬКО JSON-объект TourismResult (данные), без текста вокруг.\n"
             "- НЕ возвращай JSON Schema и не используй ключи $defs/properties/required.\n"
             "- destination_title: \"Город, Страна\".\n"
             "- overview: 3–6 предложений (что это за город, атмосфера, чем знаменит).\n"
             "- history: 3–6 предложений (очень кратко и понятно).\n"
             "- highlights: 7–10 мест. Для каждого места добавь query в формате: \"Название, Город, Страна\".\n"
             "- food_spots: 4–6 вариантов (рынки/улицы/районы/типы заведений), без точных адресов. Для каждого добавь query.\n"
             "- plan_1_day: 5–7 пунктов (утро/день/вечер) с местами из highlights.\n"
             "- Пиши по делу, без воды. Не выдумывай точные цены/расписания.\n"
             "{format_instructions}"),
            ("human",
             "Направление: {country}, {city}. Даты: {dates}\n"
             "Память/предпочтения (может быть пустой): {summary}\n"
             "Запрос: {question}\n"
             "Верни только JSON TourismResult.")
        ])

    def run(self, country: str | None, city: str | None, dates: str | None, question: str, summary: str = "") -> TourismResult:
        variables = {
            "country": country or "не указано",
            "city": city or "не указано",
            "dates": dates or "не указано",
            "question": question,
            "summary": summary or "",
            "human_hint": f"Направление: {country},{city}. Даты:{dates}. Запрос:{question}. Верни только JSON TourismResult."
        }
        res = safe_pydantic_call(
            llm=self.llm,
            model=TourismResult,
            prompt=self.prompt,
            variables=variables,
            repair_system=(
                "Ты исправляешь формат вывода. Верни только JSON-объект TourismResult (данные). "
                "НЕ возвращай JSON Schema и не используй $defs/properties/required."
            ),
            max_retries=2,
        )
        if not res.destination_title:
            parts = [p for p in [city, country] if p]
            res.destination_title = ", ".join(parts) if parts else "Путешествие"
        return res
