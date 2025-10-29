"""Simple in-memory knowledge base with fuzzy country matching.

For our prototype, the knowledge base is stored in a JSON file under
`data/knowledge_base.json`.  The retrieval functions here read that file
into a Python dict on first access and support fuzzy lookup of country
names to accommodate slight misspellings or transliteration issues.
"""

from __future__ import annotations

import json
import os
from typing import Dict, Any, Optional, List

from rapidfuzz import process, fuzz

# Alias maps for country and city names. These are constructed on demand
# when the knowledge base is first loaded. They map lowercase alias strings
# to canonical country and city keys. For example, "france" and "франция"
# both map to the canonical key "Франция". City alias maps are scoped
# per-country.
COUNTRY_ALIAS_MAP: Optional[Dict[str, str]] = None
CITY_ALIAS_MAP: Optional[Dict[str, Dict[str, str]]] = None

# Determine the path to the packaged knowledge base. We construct this
# relative path dynamically so it works regardless of the working directory.
THIS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB_PATH = os.path.join(THIS_DIR, "data", "knowledge_base.json")


def _load_kb() -> Dict[str, Any]:
    """Load the knowledge base JSON into a dictionary."""
    if not os.path.exists(KB_PATH):
        return {}
    with open(KB_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# Lazily loaded global knowledge base
_KB: Optional[Dict[str, Any]] = None


def _ensure_kb_loaded() -> Dict[str, Any]:
    global _KB
    if _KB is None:
        _KB = _load_kb()
    return _KB

def _build_alias_maps() -> None:
    """Build global alias maps for countries and cities.

    COUNTRY_ALIAS_MAP maps lowercase alias strings to canonical country keys.
    CITY_ALIAS_MAP maps canonical country keys to a nested map of lowercase
    city alias strings to canonical city keys.

    This function is idempotent and will only build the maps once.
    """
    global COUNTRY_ALIAS_MAP, CITY_ALIAS_MAP
    if COUNTRY_ALIAS_MAP is not None and CITY_ALIAS_MAP is not None:
        return
    kb = _ensure_kb_loaded()
    alias_map: Dict[str, str] = {}
    city_map: Dict[str, Dict[str, str]] = {}
    for country_key, info in kb.items():
        # Register canonical country name
        alias_map[country_key.lower()] = country_key
        # Register country aliases if present
        for alias in info.get("aliases", []):
            alias_map[str(alias).lower()] = country_key
        # Build city alias map for this country
        city_aliases: Dict[str, str] = {}
        cities = info.get("cities", {})
        if isinstance(cities, dict):
            for city_key, city_info in cities.items():
                # Canonical city name
                city_aliases[city_key.lower()] = city_key
                for calias in city_info.get("aliases", []):
                    city_aliases[str(calias).lower()] = city_key
        city_map[country_key] = city_aliases
    COUNTRY_ALIAS_MAP = alias_map
    CITY_ALIAS_MAP = city_map


def find_country_key(query: str) -> Optional[str]:
    """Return the canonical country key matching the query string.

    This function normalizes the query to lowercase and first looks up
    the COUNTRY_ALIAS_MAP for an exact alias match.  If no exact match
    is found, it uses fuzzy matching (weighted ratio) across all alias
    keys to find the best match.  Returns None if no sufficiently
    close match is found.
    """
    kb = _ensure_kb_loaded()
    if not kb:
        return None
    _build_alias_maps()
    query_norm = str(query).strip().lower()
    # Direct alias match
    if COUNTRY_ALIAS_MAP and query_norm in COUNTRY_ALIAS_MAP:
        return COUNTRY_ALIAS_MAP[query_norm]
    # Fuzzy search across all alias keys
    alias_keys = list(COUNTRY_ALIAS_MAP.keys()) if COUNTRY_ALIAS_MAP else []
    if not alias_keys:
        return None
    match = process.extractOne(query_norm, alias_keys, scorer=fuzz.WRatio)
    if match and match[1] >= 70:
        return COUNTRY_ALIAS_MAP[match[0]]
    return None


def find_city_key(country: str, query: str) -> Optional[str]:
    """Return the canonical city key within a country matching the query string.

    The country may be a canonical key or any alias; it will be resolved
    to a canonical key.  The query is normalized to lowercase and first
    matched against city aliases for that country.  If no exact match
    is found, fuzzy matching is used across all city alias keys for
    the specified country.  Returns None if no sufficiently close match
    is found or if the country is unknown.
    """
    kb = _ensure_kb_loaded()
    if not kb:
        return None
    _build_alias_maps()
    # Resolve canonical country key
    country_key = country if country in kb else find_country_key(country)
    if not country_key:
        return None
    # Obtain city alias map for this country
    city_aliases = CITY_ALIAS_MAP.get(country_key, {}) if CITY_ALIAS_MAP else {}
    if not city_aliases:
        return None
    query_norm = str(query).strip().lower()
    # Direct alias match
    if query_norm in city_aliases:
        return city_aliases[query_norm]
    # Fuzzy search across city alias keys
    alias_keys = list(city_aliases.keys())
    match = process.extractOne(query_norm, alias_keys, scorer=fuzz.WRatio)
    if match and match[1] >= 70:
        return city_aliases[match[0]]
    return None


def find_city_global(query: str) -> Optional[tuple[str, str]]:
    """Search across all countries for a city alias and return (country_key, city_key).

    This function attempts to identify both the country and city from
    the query string by fuzzy matching across all city aliases in the
    knowledge base.  It returns a tuple of (canonical country key,
    canonical city key) if a sufficiently close match is found, or
    None otherwise.
    """
    kb = _ensure_kb_loaded()
    if not kb:
        return None
    _build_alias_maps()
    # Build a flat list of all city alias keys and a mapping back to (country_key, city_key)
    alias_keys: List[str] = []
    alias_to_pair: Dict[str, tuple[str, str]] = {}
    for country_key, city_aliases in (CITY_ALIAS_MAP or {}).items():
        for alias_key, city_key in city_aliases.items():
            alias_keys.append(alias_key)
            alias_to_pair[alias_key] = (country_key, city_key)
    query_norm = str(query).strip().lower()
    if not alias_keys:
        return None
    # Fuzzy search across all city alias keys
    match = process.extractOne(query_norm, alias_keys, scorer=fuzz.WRatio)
    if match and match[1] >= 70:
        alias_key = match[0]
        return alias_to_pair.get(alias_key, None)
    return None


def get_country_sections(country: str, sections: List[str] | None = None) -> Dict[str, str]:
    """Retrieve selected sections for a given country from the knowledge base.

    Parameters
    ----------
    country: str
        Canonical country name or key. If not found, fuzzy matching will
        attempt to find a close alternative.
    sections: list[str] or None
        Specific sections to retrieve (e.g. ["visa", "culture"]). If None,
        all available sections are returned.

    Returns
    -------
    dict
        Mapping of section names to their text. Missing sections are
        omitted from the result.
    """
    kb = _ensure_kb_loaded()
    key = country if country in kb else find_country_key(country)
    if not key:
        return {}
    info = kb[key]
    if sections is None:
        # Return a copy of all sections as strings, ignoring non-string fields
        return {k: v for k, v in info.items() if isinstance(v, str)}
    # Return only requested sections, omitting missing or non-string values
    result: Dict[str, str] = {}
    for sec in sections:
        val = info.get(sec)
        if isinstance(val, str) and val:
            result[sec] = val
    return result

def get_city_sections(country: str, city: str, sections: List[str] | None = None) -> Dict[str, str]:
    """Retrieve selected sections for a specific city within a country.

    The country and city may be aliases; they will be resolved to canonical
    keys.  If a section is missing at the city level, this function will
    fall back to the country-level section if available.

    Parameters
    ----------
    country: str
        Canonical country name or any alias.  If not found, fuzzy matching
        is used to find a close alternative.
    city: str
        City name or alias within the specified country.
    sections: list[str] or None
        Specific sections to retrieve (e.g. ["culture", "attractions"]).  If None,
        all available string sections for the city are returned.

    Returns
    -------
    dict
        Mapping of section names to their text.  Sections with no data at both
        the city and country levels are omitted from the result.
    """
    kb = _ensure_kb_loaded()
    # Resolve canonical country key
    country_key = country if country in kb else find_country_key(country)
    if not country_key:
        return {}
    info = kb.get(country_key, {})
    # Resolve canonical city key within this country
    city_key = find_city_key(country_key, city)
    if not city_key:
        return {}
    city_info = info.get("cities", {}).get(city_key, {})
    result: Dict[str, str] = {}
    if sections is None:
        # Return all string fields from city_info
        for k, v in city_info.items():
            if isinstance(v, str) and v:
                result[k] = v
        return result
    # For each requested section, prefer city-level value; fall back to country-level
    for sec in sections:
        val = city_info.get(sec)
        if isinstance(val, str) and val:
            result[sec] = val
            continue
        # Fallback to country-level if not found at city-level
        cval = info.get(sec)
        if isinstance(cval, str) and cval:
            result[sec] = cval
    return result
