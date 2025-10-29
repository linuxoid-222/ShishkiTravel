
from __future__ import annotations

import requests
from typing import Optional, Dict, Any

try:
    import googlemaps  
except ImportError:
    googlemaps = None  
from ..config import settings


def get_country_info(name: str) -> Optional[Dict[str, Any]]:

    url = f"https://restcountries.com/v3.1/name/{name}"
    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()[0] 
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

if googlemaps and settings.gmaps_key:
    try:
        _gmaps_client = googlemaps.Client(key=settings.gmaps_key)
    except Exception:
        _gmaps_client = None


def get_route(origin: str, destination: str) -> Optional[str]:

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
