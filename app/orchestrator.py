import asyncio
from typing import List, Optional
import urllib.parse

from .state import UserState
from .models import FinalBundle, RouteResult, TourismResult, TourismPlace
from .renderer import render_bundle
from .agents.router_agent import RouterAgent
from .agents.tourist_agent import TouristAgent
from .agents.legal_agent import LegalAgent
from .agents.weather_agent import WeatherAgent
from .agents.route_agent import RouteAgent
from .agents.summary_agent import SummaryAgent
from .route_builder import POIRouteBuilder, GeoPoint
from .enrichment.wiki_enricher import WikiEnricher

def google_maps_search_url(q: str) -> str:
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote_plus(q)

def _extract_place_names_from_plan(plan_lines: List[str]) -> List[str]:
    names: List[str] = []
    for line in plan_lines:
        if ":" in line:
            cand = line.split(":", 1)[1].strip()
        else:
            cand = line.strip()
        if cand:
            names.append(cand)
    return names

class Orchestrator:
    def __init__(self):
        self.router = RouterAgent()
        self.tourist = TouristAgent()
        self.legal = LegalAgent()
        self.weather = WeatherAgent()
        self.route = RouteAgent()
        self.summary_agent = SummaryAgent()
        self.poi_builder = POIRouteBuilder()
        self.wiki = WikiEnricher()

    async def _enrich_tourism(self, t: TourismResult, city: str | None, country: str | None, state: UserState) -> None:
        """
        Enrichment without LLM:
        - city photo via Wikipedia (if found)
        - for POIs: maps_url + (optional) wiki summary + image
        - store POIs into state.poi_items so we can show interactive buttons
        """
        cc = ", ".join([x for x in [city, country] if x]).strip()

        # reset UI lists
        state.poi_items = []
        state.food_items = []
        state.day_plan_text = None
        state.day_plan_route_url = None

        # City photo (one media card only)
        if cc:
            wp_city = await self.wiki.enrich(cc, lang="en", sentences=2)
            if wp_city and wp_city.thumbnail_url:
                t.city_image_url = wp_city.thumbnail_url
                state.media_queue.append({
                    "type": "photo",
                    "url": wp_city.thumbnail_url,
                    "caption": f"<b>{t.destination_title or cc}</b>\n{(wp_city.extract or '')[:240]}",
                    "buttons": [("📍 Открыть на карте", google_maps_search_url(cc))]
                })

        async def enrich_place(p: TourismPlace) -> None:
            q = (p.query or "").strip() or (f"{p.name}, {cc}" if cc else p.name)
            p.maps_url = google_maps_search_url(q)
            wp = await self.wiki.enrich(q, lang="en", sentences=6)
            if wp:
                if wp.extract and not p.summary:
                    p.summary = wp.extract[:500]
                if wp.thumbnail_url and not p.image_url:
                    p.image_url = wp.thumbnail_url

        # always add maps_url for food spots (no photos)
        for f in t.food_spots:
            q = (f.query or "").strip() or (f"{f.name}, {cc}" if cc else f.name)
            f.maps_url = google_maps_search_url(q)
            state.food_items.append({
                "name": f.name,
                "why": f.why,
                "maps_url": f.maps_url,
                "query": f.query,
            })

        # Enrich top places concurrently
        top = t.highlights[:10]
        await asyncio.gather(*[enrich_place(p) for p in top], return_exceptions=True)

        # Store POIs for interactive buttons (top 10)
        for p in t.highlights[:10]:
            state.poi_items.append({
                "name": p.name,
                "why": p.why,
                "time_needed": p.time_needed,
                "summary": p.summary,
                "image_url": p.image_url,
                "maps_url": p.maps_url,
                "query": p.query,
            })

    async def handle(
        self,
        user_text: str,
        state: UserState,
        forced_needs: Optional[List[str]] = None,
        forced_start: Optional[str] = None,
        forced_end: Optional[str] = None,
    ) -> str:
        state.last_route_url = None
        state.last_origin = None
        state.last_dest = None
        state.media_queue = []
        state.poi_items = []
        state.food_items = []

        memory_hint = f"summary={state.summary}; country={state.country}; city={state.city}; dates={state.dates}"
        decision = self.router.decide(user_text, memory_hint=memory_hint)
        if forced_needs:
            decision.needs = forced_needs

        # Weather is shown only when user presses the Weather button.
        allow_weather = bool(forced_needs) and ("weather" in (forced_needs or []))

        decision.country = decision.country or state.country
        decision.city = decision.city or state.city
        decision.dates = decision.dates or state.dates
        decision.start_location = forced_start or decision.start_location or state.start_location
        decision.end_location = forced_end or decision.end_location or state.end_location

        state.country = decision.country
        state.city = decision.city
        state.dates = decision.dates
        if decision.start_location:
            state.start_location = decision.start_location
        if decision.end_location:
            state.end_location = decision.end_location

        tourism_res = None
        legal_res = None
        weather_res = None
        route_res: RouteResult | None = None

        if "tourism" in decision.needs:
            try:
                tourism_res = self.tourist.run(
                    decision.country, decision.city, decision.dates,
                    decision.user_question or user_text,
                    summary=state.summary,
                )
                await self._enrich_tourism(tourism_res, decision.city, decision.country, state)
            except Exception:
                tourism_res = None

        if "legal" in decision.needs:
            try:
                legal_res = self.legal.run(decision.country, decision.city, decision.user_question or user_text)
            except Exception:
                legal_res = None

        tasks = []
        if allow_weather and "weather" in decision.needs:
            tasks.append(asyncio.create_task(self.weather.run(decision.country, decision.city)))

        want_route = "route" in decision.needs
        route_mode_poi = want_route and not decision.start_location and not decision.end_location

        if want_route and not route_mode_poi:
            a = decision.start_location or f"{decision.city or ''} {decision.country or ''}".strip()
            b = decision.end_location or "центр города"
            tasks.append(asyncio.create_task(self.route.run(a, b)))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            idx = 0
            if allow_weather and "weather" in decision.needs:
                if not isinstance(results[idx], Exception):
                    weather_res = results[idx]
                idx += 1
            if want_route and not route_mode_poi:
                if not isinstance(results[idx], Exception):
                    route_res = results[idx]

        # POI route from tourist plan/highlights (only if asked "route" and no A->B)
        if route_mode_poi and tourism_res and tourism_res.highlights:
            names = _extract_place_names_from_plan(tourism_res.plan_1_day) if tourism_res.plan_1_day else []
            if not names:
                names = [p.name for p in tourism_res.highlights[:7]]

            queries = []
            for p in tourism_res.highlights:
                if p.query:
                    queries.append((p.name, p.query))

            def q_for(name: str) -> str:
                cc2 = ", ".join([x for x in [decision.city, decision.country] if x])
                return f"{name}, {cc2}" if cc2 else name

            chosen = names[:8]
            geo_points: List[GeoPoint] = []
            for nm in chosen:
                q = None
                for (n0, q0) in queries:
                    if n0.lower() == nm.lower():
                        q = q0
                        break
                q = q or q_for(nm)
                try:
                    ll = await self.poi_builder.geocode(q)
                    if ll:
                        geo_points.append(GeoPoint(name=nm, lat=ll[0], lon=ll[1]))
                except Exception:
                    continue

            if len(geo_points) >= 2:
                ordered = self.poi_builder.order_points_nearest(geo_points)
                maps_url = self.poi_builder.google_maps_url(ordered, travelmode="walking")
                route_res = RouteResult(
                    maps_url=maps_url,
                    points=[p.name for p in ordered],
                    source="google_maps_url",
                )
                state.last_route_url = maps_url
                state.last_origin = (ordered[0].lat, ordered[0].lon)
                state.last_dest = (ordered[-1].lat, ordered[1].lon) if len(ordered)>1 else (ordered[-1].lat, ordered[-1].lon)
                # fix dest properly below
                state.last_dest = (ordered[-1].lat, ordered[-1].lon)
            else:
                route_res = RouteResult(notes=["Не удалось определить координаты для достаточного количества мест. Попробуй уточнить названия."], points=[])

        if route_res and route_res.maps_url:
            state.last_route_url = route_res.maps_url

        dest = ", ".join([x for x in [decision.city, decision.country] if x]) or "Путешествие"
        summary_line = None
        if ("weather" in (decision.needs or [])) and not allow_weather:
            summary_line = "🌦️ Прогноз погоды покажу по кнопке «Погода»."

        bundle = FinalBundle(
            destination_title=f"✈️ {dest}",
            tourism=tourism_res,
            legal=legal_res,
            weather=weather_res,
            route=route_res,
            summary_line=summary_line,
        )

        recent = "\n".join([f"{h['role']}: {h['text']}" for h in state.history[-6:]])
        try:
            new_summary = self.summary_agent.update(state.summary, recent)
            if new_summary:
                state.summary = new_summary
        except Exception:
            pass

        return render_bundle(bundle)
