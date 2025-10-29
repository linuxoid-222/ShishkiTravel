"""Orchestrator for the travel bot.

The orchestrator analyses the user's question, extracts relevant
entities such as country and city names, selects which agents need to
be invoked and aggregates their outputs.  After gathering evidence
from selected agents it calls the responder agent to generate the
final answer.

This module defines a handful of helper functions for parsing user
queries.  These functions use simple heuristics (regular expressions)
to identify countries, cities and route endpoints.  For a more robust
solution consider integrating a proper named entity recognizer.
"""

from __future__ import annotations

import re
from typing import Dict, Any, Tuple, List

from travel_bot.agents.legal_agent import LegalAgent
from travel_bot.agents.tourist_agent import TouristAgent
from travel_bot.agents.route_agent import RouteAgent
from travel_bot.agents.verifier_agent import VerifierAgent
from travel_bot.agents.responder_agent import ResponderAgent
from travel_bot.services.knowledge_base import find_country_key, find_city_global, find_city_key


# Keyword groups for determining which agents to run.
LEGAL_KEYWORDS = ("виза", "зако", "штраф", "тамож", "правил")
WEATHER_KEYWORDS = ("погод", "температ", "climate")
ROUTE_KEYWORDS = ("маршрут", "добрат", "доех", "route")


def extract_country_and_city(q: str) -> Tuple[str | None, str | None]:
    """Attempt to extract a country and city name from the query.

    This function uses a simplistic heuristic: any capitalised word
    longer than three characters is considered a potential geographical
    name.  The first such word is treated as the country and the
    second as the city.  If only one name is found it's considered a
    country.  The function returns `(country, city)` which may
    include ``None`` values.

    Note: this heuristic is far from perfect.  Users may mention
    cities before countries or not capitalise names.  The
    ``knowledge_base.find_country_key`` function is used downstream
    to map names to canonical country keys.  For a production system
    consider using a named entity recognition library.
    """
    # Match words starting with an uppercase letter; supports Unicode.
    names: List[str] = re.findall(r"\b[А-ЯЁA-Z][а-яёa-zA-Z]{2,}\b", q)
    if not names:
        return None, None
    if len(names) == 1:
        return names[0], None
    return names[0], names[1]


def extract_route_points(q: str) -> Tuple[str | None, str | None]:
    """Parse origin and destination from phrases like "из X в Y".

    Uses a regular expression to capture text after 'из' and 'в'.  The
    expression is case-insensitive and matches Cyrillic and Latin
    characters.  Returns a tuple of (origin, destination) or
    ``(None, None)`` if no match is found.
    """
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
        """Process a user query and produce a combined response.

        The orchestrator first determines which agents should handle the
        question by scanning for keywords.  It extracts country, city
        and route endpoints from the query using helper functions and
        passes them in a context dictionary.  It then collects
        evidence from each selected agent, runs the verifier to
        identify any missing information and finally calls the
        responder agent to generate the final answer.
        """
        qlow = user_query.lower()
        categories: List[str] = []

        # Identify categories based on keywords; default to tourism.
        if any(k in qlow for k in LEGAL_KEYWORDS):
            categories.append("legal")
        if any(k in qlow for k in WEATHER_KEYWORDS):
            categories.append("weather/tourism")
        if any(k in qlow for k in ROUTE_KEYWORDS):
            categories.append("route")
        if not categories:
            categories.append("tourism")

        # Determine country and city using fuzzy matching.
        country: str | None = None
        city: str | None = None
        # First attempt to find a country in the full query.
        country = find_country_key(user_query)
        if country:
            # If a country is found, try to find a city within that country from the query.
            city = find_city_key(country, user_query)
        else:
            # If no country is found, attempt to identify a city globally (which also yields a country).
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

        # Gather evidence from selected agents.  Each agent returns an
        # AgentResult object with a 'content' field (string) that is
        # stored in the evidence dictionary under its type name.
        if "legal" in categories:
            res = self.legal_agent.answer(user_query, context)
            if res.get("content"):
                evidence[res["type"]] = res["content"]
        # Touristic information covers both culture and weather.  We
        # always call the tourist agent if 'tourism' or 'weather' is in
        # categories.
        if any(cat in categories for cat in ["weather/tourism", "tourism"]):
            res = self.tourist_agent.answer(user_query, context)
            if res.get("content"):
                evidence[res["type"]] = res["content"]
        if "route" in categories:
            res = self.route_agent.answer(user_query, context)
            if res.get("content"):
                evidence[res["type"]] = res["content"]

        # Run verifier at the end to add notes; this helps the LLM
        # request clarifications when needed.
        ver_res = self.verifier_agent.answer(user_query, context)
        if ver_res.get("content"):
            evidence[ver_res["type"]] = ver_res["content"]

        # Use the responder agent to produce the final answer.
        final_answer = self.responder_agent.generate(user_query, evidence)
        return final_answer