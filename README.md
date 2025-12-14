# SHISHKI_TRAVEL  (Telegram Travel Bot )

Это рабочий MVP туристического Telegram-бота:

- Оркестратор (LLM-router) решает, какие блоки нужны: **tourism / legal / weather / route**
- `tourist_agent` даёт туристическую информацию (достопримечательности/культура/советы) в структурированном JSON
- `legal_agent` использует **RAG по локальной базе** (Chroma) и отвечает **только** на основе базы
- `weather_agent` берёт погоду из внешнего API (OpenWeather) и оформляет
- `route` умеет:
  - **маршрут А → Б** (OSRM + кнопка Google Maps)
  - **маршрут по достопримечательностям** (по списку мест от tourist_agent → геокодинг → Google Maps URL)
- Итоговый ответ собирается **кодом** (без LLM на финальном шаге) и выводится в Telegram HTML
- Кнопки-меню + простая память пользователя + summary-память

---


### 1) Установка

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2) Ключи
`.env` :

- `TELEGRAM_BOT_TOKEN=...`
- `GIGACHAT_CREDENTIALS=...`  
- `OPENWEATHER_API_KEY=...` 

### 3) Локальная база legal (RAG)
Папка с документами: `kb/legal/` 

Построить индекс:

```bat
py -m scripts.build_legal_index
```



### 4) Запуск бота
```bat
py bot.py
```

---

## Примеры запросов

### Туризм + погода + визы/законы
`Еду в Токио на 5 дней: что посмотреть, нужна ли виза и какая погода?`



### Маршрут по достопримечательностям (карта)
`Составь маршрут по достопримечательностям на 1 день в Париже`

---


