"""Configuration loader for the travel bot.

This module reads environment variables via python-dotenv and exposes them
as a simple dataclass. Storing configuration in a dataclass makes it easy
to pass around settings without repeatedly importing os.getenv throughout
the codebase.

The `.env.example` file in the project root illustrates the expected
environment variables. Copy it to `.env` and populate with your secrets
before running the bot.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
try:
    from dotenv import load_dotenv  # type: ignore
except ImportError:
    # Define a no-op load_dotenv function if python-dotenv is not installed.
    def load_dotenv(*args: object, **kwargs: object) -> None:
        return None

# Load environment variables from a .env file if present.  Using
# load_dotenv here allows developers to keep secrets out of version control
# while still running the bot locally. In production you may supply
# environment variables via your host's mechanism instead of a .env file.
load_dotenv()


@dataclass
class Settings:
    """Strongly-typed configuration settings for the bot."""

    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

    # GigaChat API settings
    gigachat_access_token: str = os.getenv("GIGACHAT_ACCESS_TOKEN", "")
    gigachat_scope: str = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
    gigachat_base_url: str = os.getenv(
        "GIGACHAT_BASE_URL",
        "https://gigachat.devices.sberbank.ru/api/v1/chat/completions",
    )

    # External APIs (optional)
    owm_key: str = os.getenv("OPENWEATHER_API_KEY", "")
    gmaps_key: str = os.getenv("GOOGLE_MAPS_API_KEY", "")


# Instantiate a module-level settings object for convenience. Consumers can
# import `settings` from this module rather than instantiating Settings
# directly. This instantiation happens at import time, so environment
# variables should be available.
settings = Settings()
