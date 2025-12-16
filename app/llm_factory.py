from langchain_gigachat.chat_models import GigaChat
from langchain_gigachat.embeddings import GigaChatEmbeddings
from .config import settings

def make_llm(temperature: float = 0.2, max_tokens: int = 1200) -> GigaChat:
    return GigaChat(
        credentials=settings.gigachat_credentials,
        verify_ssl_certs=settings.gigachat_verify_ssl_certs,
        temperature=temperature,
        max_tokens=max_tokens,
    )

def make_embeddings() -> GigaChatEmbeddings:
    return GigaChatEmbeddings(
        credentials=settings.gigachat_credentials,
        verify_ssl_certs=settings.gigachat_verify_ssl_certs,
    )
