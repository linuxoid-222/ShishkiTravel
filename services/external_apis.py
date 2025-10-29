"""Utilities for calling external public APIs used by the travel bot.

This module encapsulates calls to free and paid APIs such as RestCountries,
OpenWeatherMap and Google Maps Directions. Each function returns
structured Python data or None if the request fails. By isolating these
calls here, agents remain focused on business logic rather than
HTTP intricacies, and fallback logic can be centralized.
"""

from __future__ import annotations

import requests
from typing import Optional, Dict, Any

try:
    import googlemaps  # type: ignore
except ImportError:
    googlemaps = None  # type: ignore
from ..config import settings


def get_country_info(name: str) -> Optional[Dict[str, Any]]:
    """Return basic information about a country using the RestCountries API.

    Parameters
    ----------
    name: str
        The common name of the country (e.g. "France", "Japan").

    Returns
    -------
    Optional[Dict[str, Any]]
        A dictionary with keys `name`, `capital`, `region`, `population`, `languages`.
        If the request fails or no data is found, returns None.
    """
    url = f"https://restcountries.com/v3.1/name/{name}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()[0]  # Take the first result
            return {
                "name": data.get("name", {}).get("common"),
                "capital": (data.get("capital") or [None])[0],
                "region": data.get("region"),
                "population": data.get("population"),
                "languages": ", ".join((data.get("languages") or {}).values()),
            }
    except Exception:
        pass
    return None


def get_weather(city: str) -> Optional[str]:
    """Return a human-readable weather string for the given city.

    Requires a valid OpenWeatherMap API key to be present in `settings.owm_key`.
    The result is localized to Russian and uses Celsius units. If no key is
    configured or the API call fails, returns None.
    """
    if not settings.owm_key:
        return None
    params = {
        "q": city,
        "appid": settings.owm_key,
        "units": "metric",
        "lang": "ru",
    }
    try:
        resp = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params=params,
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            desc = data["weather"][0]["description"].capitalize()
            temp = round(float(data["main"]["temp"]))
            return f"{desc}, {temp}°C"
    except Exception:
        pass
    return None


_gmaps_client: Optional[Any] = None
# Only initialize Google Maps client if the library and API key are available
if googlemaps and settings.gmaps_key:
    try:
        _gmaps_client = googlemaps.Client(key=settings.gmaps_key)
    except Exception:
        _gmaps_client = None


def get_route(origin: str, destination: str) -> Optional[str]:
    """Build a route summary between two locations using Google Maps Directions.

    Parameters
    ----------
    origin: str
        Starting point of the route (e.g. "Rome, Italy").
    destination: str
        Destination point of the route (e.g. "Florence, Italy").

    Returns
    -------
    Optional[str]
        A string summarizing distance, duration and first step, or None on failure.
    """
    if not _gmaps_client:
        return None
    try:
        directions = _gmaps_client.directions(
            origin,
            destination,
            mode="transit",
            language="ru",
        )
        if not directions:
            return None
        leg = directions[0]["legs"][0]
        dist = leg["distance"]["text"]
        dur = leg["duration"]["text"]
        step = leg.get("steps", [{}])[0]
        instr_html = step.get("html_instructions", "").replace("<b>", "").replace("</b>", "")
        return f"Маршрут: {origin} → {destination}. Дистанция: {dist}, время: {dur}. Первый шаг: {instr_html}"
    except Exception:
        return None
