from vector_store.store import vector_store, COLLECTION_NAME
from rag.document_rag.chunker import chunk_all_documents
import logging

logger = logging.getLogger(__name__)


def index_documents(reset: bool = False) -> dict:
    if reset:
        vector_store.reset()

    if vector_store.count() > 0 and not reset:
        logger.info("Documents already indexed. Use reset=True to reindex.")
        return {"status": "already_indexed", "count": vector_store.count()}

    chunks = chunk_all_documents()
    vector_store.add_chunks(chunks)
    return {
        "status": "success",
        "chunks_indexed": len(chunks),
        "collection": COLLECTION_NAME,
    }


def verify_index() -> dict:
    return vector_store.get_collection_info()


# Run with: uv run python -m vector_store.indexer
if __name__ == "__main__":
    print("Starting document indexing...")
    result = index_documents(reset=True)
    print(f"Status: {result['status']}")
    print(f"Chunks indexed: {result.get('chunks_indexed', 0)}")

    info = verify_index()
    print(f"Collection: {info['name']}")
    print(f"Total vectors in ChromaDB: {info['count']}")
    print(f"Embedding model: {info['embedding_model']}")
