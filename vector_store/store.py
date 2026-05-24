import chromadb
from langchain_openai import OpenAIEmbeddings
from config.settings import settings
import logging

logger = logging.getLogger(__name__)

COLLECTION_NAME = "hr_policies"


class VectorStore:
    def __init__(self):
        self.client = chromadb.HttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
        )
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=settings.openai_api_key,
        )
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"VectorStore initialised — collection: {COLLECTION_NAME}")

    def add_chunks(self, chunks: list) -> int:
        all_embeddings = []
        for chunk in chunks:
            vectors = self.embeddings.embed_documents([chunk.text])
            all_embeddings.append(vectors[0])

        self.collection.add(
            ids=[chunk.chunk_id for chunk in chunks],
            embeddings=all_embeddings,
            documents=[chunk.text for chunk in chunks],
            metadatas=[
                {
                    "source": chunk.source,
                    "page_number": chunk.page_number,
                    "chunk_index": chunk.chunk_index,
                    "source_path": chunk.source_path,
                }
                for chunk in chunks
            ],
        )
        logger.info(f"Added {len(chunks)} chunks to ChromaDB")
        return len(chunks)

    def query(self, question: str, top_k: int = 3) -> list[dict]:
        query_vector = self.embeddings.embed_query(question)
        results = self.collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        output = [
            {
                "text": doc,
                "source": meta["source"],
                "page_number": meta["page_number"],
                "chunk_index": meta["chunk_index"],
                "distance": dist,
            }
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]
        logger.info(f"Query returned {len(output)} chunks")
        return output

    def count(self) -> int:
        return self.collection.count()

    def reset(self) -> None:
        self.client.delete_collection(COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("Collection reset — all vectors deleted")

    def get_collection_info(self) -> dict:
        return {
            "name": COLLECTION_NAME,
            "count": self.count(),
            "embedding_model": "text-embedding-3-small",
        }


vector_store = VectorStore()
