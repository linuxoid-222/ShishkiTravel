
from __future__ import annotations

import os
import shutil
from typing import List, Dict, Any, Optional

from langchain_community.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.docstore.document import Document


CHROMA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chroma_rag")
_VECTORDB: Chroma | None = None


from travel_bot.services.knowledge_base import _ensure_kb_loaded  


def embed_knowledge_base() -> None:
    """Пересоздать Chroma-индекс из локальной БД: страны + города, с метаданными."""
    kb = _ensure_kb_loaded()
    if os.path.exists(CHROMA_DIR):
        shutil.rmtree(CHROMA_DIR)

    docs: List[Document] = []

    for country, info in kb.items():
        if not isinstance(info, dict):
            continue

        # Страновые строковые поля (culture, attractions и т.п.)
        for section, value in info.items():
            if isinstance(value, str):
                docs.append(Document(
                    page_content=value,
                    metadata={"country": country, "city": None, "section": section},
                ))


        cities = info.get("cities") or {}
        if isinstance(cities, dict):
            for city, cdata in cities.items():
                if not isinstance(cdata, dict):
                    continue
                for section, value in cdata.items():
                    if isinstance(value, str):
                        docs.append(Document(
                            page_content=value,
                            metadata={"country": country, "city": city, "section": section},
                        ))

    embedder = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectordb = Chroma.from_documents(
        documents=docs,
        embedding=embedder,
        persist_directory=CHROMA_DIR,
    )
    vectordb.persist()


def _get_vectordb() -> Chroma:
    """Ленивая загрузка/инициализация индекса."""
    global _VECTORDB
    if _VECTORDB is not None:
        return _VECTORDB

    embedder = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    _VECTORDB = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embedder,
    )


    try:
        count = _VECTORDB._collection.count()
    except Exception:
        count = 0

    if not count:
        embed_knowledge_base()
        _VECTORDB = Chroma(
            persist_directory=CHROMA_DIR,
            embedding_function=embedder,
        )

    return _VECTORDB


def retrieve_advanced(
    query: str,
    *,
    k: int = 6,
    fetch_k: int = 20,
    mmr: bool = True,
    metadata_filter: Optional[Dict[str, Any]] = None,
    section_filter: Optional[List[str]] = None,
) -> List[Document]:
    """
    section_filter: если указан, ограничивает выдачу конкретными разделами (напр. ["culture", "attractions"]).
    """
    db = _get_vectordb()

    if mmr:
        docs = db.max_marginal_relevance_search(
            query=query, k=k, fetch_k=fetch_k, filter=metadata_filter
        )
    else:
        docs = db.similarity_search(query=query, k=k, filter=metadata_filter)

    cleaned = [d for d in docs if (d.page_content or "").strip()]

    if section_filter:
        allowed = set(section_filter)
        cleaned = [d for d in cleaned if (d.metadata or {}).get("section") in allowed]

    return cleaned
