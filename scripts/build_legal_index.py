from app.rag.legal_rag import LegalRAG
from app.config import settings

if __name__ == "__main__":
    LegalRAG.build_index(settings.legal_kb_dir, settings.legal_chroma_dir)
    print("✅ Legal index built at:", settings.legal_chroma_dir)

# Tip: add 'country_ru: <Страна>' at top of each kb/legal/*.md for precise filtering.
