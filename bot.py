"""

    python -m travel_bot.bot


"""

from __future__ import annotations

import os
import sqlite3
import time
from typing import Optional

import telebot
from travel_bot.config import settings
from travel_bot.orchestrator import Orchestrator


def ensure_history_db(db_path: str) -> sqlite3.Connection:

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    cur = conn.cursor()
    cur.execute()
    conn.commit()
    return conn


def main() -> None:
    """Start the Telegram bot and begin polling for updates."""
    if not settings.telegram_token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN not set.  Please set it in your environment or .env file."
        )

    bot = telebot.TeleBot(settings.telegram_token, parse_mode="Markdown")
    orchestrator = Orchestrator()
    history_db = ensure_history_db(os.path.join("storage", "history.sqlite"))
    cur = history_db.cursor()

    @bot.message_handler(commands=["start", "help"])
    def greet(message: telebot.types.Message) -> None:
        bot.reply_to(
            message,
            (
                "Привет! Я ваш ассистент по путешествиям. "
                "Спросите меня о законах, культуре, достопримечательностях "
                "или маршрутах для любой страны. Примеры запросов:\n"
                "- Нужна ли виза в Японию?\n"
                "- Какие традиции во Франции?\n"
                "- Как добраться из Милана в Венецию?"
            ),
        )

    @bot.message_handler(content_types=["text"])
    def handle_text(message: telebot.types.Message) -> None:
        user_text = message.text.strip()

        try:
            answer = orchestrator.process(user_text)
        except Exception as exc:
            answer = f"Произошла ошибка: {exc}"
        bot.send_message(message.chat.id, answer or "Извините, я не могу ответить на ваш запрос.")

        cur.execute(
            "INSERT INTO history (chat_id, ts, user_text, bot_text) VALUES (?,?,?,?)",
            (str(message.chat.id), int(time.time()), user_text, answer or ""),
        )
        history_db.commit()

    # Start polling loop
    bot.infinity_polling(skip_pending=True, allowed_updates=["message"])


if __name__ == "__main__":
    main()
