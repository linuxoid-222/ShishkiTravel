import asyncio
import httpx
import html
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from app.config import settings
from app.orchestrator import Orchestrator
from app.state import StateStore
from app.renderer import split_telegram_html
from app.route_builder import POIRouteBuilder, GeoPoint


async def _download_image_bytes(url: str) -> bytes | None:
    """Download image bytes for Telegram upload. Returns None on failure."""
    u = (url or "").strip()
    if not u:
        return None
    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
            r = await client.get(u)
            r.raise_for_status()
            return r.content
    except Exception:
        return None


def main_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🏙️ Туризм", callback_data="need:tourism")
    kb.button(text="⚖️ Визы / законы", callback_data="need:legal")
    kb.button(text="🌦️ Погода", callback_data="need:weather")
    kb.button(text="🗺️ Маршрут", callback_data="need:route")
    kb.button(text="🧹 Сброс", callback_data="need:reset")
    kb.adjust(2, 2, 1)
    return kb.as_markup()

def poi_list_kb(poi_items):
    kb = InlineKeyboardBuilder()
    for i, it in enumerate(poi_items[:10]):
        title = (it.get("name") or f"Место {i+1}").strip()
        kb.button(text=title[:32], callback_data=f"poi:{i}")
    # extra actions
    kb.button(text="📅 План на день", callback_data="plan:day")
    kb.adjust(2, 2, 1)
    return kb.as_markup()

def poi_detail_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Назад к списку", callback_data="poi:list")
    kb.button(text="📅 План на день", callback_data="plan:day")
    kb.adjust(1, 1)
    return kb.as_markup()

def food_kb(food_items):
    kb = InlineKeyboardBuilder()
    for it in food_items[:8]:
        title = (it.get("name") or "Еда").strip()
        url = it.get("maps_url")
        if url:
            kb.add(InlineKeyboardButton(text=title[:32], url=url))
    kb.adjust(2)
    return kb.as_markup() if kb.buttons else None

def _escape(s: str) -> str:
    return html.escape(s or "")

def _make_day_plan_text(city: str | None, country: str | None, ordered_pois: list[str], food_items: list[dict]) -> str:
    # pick 4-6 POIs
    pois = ordered_pois[:6]
    lunch = (food_items[0]["name"] if len(food_items) >= 1 else "местное кафе/рынок")
    dinner = (food_items[1]["name"] if len(food_items) >= 2 else "уютный ресторан рядом с центром")

    dest = ", ".join([x for x in [city, country] if x]) or "город"

    blocks = []
    blocks.append(f"📅 <b>План на 1 день</b> — {_escape(dest)}")
    blocks.append("")

    # Build timeline (simple but consistent)
    t = [
        ("09:00–10:30", pois[0] if len(pois) > 0 else "Прогулка по центру"),
        ("10:45–12:00", pois[1] if len(pois) > 1 else "Кофе + видовая точка"),
        ("12:15–13:15", f"Обед: {lunch}"),
        ("13:30–15:00", pois[2] if len(pois) > 2 else "Музей/галерея"),
        ("15:15–16:30", pois[3] if len(pois) > 3 else "Парк/набережная"),
        ("16:45–18:00", pois[4] if len(pois) > 4 else "Шоппинг-улица/район"),
        ("19:00–20:30", f"Ужин: {dinner}"),
    ]

    blocks.append("<b>⏰ Расписание</b>")
    for time_slot, item in t:
        blocks.append(f"• <b>{_escape(time_slot)}</b> — {_escape(item)}")

    if food_items:
        blocks.append("")
        blocks.append("<b>🍜 Где поесть (из подборки)</b>")
        for it in food_items[:4]:
            name = it.get("name") or ""
            why = it.get("why") or ""
            blocks.append(f"• <b>{_escape(name)}</b> — {_escape(why)}")

    blocks.append("")
    blocks.append("Совет: если хочешь — напиши «сделай план спокойнее» или «больше музеев/еды/видов», и я перестрою подборку.")
    return "\n".join(blocks).strip()

async def main():
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is empty")
    if not settings.gigachat_credentials:
        raise RuntimeError("GIGACHAT_CREDENTIALS is empty")

    bot = Bot(token=settings.telegram_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    orch = Orchestrator()
    store = StateStore()
    poi_route_builder = POIRouteBuilder()

    @dp.message(F.text == "/start")
    async def start(m: Message):
        await m.answer(
            "Привет! ✈️\n"
            "Я помогу с: достопримечательностями, культурой, визами/законами (из локальной базы), погодой и маршрутами.\n\n"
            "Можно нажать кнопку снизу или просто написать запрос.\n"
            "Пример: <i>«Еду в Токио на 5 дней: что посмотреть, нужна ли виза и какая погода?»</i>\n"
            "Интерактив: после ответа появятся кнопки мест — нажми и получишь фото+описание+карту.\n",
            reply_markup=main_menu_kb()
        )

        @dp.callback_query(F.data.startswith("need:"))
        async def menu_click(cb: CallbackQuery):
            user_id = cb.from_user.id
            state = store.get(user_id)
            action = cb.data.split(":", 1)[1]

            if action == "reset":
                store.reset(user_id)
                await cb.message.answer("Сбросил контекст ✅", reply_markup=main_menu_kb())
                await cb.answer()
                return

            has_destination = bool((state.city and state.city.strip()) or (state.country and state.country.strip()))

            # If destination is already known, run immediately (no extra questions)
            if action in ("tourism", "legal", "weather") and has_destination:
                state.pending_needs = []
                state.pending_input = None

                await cb.message.answer("Думаю… 🧠")
                try:
                    html_answer = await orch.handle(
                        user_text=f"Покажи {action}",
                        state=state,
                        forced_needs=[action],
                    )
                except Exception as e:
                    print("ERROR:", e)
                    await cb.message.answer("Что-то пошло не так 😕 Попробуй повторить.", reply_markup=main_menu_kb())
                    await cb.answer()
                    return

                for chunk in split_telegram_html(html_answer):
                    await cb.message.answer(chunk, reply_markup=main_menu_kb())

                if action == "tourism":
                    if state.poi_items:
                        await cb.message.answer(
                            "🏛️ <b>Достопримечательности</b>\n"
                            "Нажми на кнопку — пришлю фото + подробности + карту:",
                            reply_markup=poi_list_kb(state.poi_items),
                        )
                    mk = food_kb(state.food_items)
                    if mk:
                        await cb.message.answer(
                            "🍜 <b>Где поесть</b>\n"
                            "Кнопки ведут в Google Maps:",
                            reply_markup=mk,
                        )

                await cb.answer()
                return

            # Otherwise, ask for needed input
            state.pending_needs = [action]

            if action == "route":
                state.pending_input = "route_points"
                await cb.message.answer(
                    "Напиши маршрут в формате: <b>Откуда -> Куда</b>\n"
                    "Например: <i>Амстердам -> Париж</i>\n\n"
                    "Или напиши: <i>«Составь маршрут по достопримечательностям на 1 день в Париже»</i> — тогда я сделаю маршрут по местам.",
                )
            else:
                state.pending_input = "destination"
                await cb.message.answer(
                    "Ок. Напиши город/страну и детали (даты/интересы), например: <i>Рим на 4 дня в январе</i>"
                )

            await cb.answer()

    @dp.callback_query(F.data.startswith("poi:"))
    async def poi_click(cb: CallbackQuery):
        user_id = cb.from_user.id
        state = store.get(user_id)
        suffix = cb.data.split(":", 1)[1].strip()

        if suffix == "list":
            if not state.poi_items:
                await cb.answer("Список мест пуст. Спроси заново 🙂", show_alert=False)
                return
            await cb.message.answer("🏛️ <b>Достопримечательности</b>\nНажми на кнопку — пришлю фото + подробности + карту:", reply_markup=poi_list_kb(state.poi_items))
            await cb.answer()
            return

        try:
            idx = int(suffix)
        except Exception:
            await cb.answer("Не понял выбор 😅", show_alert=False)
            return

        if idx < 0 or idx >= len(state.poi_items):
            await cb.answer("Эта кнопка уже устарела. Спроси заново 🙂", show_alert=False)
            return

        it = state.poi_items[idx]
        name = (it.get("name") or "Место").strip()
        why = (it.get("why") or "").strip()
        summary = (it.get("summary") or "").strip()
        image_url = it.get("image_url")
        maps_url = it.get("maps_url")

        # Build rich text
        text_bits = [f"🏛️ <b>{_escape(name)}</b>"]
        if summary:
            text_bits.append(_escape(summary))
        if why:
            text_bits.append(f"\n<b>Почему стоит:</b>\n{_escape(why)}")

        full_text = "\n".join([x for x in text_bits if x]).strip()

        kb = InlineKeyboardBuilder()
        if maps_url:
            kb.add(InlineKeyboardButton(text="📍 Google Maps", url=maps_url))
        kb.add(InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="poi:list"))
        kb.add(InlineKeyboardButton(text="📅 План на день", callback_data="plan:day"))
        kb.adjust(1)
        markup = kb.as_markup()

        # For photo captions keep it short
        caption = full_text[:900]

        try:
            if image_url:
                # 1) Try direct URL (fast path)
                try:
                    await cb.message.answer_photo(photo=image_url, caption=caption, reply_markup=markup)
                except Exception:
                    # 2) Fallback: download and upload bytes (more reliable for Telegram)
                    data = await _download_image_bytes(str(image_url))
                    if data:
                        await cb.message.answer_photo(
                            photo=BufferedInputFile(data, filename="photo.jpg"),
                            caption=caption,
                            reply_markup=markup,
                        )
                    else:
                        await cb.message.answer(full_text, reply_markup=markup)

                if len(full_text) > 900:
                    await cb.message.answer(full_text, reply_markup=markup)
            else:
                await cb.message.answer(full_text, reply_markup=markup)
        except Exception as e:
            print("POI SEND ERROR:", e)
            await cb.message.answer(full_text, reply_markup=markup)

        await cb.answer()

    @dp.callback_query(F.data == "plan:day")
    async def plan_day(cb: CallbackQuery):
        user_id = cb.from_user.id
        state = store.get(user_id)

        if not state.poi_items:
            await cb.answer("Сначала попроси места в городе 🙂", show_alert=False)
            return

        # If cached, reuse
        if state.day_plan_text and state.day_plan_route_url:
            plan_text = state.day_plan_text
            route_url = state.day_plan_route_url
        else:
            # Build route from POIs (top 5-6)
            city = state.city
            country = state.country
            cc = ", ".join([x for x in [city, country] if x]).strip()

            # geocode points (limit to 6)
            async def geo_for(it: dict):
                q = (it.get("query") or "").strip()
                name = (it.get("name") or "").strip()
                if not q:
                    q = f"{name}, {cc}" if cc else name
                ll = await poi_route_builder.geocode(q)
                return (name, q, ll)

            items = state.poi_items[:6]
            results = await asyncio.gather(*[geo_for(it) for it in items], return_exceptions=True)

            geos = []
            for r in results:
                if isinstance(r, Exception):
                    continue
                name, q, ll = r
                if ll:
                    geos.append(GeoPoint(name=name, lat=ll[0], lon=ll[1]))

            if len(geos) >= 2:
                ordered = poi_route_builder.order_points_nearest(geos)
                route_url = poi_route_builder.google_maps_url(ordered, travelmode="walking")
                ordered_names = [p.name for p in ordered]
            else:
                route_url = None
                ordered_names = [it.get("name") or "" for it in state.poi_items[:6]]

            plan_text = _make_day_plan_text(state.city, state.country, ordered_names, state.food_items)

            state.day_plan_text = plan_text
            state.day_plan_route_url = route_url

        kb = InlineKeyboardBuilder()
        if route_url:
            kb.add(InlineKeyboardButton(text="🗺️ Маршрут в Google Maps", url=route_url))
        kb.add(InlineKeyboardButton(text="⬅️ Назад к списку мест", callback_data="poi:list"))
        kb.adjust(1)
        await cb.message.answer(plan_text, reply_markup=kb.as_markup())
        await cb.answer()

    @dp.message(F.text)
    async def handle(m: Message):
        user_id = m.from_user.id
        state = store.get(user_id)
        text = (m.text or "").strip()

        state.history.append({"role": "user", "text": text})
        state.history = state.history[-8:]

        forced_needs = state.pending_needs[:] if state.pending_needs else None
        forced_start = None
        forced_end = None

        if state.pending_input == "route_points":
            if "->" in text:
                a, b = [x.strip() for x in text.split("->", 1)]
                forced_start, forced_end = a, b
                state.start_location, state.end_location = a, b
            state.pending_input = None
            state.pending_needs = []
        else:
            if state.pending_input == "destination":
                state.pending_input = None
                state.pending_needs = []

        await m.answer("Думаю… 🧠")

        try:
            html_answer = await orch.handle(
                user_text=text,
                state=state,
                forced_needs=forced_needs,
                forced_start=forced_start,
                forced_end=forced_end,
            )
        except Exception as e:
            print("ERROR:", e)
            await m.answer("Что-то пошло не так 😕 Попробуй повторить или переформулировать запрос.", reply_markup=main_menu_kb())
            return

        state.history.append({"role": "assistant", "text": html_answer})
        state.history = state.history[-8:]

        for chunk in split_telegram_html(html_answer):
            await m.answer(chunk, reply_markup=main_menu_kb())

        # Send city photo etc.
        if state.media_queue:
            for item in state.media_queue[:6]:
                if item.get("type") == "photo" and item.get("url"):
                    kb = None
                    buttons = item.get("buttons") or []
                    if buttons:
                        b = InlineKeyboardBuilder()
                        for (t, u) in buttons:
                            b.add(InlineKeyboardButton(text=t, url=u))
                        b.adjust(1)
                        kb = b.as_markup()
                    try:
                        await m.answer_photo(photo=item["url"], caption=item.get("caption") or "", reply_markup=kb)
                    except Exception as e:
                        print("MEDIA SEND ERROR:", e)
            state.media_queue = []

        # Interactive POI buttons (with Plan button)
        if state.poi_items:
            await m.answer(
                "🏛️ <b>Достопримечательности</b>\n"
                "Нажми на кнопку — пришлю фото + подробности + карту:",
                reply_markup=poi_list_kb(state.poi_items),
            )

        # Food: direct links (optional)
        if state.food_items:
            mk = food_kb(state.food_items)
            if mk:
                await m.answer("🍜 <b>Где поесть</b>\nКнопки ведут в Google Maps:", reply_markup=mk)

        # If we have a route URL (A->B or POI), offer a map button
        if state.last_route_url:
            kb = InlineKeyboardBuilder()
            kb.add(InlineKeyboardButton(text="🗺️ Открыть в Google Maps", url=state.last_route_url))
            kb.adjust(1)

            if state.last_origin:
                lat, lon = state.last_origin
                await m.answer_location(latitude=lat, longitude=lon)
            if state.last_dest:
                lat, lon = state.last_dest
                await m.answer_location(latitude=lat, longitude=lon)

            await m.answer("Маршрут на карте:", reply_markup=kb.as_markup())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
