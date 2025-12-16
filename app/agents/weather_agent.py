from __future__ import annotations

from typing import Optional, Tuple, List
import datetime as dt
import httpx

from ..models import WeatherResult
from ..config import settings
from ..cache import TTLCache

_WEATHER_CODE_RU = {
    0: "ясно",
    1: "в основном ясно",
    2: "переменная облачность",
    3: "пасмурно",
    45: "туман",
    48: "изморозевый туман",
    51: "морось (слабая)",
    53: "морось (умеренная)",
    55: "морось (сильная)",
    56: "ледяная морось (слабая)",
    57: "ледяная морось (сильная)",
    61: "дождь (слабый)",
    63: "дождь (умеренный)",
    65: "дождь (сильный)",
    66: "ледяной дождь (слабый)",
    67: "ледяной дождь (сильный)",
    71: "снег (слабый)",
    73: "снег (умеренный)",
    75: "снег (сильный)",
    77: "снежные зёрна",
    80: "ливни (слабые)",
    81: "ливни (умеренные)",
    82: "ливни (сильные)",
    85: "снегопад (слабый)",
    86: "снегопад (сильный)",
    95: "гроза",
    96: "гроза с градом (слабая)",
    99: "гроза с градом (сильная)",
}

class WeatherAgent:
    """Погода через Open-Meteo (без ключей)."""

    def __init__(self, cache: TTLCache | None = None):
        self.cache = cache or TTLCache(default_ttl_seconds=1800)

    async def _geocode_open_meteo(self, name: str) -> Optional[Tuple[float, float, str]]:
        q = (name or "").strip()
        if not q:
            return None

        cache_key = f"om_geo:{q.lower()}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        url = f"{settings.open_meteo_geocoding_url}/search"
        params = {"name": q, "count": 1, "language": "ru", "format": "json"}
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json() or {}
            results = data.get("results") or []
            if not results:
                return None
            lat = float(results[0]["latitude"])
            lon = float(results[0]["longitude"])
            display = results[0].get("name") or q
            country = results[0].get("country") or ""
            admin1 = results[0].get("admin1") or ""
            label = ", ".join([x for x in [display, admin1, country] if x]).strip()
            out = (lat, lon, label)
            self.cache.set(cache_key, out, ttl_seconds=24 * 3600)
            return out

    async def _forecast_open_meteo(self, lat: float, lon: float) -> dict:
        cache_key = f"om_fc:{lat:.4f},{lon:.4f}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        url = f"{settings.open_meteo_base_url}/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max,windspeed_10m_max",
            "current_weather": "true",
            "timezone": "auto",
            "forecast_days": 3,
        }
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
            self.cache.set(cache_key, data, ttl_seconds=1800)
            return data

    @staticmethod
    def _pick_day(daily: dict, idx: int = 0) -> dict:
        def get_arr(key: str):
            arr = daily.get(key)
            return arr[idx] if isinstance(arr, list) and len(arr) > idx else None
        return {
            "date": get_arr("time"),
            "code": get_arr("weathercode"),
            "tmax": get_arr("temperature_2m_max"),
            "tmin": get_arr("temperature_2m_min"),
            "pp": get_arr("precipitation_probability_max"),
            "wind": get_arr("windspeed_10m_max"),
        }

    @staticmethod
    def _ru_desc(code: Optional[int]) -> str:
        if code is None:
            return "нет данных"
        return _WEATHER_CODE_RU.get(int(code), f"код {code}")

    async def run(self, country: str | None, city: str | None) -> WeatherResult:
        place = ", ".join([p for p in [city, country] if p]).strip()
        if not place:
            return WeatherResult(place="", summary="Не указана локация для прогноза.")

        geo = await self._geocode_open_meteo(place)
        if not geo:
            return WeatherResult(place=place, summary="Не удалось найти локацию. Уточни город/страну.")

        lat, lon, label = geo
        data = await self._forecast_open_meteo(lat, lon)
        daily = (data or {}).get("daily") or {}
        day0 = self._pick_day(daily, 0)

        cur = (data or {}).get("current_weather") or {}
        now_temp = cur.get("temperature")
        wind_now = cur.get("windspeed")

        desc = self._ru_desc(day0.get("code"))
        date_str = day0.get("date") or ""
        pretty_date = date_str
        try:
            d = dt.date.fromisoformat(date_str)
            pretty_date = d.strftime("%d.%m.%Y")
        except Exception:
            pass

        tmin = day0.get("tmin")
        tmax = day0.get("tmax")
        pp = day0.get("pp")
        wind = day0.get("wind")

        lines: List[str] = []
        lines.append(f"Прогноз на {pretty_date}: {desc}.")
        if tmin is not None and tmax is not None:
            lines.append(f"Температура: от {float(tmin):.0f}°C до {float(tmax):.0f}°C.")
        if pp is not None:
            lines.append(f"Вероятность осадков: {int(pp)}%.")
        if wind is not None:
            lines.append(f"Ветер (макс): {float(wind):.0f} км/ч.")

        advice: List[str] = []
        if pp is not None and int(pp) >= 50:
            advice.append("Возьми зонт/дождевик.")
        if tmax is not None and float(tmax) <= 5:
            advice.append("Одевайся теплее (ветрозащита пригодится).")
        if tmax is not None and float(tmax) >= 28:
            advice.append("Вода и головной убор будут кстати.")

        return WeatherResult(
            place=label,
            summary=" ".join(lines),
            now_temp_c=float(now_temp) if now_temp is not None else None,
            wind_ms=(float(wind_now) / 3.6) if wind_now is not None else None,  # km/h -> m/s
            advice=advice,
            source="open-meteo",
        )
