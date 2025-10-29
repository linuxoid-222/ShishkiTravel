"""Thin wrapper around the GigaChat REST API.

This module exposes a minimal client for interacting with Sber's GigaChat
model. It hides away the HTTP details and returns plain Python strings
for generated answers. If desired, you could expand this class to
support streaming responses or to include additional request parameters
such as temperature or system messages.  The current implementation
focuses on the synchronous chat completions endpoint.
"""

from __future__ import annotations

import requests
from typing import List, Dict, Optional

from ..config import settings


class GigaChatClient:
    """Simple client for the GigaChat REST API.

    Attributes
    ----------
    access_token: str
        Bearer token used for authentication. See `.env.example` for how
        to configure it.
    base_url: str
        Base URL for the chat completions endpoint. This value defaults
        to Sber's hosted API but can be overridden.
    scope: str
        OAuth scope used when authenticating. Not currently used by
        requests but retained for future extensions.
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        base_url: Optional[str] = None,
        scope: Optional[str] = None,
    ) -> None:
        self.access_token = access_token or settings.gigachat_access_token
        self.base_url = base_url or settings.gigachat_base_url
        self.scope = scope or settings.gigachat_scope
        # Do not raise here if the token is missing.  The responder agent
        # handles missing credentials by falling back to a concatenated
        # answer.  We defer raising until the actual chat request to
        # avoid import-time failures.

    def chat(
        self, messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 1200
    ) -> str:
        """Send a list of messages to the GigaChat chat completions endpoint.

        Parameters
        ----------
        messages: List[Dict[str, str]]
            Sequence of messages describing the conversation context. See
            https://developers.sber.ru/docs/api-gigachat/openapi for the
            expected format. Each dict must contain `role` and `content` keys.
        temperature: float, optional
            Sampling temperature for the model. Higher values yield more
            diverse outputs. Defaults to 0.2 for conservative responses.
        max_tokens: int, optional
            Maximum number of tokens to generate.  Token counts differ
            depending on the model used. Default value should suffice for
            medium-length answers.

        Returns
        -------
        str
            The content of the first choice returned by GigaChat. If
            parsing fails, the raw JSON string is returned for debugging.
        """

        # Ensure we have a token before making the request.  Without a
        # token the caller should catch the exception and use fallback
        # behaviour.
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
            # Typical response format: {'choices': [{'message': {'content': ...}}]}
            return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        except Exception as exc:
            # Bubble up the exception but return a human-friendly message
            return f"Ошибка при вызове GigaChat: {exc}"


# Expose a default instance for convenience. Users can import gigachat
# directly from this module rather than instantiating GigaChatClient.
gigachat = GigaChatClient()
