from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import os
import re

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

from ..llm_factory import make_embeddings
from ..config import settings


def _norm_country(s: str) -> str:
    """Normalize country name for exact metadata matching."""
    s = (s or "").strip().lower()
    s = s.replace("ё", "е")
    # keep letters/digits, collapse others to space
    s = re.sub(r"[^0-9a-zа-я]+", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _extract_country_from_text(text: str) -> Optional[str]:
    """Try to extract country from YAML-like header."""
    # Support either simple header lines or YAML frontmatter
    # Examples:
    # country_ru: Япония
    # country: Japan
    # country_key: JP  (we still prefer country_ru if present)
    if not text:
        return None

    # If YAML frontmatter present, search inside first 60 lines
    head = "\n".join(text.splitlines()[:60])

    m = re.search(r"^\s*country_ru\s*:\s*(.+?)\s*$", head, flags=re.MULTILINE | re.IGNORECASE)
    if m:
        return m.group(1).strip().strip('"\'')

    m = re.search(r"^\s*country\s*:\s*(.+?)\s*$", head, flags=re.MULTILINE | re.IGNORECASE)
    if m:
        return m.group(1).strip().strip('"\'')

    return None


def _country_from_source_path(source: str) -> str:
    """Fallback: derive country from filename."""
    stem = os.path.splitext(os.path.basename(source))[0]
    # support names like: JP__japan__ru.md -> try to use second part
    parts = stem.split("__")
    if len(parts) >= 2 and parts[0].isupper() and len(parts[0]) <= 3:
        return parts[1]
    return parts[0]


@dataclass
class RetrievedChunk:
    source: str
    chunk: str


class LegalRAG:
    def __init__(self, persist_dir: str | None = None):
        self.persist_dir = persist_dir or settings.legal_chroma_dir
        self.embeddings = make_embeddings()
        self.vs = Chroma(
            collection_name="legal_kb",
            embedding_function=self.embeddings,
            persist_directory=self.persist_dir,
        )

    @staticmethod
    def build_index(kb_dir: str | None = None, persist_dir: str | None = None) -> None:
        kb_dir = kb_dir or settings.legal_kb_dir
        persist_dir = persist_dir or settings.legal_chroma_dir

        loader = DirectoryLoader(
            kb_dir,
            glob="**/*.md",
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},
            show_progress=True,
        )
        docs = loader.load()

        # Attach country metadata to each doc (later inherited by chunks)
        enriched_docs: List[Document] = []
        for d in docs:
            src = d.metadata.get("source", "")
            text = d.page_content or ""
            country_raw = _extract_country_from_text(text) or _country_from_source_path(src)
            country_norm = _norm_country(country_raw)

            md = dict(d.metadata)
            md["country"] = country_raw
            md["country_norm"] = country_norm
            enriched_docs.append(Document(page_content=text, metadata=md))

        splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=150)
        chunks = splitter.split_documents(enriched_docs)

        embeddings = make_embeddings()
        _ = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            collection_name="legal_kb",
            persist_directory=persist_dir,
        )

    def retrieve(self, query: str, country: str | None = None, k: int = 6) -> List[RetrievedChunk]:
        """Retrieve chunks, optionally filtered to a specific country."""
        filt = None
        if country:
            filt = {"country_norm": _norm_country(country)}

        # Prefer retriever with filter (LangChain docs recommend search_kwargs['filter'])
        if filt:
            retriever = self.vs.as_retriever(search_kwargs={"k": k, "filter": filt})
            docs = retriever.get_relevant_documents(query)
        else:
            docs = self.vs.similarity_search(query, k=k)

        out: List[RetrievedChunk] = []
        for d in docs:
            src = d.metadata.get("source", "unknown")
            out.append(RetrievedChunk(source=os.path.basename(src), chunk=d.page_content))
        return out
