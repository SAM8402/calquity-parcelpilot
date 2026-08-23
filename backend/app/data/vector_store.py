import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma
from app.config import CHROMA_DIR, EMBEDDING_MODEL, GOOGLE_API_KEY


def get_vectorstore():
    embeddings = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=GOOGLE_API_KEY,
    )
    return Chroma(
        persist_directory=str(CHROMA_DIR),
        embedding_function=embeddings,
        collection_name="parcelpilot_docs",
    )


def get_retriever(k: int = 5):
    vectorstore = get_vectorstore()
    return vectorstore.as_retriever(search_kwargs={"k": k})


def search_with_metadata(query: str, k: int = 5, filter_dict: dict = None):
    vectorstore = get_vectorstore()
    kwargs = {"k": k}
    if filter_dict:
        kwargs["filter"] = filter_dict
    return vectorstore.similarity_search_with_score(query, **kwargs)
