"""Route agent for the travel bot.

This agent provides basic routing information between two points.  It
relies on an external mapping service (Google Maps) configured in
``services.external_apis``.  If no origin or destination is supplied
in the context, the agent returns an empty result.  The returned
string can include distance and travel time when available.
"""

from __future__ import annotations

from typing import Dict, Any

from .base import BaseAgent, AgentResult
from travel_bot.services.external_apis import get_route
from travel_bot.services.gigachat_api import gigachat


class RouteAgent(BaseAgent):
    """Build travel directions between two locations.

    The agent expects ``origin`` and ``destination`` keys in the
    context.  If both are present, it calls the external API to
    construct a summary of the route.  Otherwise it returns an empty
    result.  If the API call fails, the content remains empty.
    """

    name = "route"

    def answer(self, query: str, context: Dict[str, Any]) -> AgentResult:
        origin = context.get("origin")
        destination = context.get("destination")
        result = AgentResult(type=self.name, content="")
        if not origin or not destination:
            return result

        route_info = get_route(origin, destination)
        # If we successfully retrieved the route, summarise it via the LLM.
        if route_info:
            raw_text = route_info
            try:
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "Ты — агент по построению маршрутов. Перескажи полученную информацию "
                            "о маршруте кратко и понятно для путешественника."
                        ),
                    },
                    {"role": "user", "content": raw_text},
                ]
                summary = gigachat.chat(messages, temperature=0.3, max_tokens=200)
                if summary and isinstance(summary, str):
                    result["content"] = summary.strip()
                else:
                    result["content"] = raw_text
            except Exception:
                result["content"] = raw_text
        else:
            # Graceful fallback: no route computed
            result["content"] = (
                f"Не удалось построить маршрут между {origin} и {destination}. "
                "Возможно, сервис маршрутов временно недоступен."
            )
        return result