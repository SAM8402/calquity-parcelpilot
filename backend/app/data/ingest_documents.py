import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma
from app.config import PDF_DIR, CHROMA_DIR, EMBEDDING_MODEL, GOOGLE_API_KEY


DOCUMENT_METADATA = {
    "01_Support_Policy_v3_CURRENT.pdf": {
        "doc_type": "policy",
        "version": "v3",
        "status": "CURRENT",
        "authority": "high",
        "freshness": "current",
    },
    "02_Support_Policy_v2_DEPRECATED.pdf": {
        "doc_type": "policy",
        "version": "v2",
        "status": "DEPRECATED",
        "authority": "low",
        "freshness": "outdated",
    },
    "03_Cancellation_and_Service_Credit_SOP_v4.pdf": {
        "doc_type": "sop",
        "version": "v4",
        "status": "CURRENT",
        "authority": "high",
        "freshness": "current",
    },
    "04_Product_Operations_Guide_and_Known_Issues.pdf": {
        "doc_type": "operations_guide",
        "status": "CURRENT",
        "authority": "medium",
        "freshness": "current",
    },
    "05_Northstar_Logistics_Enterprise_Agreement.pdf": {
        "doc_type": "customer_agreement",
        "customer": "Northstar Logistics",
        "customer_account_id": "ACCT-001",
        "authority": "highest",
        "freshness": "current",
    },
    "06_LumenWorks_Service_Agreement.pdf": {
        "doc_type": "customer_agreement",
        "customer": "LumenWorks",
        "customer_account_id": "ACCT-002",
        "authority": "highest",
        "freshness": "current",
    },
}


def ingest_all_documents(pdf_dir: str = None, persist_dir: str = None):
    pdf_path = Path(pdf_dir) if pdf_dir else PDF_DIR
    persist_path = Path(persist_dir) if persist_dir else CHROMA_DIR

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " "],
    )
    embeddings = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=GOOGLE_API_KEY,
    )

    all_docs = []
    for filename, meta in DOCUMENT_METADATA.items():
        file_path = pdf_path / filename
        if not file_path.exists():
            print(f"WARNING: {filename} not found in {pdf_path}")
            continue

        loader = PyPDFLoader(str(file_path))
        pages = loader.load()
        chunks = splitter.split_documents(pages)
        for chunk in chunks:
            chunk.metadata.update(meta)
            chunk.metadata["source_file"] = filename
        all_docs.extend(chunks)
        print(f"Ingested {filename}: {len(chunks)} chunks")

    if not all_docs:
        print("No documents found to ingest.")
        return None

    vectorstore = Chroma.from_documents(
        documents=all_docs,
        embedding=embeddings,
        persist_directory=str(persist_path),
        collection_name="parcelpilot_docs",
    )
    print(f"Total chunks ingested: {len(all_docs)}")
    return vectorstore


if __name__ == "__main__":
    ingest_all_documents()
