

from __future__ import annotations

import requests
from typing import List, Dict, Optional

from ..config import settings


class GigaChatClient:


    def __init__(
        self,
        access_token: Optional[str] = None,
        base_url: Optional[str] = None,
        scope: Optional[str] = None,
    ) -> None:
        self.access_token = access_token or settings.gigachat_access_token
        self.base_url = base_url or settings.gigachat_base_url
        self.scope = scope or settings.gigachat_scope

    def chat(
        self, messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 1200
    ) -> str:

        if not self.access_token:
            raise RuntimeError(
                "GigaChat access token is missing; cannot call the API."
            )
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, object] = {
            "model": "GigaChat",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        try:
            response = requests.post(
                self.base_url,
                json=payload,
                headers=headers,
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
  
            return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        except Exception as exc:

            return f"Ошибка при вызове GigaChat: {exc}"


# Expose a default instance for convenience. Users can import gigachat
# directly from this module rather than instantiating GigaChatClient.
gigachat = GigaChatClient()
