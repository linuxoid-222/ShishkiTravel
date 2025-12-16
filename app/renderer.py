from __future__ import annotations
from typing import List
from html import escape

from .models import FinalBundle, TourismResult, LegalResult, WeatherResult, RouteResult

TELEGRAM_LIMIT = 3800

def _bullets(items: List[str]) -> str:
    if not items:
        return ""
    return "\n".join([f"• {escape(x)}" for x in items if x])

def _title(t: str) -> str:
    return f"<b>{escape(t)}</b>"

def render_bundle(bundle: FinalBundle) -> str:
    parts: List[str] = []
    parts.append(_title(bundle.destination_title))
    parts.append("────────")

    if bundle.tourism:
        parts.append("<b>🧭 Коротко о месте</b>")
        parts.append(render_overview(bundle.tourism))
        parts.append("")
        parts.append("<b>🏛️ Что посмотреть</b>")
        parts.append(render_highlights(bundle.tourism))
        parts.append("")
        parts.append("<b>🍜 Где поесть</b>")
        parts.append(render_food(bundle.tourism))
        parts.append("")
        # Plan is now interactive (button), keep only a hint here
        parts.append("<b>🗓️ План на день</b>")
        parts.append("• Нажми кнопку <b>«План на день»</b> под списком мест — пришлю подробный план и маршрут на карте.")
        parts.append("")
        extras = render_tourism_extras(bundle.tourism)
        if extras:
            parts.append(extras)
            parts.append("")

    if bundle.weather:
        parts.append("<b>🌦️ Погода</b>")
        parts.append(render_weather(bundle.weather))
        parts.append("")

    if bundle.route:
        parts.append("<b>🗺️ Маршрут</b>")
        parts.append(render_route(bundle.route))
        parts.append("")

    if bundle.legal:
        parts.append("<b>⚖️ Визы и законы</b>")
        parts.append(render_legal(bundle.legal))
        parts.append("")

    return "\n".join([p for p in parts if p]).strip()

def render_overview(t: TourismResult) -> str:
    out: List[str] = []
    if t.overview:
        out.append(escape(t.overview))
    if t.history:
        out.append("\n<b>Коротко об истории</b>")
        out.append(escape(t.history))
    return "\n".join(out) if out else "• (нет данных)"

def render_highlights(t: TourismResult) -> str:
    # Links removed from main message (will be shown on button click)
    out: List[str] = []
    for p in t.highlights[:10]:
        line = f"• <b>{escape(p.name)}</b> — {escape(p.why)}"
        if p.time_needed:
            line += f" <i>({escape(p.time_needed)})</i>"
        out.append(line)
    return "\n".join(out) if out else "• (нет данных)"

def render_food(t: TourismResult) -> str:
    out: List[str] = []
    for f in t.food_spots[:8]:
        line = f"• <b>{escape(f.name)}</b> — {escape(f.why)}"
        out.append(line)
    if not out and t.food:
        return _bullets(t.food)
    return "\n".join(out) if out else "• (нет данных)"

def render_tourism_extras(t: TourismResult) -> str:
    out: List[str] = []
    if t.areas:
        out.append("<b>📍 Районы</b>\n" + _bullets(t.areas))
    if t.etiquette:
        out.append("<b>🤝 Этикет</b>\n" + _bullets(t.etiquette))
    if t.tips:
        out.append("<b>💡 Советы</b>\n" + _bullets(t.tips))
    if t.questions_to_clarify:
        out.append("<b>❓ Что уточнить</b>\n" + _bullets(t.questions_to_clarify[:4]))
    return "\n\n".join([x for x in out if x])

def render_legal(l: LegalResult) -> str:
    out: List[str] = []
    if l.missing_info:
        out.append(f"⚠️ {escape(l.missing_info)}")

    if l.visa_required is True:
        out.append("Виза: <b>требуется</b>")
    elif l.visa_required is False:
        out.append("Виза: <b>не требуется</b>")
    else:
        out.append("Виза: <b>нет точных данных в базе</b>")

    if l.visa:
        out.append("\n<b>Визы</b>\n" + _bullets(l.visa))
    if l.entry_and_registration:
        out.append("\n<b>Въезд / регистрация</b>\n" + _bullets(l.entry_and_registration))
    if l.prohibitions_and_fines:
        out.append("\n<b>Запреты / штрафы</b>\n" + _bullets(l.prohibitions_and_fines))
    if l.recommendations:
        out.append("\n<b>Рекомендации</b>\n" + _bullets(l.recommendations))
    if l.sources:
        out.append("\n<b>Источники (локальная база)</b>\n" + _bullets([str(s) for s in l.sources]))

    return "\n".join([x for x in out if x])

def render_weather(w: WeatherResult) -> str:
    out = []
    if w.place:
        out.append(f"<b>{escape(w.place)}</b>")
    out.append(escape(w.summary or ""))
    details = []
    if w.now_temp_c is not None:
        details.append(f"Температура: {w.now_temp_c:.1f}°C")
    if w.feels_like_c is not None:
        details.append(f"Ощущается как: {w.feels_like_c:.1f}°C")
    if w.wind_ms is not None:
        details.append(f"Ветер: {w.wind_ms:.1f} м/с")
    if details:
        out.append(escape(" | ".join(details)))
    if w.advice:
        out.append(_bullets(w.advice))
    return "\n".join([x for x in out if x])

def render_route(r: RouteResult) -> str:
    out: List[str] = []
    if r.points:
        out.append("<b>Маршрут по точкам</b>")
        out.append(_bullets(r.points[:10]))
    else:
        out.append(f"<b>{escape(r.start)}</b> → <b>{escape(r.end)}</b>")

    if r.distance_km is not None or r.duration_min is not None:
        bits = []
        if r.distance_km is not None:
            bits.append(f"{r.distance_km:.1f} км")
        if r.duration_min is not None:
            bits.append(f"{r.duration_min:.0f} мин")
        out.append(escape(" · ".join(bits)))

    if r.steps:
        out.append("\n<b>Шаги</b>")
        for s in r.steps[:12]:
            out.append(f"• {escape(s.instruction)}")

    if r.maps_url:
        out.append(f"\n<b>Google Maps:</b> {escape(r.maps_url)}")

    if r.notes:
        out.append("\n<b>Заметки</b>")
        out.append(_bullets(r.notes))

    return "\n".join([x for x in out if x])

def split_telegram_html(text: str, limit: int = TELEGRAM_LIMIT) -> List[str]:
    text = text.strip()
    if len(text) <= limit:
        return [text]
    lines = text.split("\n")
    chunks: List[str] = []
    cur = ""
    for line in lines:
        candidate = (cur + "\n" + line) if cur else line
        if len(candidate) > limit and cur:
            chunks.append(cur)
            cur = line
        else:
            cur = candidate
    if cur:
        chunks.append(cur)
    return chunks
