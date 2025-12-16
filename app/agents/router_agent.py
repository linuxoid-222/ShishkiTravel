from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from ..llm_factory import make_llm
from ..models import RouteDecision
from .json_utils import safe_pydantic_call

class RouterAgent:
    def __init__(self):
        self.llm = make_llm(temperature=0.0, max_tokens=650)

        self.prompt = ChatPromptTemplate.from_messages([
            ("system",
             "Ты оркестратор туристического бота. "
             "Задачи: (1) извлечь страну/город/даты/точки маршрута, (2) определить needs. "
             "needs может быть только: tourism, legal, weather, route. "
             "Если пользователь спрашивает про визы/законы/правила — legal. "
             "Если про погоду — weather. "
             "Если про маршрут/как добраться/путь/маршрут по достопримечательностям/план на день — route. "
             "Если про достопримечательности/культуру/советы — tourism. "
             "Если запрос общий и содержит несколько тем — включи несколько needs. "
             "КРИТИЧНО: верни ТОЛЬКО JSON-объект данных RouteDecision (не JSON Schema). "
             "НЕ используй ключи $defs/properties/required.\n"
             "{format_instructions}"),
            ("human",
             "ПАМЯТЬ: {memory_hint}\n"
             "СООБЩЕНИЕ: {text}\n"
             "Верни JSON RouteDecision, обязательно заполни user_question (можно повторить сообщение).")
        ])

    def decide(self, text: str, memory_hint: str = "") -> RouteDecision:
        variables = {
            "text": text,
            "memory_hint": memory_hint,
            "human_hint": f"Память: {memory_hint}\nСообщение: {text}\nВерни только JSON RouteDecision."
        }
        res = safe_pydantic_call(
            llm=self.llm,
            model=RouteDecision,
            prompt=self.prompt,
            variables=variables,
            repair_system=(
                "Ты исправляешь формат вывода. Верни только JSON-объект RouteDecision (данные). "
                "НЕ возвращай JSON Schema и не используй $defs/properties/required."
            ),
            max_retries=2,
        )
        if not res.user_question:
            res.user_question = text
        return res
