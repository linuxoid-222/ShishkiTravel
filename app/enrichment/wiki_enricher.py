from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import httpx

@dataclass
class WikiPage:
    title: str
    extract: str = ""
    thumbnail_url: Optional[str] = None

class WikiEnricher:
    """
    Wikipedia helper (no keys):
    - search page title (MediaWiki API)
    - get intro extract + thumbnail via MediaWiki API (more Telegram-friendly than REST thumbnails)
    """
    def __init__(self):
        self._headers = {"User-Agent": "shishki-travel-bot/1.0"}

    async def search_title(self, query: str, lang: str = "en") -> Optional[str]:
        q = (query or "").strip()
        if not q:
            return None
        url = f"https://{lang}.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": q,
            "format": "json",
            "srlimit": 1,
        }
        async with httpx.AsyncClient(timeout=20, headers=self._headers) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            hits = (((r.json() or {}).get("query") or {}).get("search") or [])
            return hits[0].get("title") if hits else None

    async def page_intro(self, title: str, lang: str = "en", sentences: int = 5, thumb_px: int = 1200) -> WikiPage:
        """
        Uses prop=extracts + prop=pageimages to get plain text extract and a thumbnail URL.
        Usually returns jpg/png thumbnails (better for Telegram than REST which often returns webp).
        """
        url = f"https://{lang}.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "prop": "extracts|pageimages",
            "explaintext": 1,
            "exintro": 1,
            "exsentences": sentences,
            "piprop": "thumbnail",
            "pithumbsize": thumb_px,
            "titles": title,
            "format": "json",
            "formatversion": 2,
        }
        async with httpx.AsyncClient(timeout=20, headers=self._headers) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json() or {}
            pages = (data.get("query") or {}).get("pages") or []
            if not pages:
                return WikiPage(title=title)
            p0 = pages[0] or {}
            extract = (p0.get("extract") or "").strip() if isinstance(p0, dict) else ""
            thumb = ((p0.get("thumbnail") or {}).get("source")) if isinstance(p0, dict) else None
            return WikiPage(title=p0.get("title") or title, extract=extract, thumbnail_url=thumb)

    async def enrich(self, query: str, lang: str = "en", sentences: int = 5) -> Optional[WikiPage]:
        title = await self.search_title(query, lang=lang)
        if not title:
            return None
        try:
            return await self.page_intro(title, lang=lang, sentences=sentences)
        except Exception:
            return None
