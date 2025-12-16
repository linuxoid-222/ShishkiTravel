from __future__ import annotations
from typing import Type, TypeVar, Optional
from pydantic import BaseModel
from langchain.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models.chat_models import BaseChatModel

T = TypeVar("T", bound=BaseModel)

_SCHEMA_MARKERS = ['"$defs"', '"properties"', '"required"', '"title"', '"type"']

def looks_like_schema(text: str) -> bool:
    t = text or ""
    return any(m in t for m in _SCHEMA_MARKERS)

def safe_pydantic_call(
    llm: BaseChatModel,
    model: Type[T],
    prompt: ChatPromptTemplate,
    variables: dict,
    repair_system: str,
    max_retries: int = 2,
) -> T:
    """Robust call that prevents 'JSON Schema' answers and retries parsing.

    We intentionally avoid OutputFixingParser here because some models will 'fix' into schema again.
    This helper uses an explicit repair prompt and falls back to defaults.
    """
    parser = PydanticOutputParser(pydantic_object=model)

    last_text: Optional[str] = None
    for _ in range(max_retries + 1):
        msgs = prompt.format_messages(**variables, format_instructions=parser.get_format_instructions())
        text = llm.invoke(msgs).content
        last_text = text

        if looks_like_schema(text):
            # hard repair if model returned schema
            repair_prompt = ChatPromptTemplate.from_messages([
                ("system", repair_system + "\n" + parser.get_format_instructions()),
                ("human", variables.get("human_hint","") or "Верни только JSON-объект данных.")
            ])
            text = llm.invoke(repair_prompt.format_messages()).content
            last_text = text

        try:
            return parser.parse(text)
        except Exception:
            repair_prompt = ChatPromptTemplate.from_messages([
                ("system", repair_system + "\n" + parser.get_format_instructions()),
                ("human", f"Вот твой неверный ответ:\n{text}\n\nИсправь и верни только корректный JSON-объект данных.")
            ])
            last_text = llm.invoke(repair_prompt.format_messages()).content
            try:
                return parser.parse(last_text)
            except Exception:
                continue

    return model()  # type: ignore
