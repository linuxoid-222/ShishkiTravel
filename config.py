
from __future__ import annotations

import os
from dataclasses import dataclass
try:
    from dotenv import load_dotenv  
except ImportError:

    def load_dotenv(*args: object, **kwargs: object) -> None:
        return None

load_dotenv()


@dataclass
class Settings:
    """Strongly-typed configuration settings for the bot."""

    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")


    gigachat_access_token: str = os.getenv("GIGACHAT_ACCESS_TOKEN", "")
    gigachat_scope: str = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    gigachat_base_url: str = os.getenv(
        "GIGACHAT_BASE_URL",
        "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
    )

    owm_key: str = os.getenv("OPENWEATHER_API_KEY", "")
    gmaps_key: str = os.getenv("GOOGLE_MAPS_API_KEY", "")


settings = Settings()
