# SHISHKI_TRAVEL  (Telegram Travel Bot )





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


