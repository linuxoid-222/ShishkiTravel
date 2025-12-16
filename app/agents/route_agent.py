from __future__ import annotations
import httpx

from ..models import RouteResult, RouteStep
from ..config import settings
from ..cache import TTLCache

class RouteAgent:
    def __init__(self, cache: TTLCache | None = None):
        self.cache = cache or TTLCache(default_ttl_seconds=6 * 3600)

    async def geocode_nominatim(self, q: str) -> tuple[float, float] | None:
        qn = (q or "").strip()
        if not qn:
            return None
        cache_key = f"geo:{qn.lower()}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": qn, "format": "json", "limit": 1}
        headers = {"User-Agent": "travel-bot/1.0"}
        async with httpx.AsyncClient(timeout=20, headers=headers) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
            if not data:
                return None
            lat, lon = float(data[0]["lat"]), float(data[0]["lon"])
            self.cache.set(cache_key, (lat, lon), ttl_seconds=7 * 24 * 3600)
            return lat, lon

    async def fetch_osrm_route(self, a_ll: tuple[float,float], b_ll: tuple[float,float]) -> dict:
        (alat, alon), (blat, blon) = a_ll, b_ll
        url = f"{settings.osrm_base_url}/route/v1/driving/{alon},{alat};{blon},{blat}"
        params = {"overview": "false", "steps": "true"}

        cache_key = f"osrm:{alon},{alat}->{blon},{blat}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        async with httpx.AsyncClient(timeout=25) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
            self.cache.set(cache_key, data, ttl_seconds=6 * 3600)
            return data

    @staticmethod
    def google_maps_url(a_ll: tuple[float,float], b_ll: tuple[float,float], travelmode: str = "driving") -> str:
        (alat, alon), (blat, blon) = a_ll, b_ll
        return (
            "https://www.google.com/maps/dir/?api=1"
            f"&origin={alat},{alon}"
            f"&destination={blat},{blon}"
            f"&travelmode={travelmode}"
        )

    @staticmethod
    def _step_instruction(st: dict) -> str:
        man = st.get("maneuver", {}) or {}
        name = (st.get("name") or "").strip()
        mtype = (man.get("type") or "").strip()
        mod = (man.get("modifier") or "").strip()
        parts = [p for p in [mtype, mod] if p]
        base = " ".join(parts).strip()
        if name:
            return f"{base} на {name}".strip() if base else name
        return base or "Двигайтесь по маршруту"

    async def run(self, start_location: str, end_location: str) -> RouteResult:
        a = (start_location or "").strip()
        b = (end_location or "").strip()

        a_ll = await self.geocode_nominatim(a)
        b_ll = await self.geocode_nominatim(b)
        if not a_ll or not b_ll:
            return RouteResult(
                start=a or "не указано",
                end=b or "не указано",
                steps=[],
                notes=["Не удалось геокодировать одну из точек. Попробуй формат: «Город, Страна -> Город, Страна»."],
            )

        try:
            data = await self.fetch_osrm_route(a_ll, b_ll)
            if data.get("code") != "Ok" or not data.get("routes"):
                return RouteResult(start=a, end=b, steps=[], notes=[f"OSRM вернул ошибку: {data.get('code', 'unknown')}"])

            route0 = data["routes"][0]
            dist_km = float(route0.get("distance", 0)) / 1000.0
            dur_min = float(route0.get("duration", 0)) / 60.0

            steps_out: list[RouteStep] = []
            for leg in route0.get("legs", []):
                for st in leg.get("steps", []):
                    steps_out.append(RouteStep(
                        instruction=self._step_instruction(st),
                        distance_m=int(st.get("distance", 0)) if st.get("distance") is not None else None,
                        duration_s=int(st.get("duration", 0)) if st.get("duration") is not None else None,
                    ))

            return RouteResult(
                start=a,
                end=b,
                distance_km=dist_km,
                duration_min=dur_min,
                steps=steps_out[:20],
                notes=[],
                maps_url=self.google_maps_url(a_ll, b_ll, travelmode="driving"),
                source="osrm",
            )
        except Exception as e:
            return RouteResult(start=a, end=b, steps=[], notes=[f"Не удалось построить маршрут: {e}"])
