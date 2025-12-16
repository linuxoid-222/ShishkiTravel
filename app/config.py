from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    gigachat_credentials: str = os.getenv("GIGACHAT_CREDENTIALS", "")
    gigachat_verify_ssl_certs: bool = os.getenv("GIGACHAT_VERIFY_SSL_CERTS", "false").lower() == "true"

    openweather_api_key: str = os.getenv("OPENWEATHER_API_KEY", "")
    open_meteo_base_url: str = os.getenv("OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1")
    open_meteo_geocoding_url: str = os.getenv("OPEN_METEO_GEOCODING_URL", "https://geocoding-api.open-meteo.com/v1")
    osrm_base_url: str = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org")

    legal_chroma_dir: str = os.getenv("LEGAL_CHROMA_DIR", "./.chroma_legal")
    legal_kb_dir: str = os.getenv("LEGAL_KB_DIR", "./kb/legal")

settings = Settings()
