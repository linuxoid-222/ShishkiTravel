

from __future__ import annotations

import re
from typing import Dict, Any, Tuple, List

from travel_bot.agents.legal_agent import LegalAgent
from travel_bot.agents.tourist_agent import TouristAgent
from travel_bot.agents.route_agent import RouteAgent
from travel_bot.agents.verifier_agent import VerifierAgent
from travel_bot.agents.responder_agent import ResponderAgent
from travel_bot.services.knowledge_base import find_country_key, find_city_global, find_city_key



LEGAL_KEYWORDS = ("виза", "зако", "штраф", "тамож", "правил")
WEATHER_KEYWORDS = ("погод", "температ", "climate")
ROUTE_KEYWORDS = ("маршрут", "добрат", "доех", "route")


def extract_country_and_city(q: str) -> Tuple[str | None, str | None]:

    names: List[str] = re.findall(r"\b[А-ЯЁA-Z][а-яёa-zA-Z]{2,}\b", q)
    if not names:
        return None, None
    if len(names) == 1:
        return names[0], None
    return names[0], names[1]


def extract_route_points(q: str) -> Tuple[str | None, str | None]:

    m = re.search(r"\b(?:из|from)\s+([\w\-\s]+?)\s+(?:в|to)\s+([\w\-\s]+)", q, flags=re.IGNORECASE)
    if m:
        origin = m.group(1).strip()
        dest = m.group(2).strip()
        return origin, dest
    return None, None


class Orchestrator:
    """Main controller that coordinates agents to answer user questions."""

    def __init__(self) -> None:
        self.legal_agent = LegalAgent()
        self.tourist_agent = TouristAgent()
        self.route_agent = RouteAgent()
        self.verifier_agent = VerifierAgent()
        self.responder_agent = ResponderAgent()

    def process(self, user_query: str) -> str:

        qlow = user_query.lower()
        categories: List[str] = []

        if any(k in qlow for k in LEGAL_KEYWORDS):
            categories.append("legal")
        if any(k in qlow for k in WEATHER_KEYWORDS):
            categories.append("weather/tourism")
        if any(k in qlow for k in ROUTE_KEYWORDS):
            categories.append("route")
        if not categories:
            categories.append("tourism")

        country: str | None = None
        city: str | None = None

        country = find_country_key(user_query)
        if country:

            city = find_city_key(country, user_query)
        else:

            city_pair = find_city_global(user_query)
            if city_pair:
                country = city_pair[0]
                city = city_pair[1]
        origin, dest = extract_route_points(user_query)

        context: Dict[str, Any] = {
            "country": country,
            "city": city,
            "origin": origin,
            "destination": dest,
        }

        evidence: Dict[str, str] = {}


        if "legal" in categories:
            res = self.legal_agent.answer(user_query, context)
            if res.get("content"):
                evidence[res["type"]] = res["content"]

        if any(cat in categories for cat in ["weather/tourism", "tourism"]):
            res = self.tourist_agent.answer(user_query, context)
            if res.get("content"):
                evidence[res["type"]] = res["content"]
        if "route" in categories:
            res = self.route_agent.answer(user_query, context)
            if res.get("content"):
                evidence[res["type"]] = res["content"]

        ver_res = self.verifier_agent.answer(user_query, context)
        if ver_res.get("content"):
            evidence[ver_res["type"]] = ver_res["content"]


        final_answer = self.responder_agent.generate(user_query, evidence)
        return final_answer
