
from __future__ import annotations

import json
import os
from typing import Dict, Any, Optional, List

from rapidfuzz import process, fuzz

COUNTRY_ALIAS_MAP: Optional[Dict[str, str]] = None
CITY_ALIAS_MAP: Optional[Dict[str, Dict[str, str]]] = None


THIS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_PATH = os.path.join(THIS_DIR, "data", "knowledge_base.json")


def _load_kb() -> Dict[str, Any]:
    """Load the knowledge base JSON into a dictionary."""
    if not os.path.exists(KB_PATH):
        return {}
    with open(KB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


_KB: Optional[Dict[str, Any]] = None


def _ensure_kb_loaded() -> Dict[str, Any]:
    global _KB
    if _KB is None:
        _KB = _load_kb()
    return _KB

def _build_alias_maps() -> None:

    global COUNTRY_ALIAS_MAP, CITY_ALIAS_MAP
    if COUNTRY_ALIAS_MAP is not None and CITY_ALIAS_MAP is not None:
        return
    kb = _ensure_kb_loaded()
    alias_map: Dict[str, str] = {}
    city_map: Dict[str, Dict[str, str]] = {}
    for country_key, info in kb.items():

        alias_map[country_key.lower()] = country_key

        for alias in info.get("aliases", []):
            alias_map[str(alias).lower()] = country_key
                # Canonical city name
        city_aliases: Dict[str, str] = {}
        cities = info.get("cities", {})
        if isinstance(cities, dict):
            for city_key, city_info in cities.items():

                city_aliases[city_key.lower()] = city_key
                for calias in city_info.get("aliases", []):
                    city_aliases[str(calias).lower()] = city_key
        city_map[country_key] = city_aliases
    COUNTRY_ALIAS_MAP = alias_map
    CITY_ALIAS_MAP = city_map


def find_country_key(query: str) -> Optional[str]:

    kb = _ensure_kb_loaded()
    if not kb:
        return None
    _build_alias_maps()
    query_norm = str(query).strip().lower()

    if COUNTRY_ALIAS_MAP and query_norm in COUNTRY_ALIAS_MAP:
        return COUNTRY_ALIAS_MAP[query_norm]

    alias_keys = list(COUNTRY_ALIAS_MAP.keys()) if COUNTRY_ALIAS_MAP else []
    if not alias_keys:
        return None
    match = process.extractOne(query_norm, alias_keys, scorer=fuzz.WRatio)
    if match and match[1] >= 70:
        return COUNTRY_ALIAS_MAP[match[0]]
    return None


def find_city_key(country: str, query: str) -> Optional[str]:

    kb = _ensure_kb_loaded()
    if not kb:
        return None
    _build_alias_maps()

    country_key = country if country in kb else find_country_key(country)
    if not country_key:
        return None

    city_aliases = CITY_ALIAS_MAP.get(country_key, {}) if CITY_ALIAS_MAP else {}
    if not city_aliases:
        return None
    query_norm = str(query).strip().lower()

    if query_norm in city_aliases:
        return city_aliases[query_norm]

    alias_keys = list(city_aliases.keys())
    match = process.extractOne(query_norm, alias_keys, scorer=fuzz.WRatio)
    if match and match[1] >= 70:
        return city_aliases[match[0]]
    return None


def find_city_global(query: str) -> Optional[tuple[str, str]]:

    kb = _ensure_kb_loaded()
    if not kb:
        return None
    _build_alias_maps()

    alias_keys: List[str] = []
    alias_to_pair: Dict[str, tuple[str, str]] = {}
    for country_key, city_aliases in (CITY_ALIAS_MAP or {}).items():
        for alias_key, city_key in city_aliases.items():
            alias_keys.append(alias_key)
            alias_to_pair[alias_key] = (country_key, city_key)
    query_norm = str(query).strip().lower()
    if not alias_keys:
        return None

    match = process.extractOne(query_norm, alias_keys, scorer=fuzz.WRatio)
    if match and match[1] >= 70:
        alias_key = match[0]
        return alias_to_pair.get(alias_key, None)
    return None


def get_country_sections(country: str, sections: List[str] | None = None) -> Dict[str, str]:

    kb = _ensure_kb_loaded()
    key = country if country in kb else find_country_key(country)
    if not key:
        return {}
    info = kb[key]
    if sections is None:

        return {k: v for k, v in info.items() if isinstance(v, str)}

    result: Dict[str, str] = {}
    for sec in sections:
        val = info.get(sec)
        if isinstance(val, str) and val:
            result[sec] = val
    return result

def get_city_sections(country: str, city: str, sections: List[str] | None = None) -> Dict[str, str]:

    kb = _ensure_kb_loaded()

    country_key = country if country in kb else find_country_key(country)
    if not country_key:
        return {}
    info = kb.get(country_key, {})

    city_key = find_city_key(country_key, city)
    if not city_key:
        return {}
    city_info = info.get("cities", {}).get(city_key, {})
    result: Dict[str, str] = {}
    if sections is None:

        for k, v in city_info.items():
            if isinstance(v, str) and v:
                result[k] = v
        return result

    for sec in sections:
        val = city_info.get(sec)
        if isinstance(val, str) and val:
            result[sec] = val
            continue

        cval = info.get(sec)
        if isinstance(cval, str) and cval:
            result[sec] = cval
    return result
