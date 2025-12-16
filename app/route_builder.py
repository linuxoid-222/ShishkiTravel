from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple
import math
import urllib.parse
import httpx

from .cache import TTLCache

@dataclass
class GeoPoint:
    name: str
    lat: float
    lon: float

def _haversine_km(a: Tuple[float,float], b: Tuple[float,float]) -> float:
    (lat1, lon1), (lat2, lon2) = a, b
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(x))

class POIRouteBuilder:
    def __init__(self, cache: Optional[TTLCache] = None):
        self.cache = cache or TTLCache(default_ttl_seconds=7*24*3600)

    async def geocode(self, query: str) -> Optional[Tuple[float,float]]:
        q = (query or "").strip()
        if not q:
            return None
        ck = f"geo:{q.lower()}"
        cached = self.cache.get(ck)
        if cached is not None:
            return cached

        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": q, "format": "json", "limit": 1}
        headers = {"User-Agent": "travel-bot/1.0"}
        async with httpx.AsyncClient(timeout=20, headers=headers) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
            if not data:
                return None
            lat, lon = float(data[0]["lat"]), float(data[0]["lon"])
            self.cache.set(ck, (lat, lon))
            return lat, lon

    def order_points_nearest(self, points: List[GeoPoint]) -> List[GeoPoint]:
        if len(points) <= 2:
            return points
        remaining = points[:]
        route = [remaining.pop(0)]
        while remaining:
            last = route[-1]
            best_i = 0
            best_d = 1e18
            for i,p in enumerate(remaining):
                d = _haversine_km((last.lat,last.lon),(p.lat,p.lon))
                if d < best_d:
                    best_d = d
                    best_i = i
            route.append(remaining.pop(best_i))
        return route

    def google_maps_url(self, ordered: List[GeoPoint], travelmode: str = "walking") -> Optional[str]:
        if len(ordered) < 2:
            return None
        origin = f"{ordered[0].lat},{ordered[0].lon}"
        dest = f"{ordered[-1].lat},{ordered[-1].lon}"
        waypoints = "|".join([f"{p.lat},{p.lon}" for p in ordered[1:-1]])
        base = "https://www.google.com/maps/dir/?api=1"
        params = {"origin": origin, "destination": dest, "travelmode": travelmode}
        if waypoints:
            params["waypoints"] = waypoints
        return base + "&" + urllib.parse.urlencode(params, safe="|,")
