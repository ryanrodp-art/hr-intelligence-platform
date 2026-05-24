from vector_store.store import vector_store
from config.settings import settings
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    text: str
    source: str
    page_number: int
    chunk_index: int
    similarity_score: float
    citation: str


def format_citation(source: str, page_number: int) -> str:
    name_map = {
        "leave_policy.pdf": "Leave Policy",
        "code_of_conduct.pdf": "Code of Conduct",
        "benefits_guide.pdf": "Benefits Guide",
        "employee_handbook.pdf": "Employee Handbook",
    }
    document_name = name_map.get(source, source.replace("_", " ").replace(".pdf", "").title())
    return f"{document_name}, Page {page_number}"


def retrieve(
    query: str,
    top_k: int = 3,
    min_similarity: float = 0.3,
) -> list[RetrievedChunk]:
    raw = vector_store.query(query, top_k=top_k)
    chunks = []
    for result in raw:
        similarity = 1 - result["distance"]
        if similarity < min_similarity:
            continue
        chunks.append(
            RetrievedChunk(
                text=result["text"],
                source=result["source"],
                page_number=result["page_number"],
                chunk_index=result["chunk_index"],
                similarity_score=similarity,
                citation=format_citation(result["source"], result["page_number"]),
            )
        )
    chunks.sort(key=lambda c: c.similarity_score, reverse=True)
    logger.info(f"Retrieved {len(chunks)} chunks for query: {query[:50]}...")
    return chunks


def retrieve_with_context(
    query: str,
    top_k: int = 3,
) -> dict:
    chunks = retrieve(query, top_k=top_k)
    context_parts = [f"[{chunk.citation}]\n{chunk.text}" for chunk in chunks]
    context_text = "\n\n".join(context_parts)
    sources = list(dict.fromkeys(chunk.citation for chunk in chunks))
    return {
        "query": query,
        "chunks": chunks,
        "context_text": context_text,
        "sources": sources,
    }


def test_retrieval() -> None:
    queries = [
        "How many days annual leave do I get?",
        "What is the parental leave policy?",
        "What is the remote work policy?",
        "How do I report harassment?",
        "What is the company retirement plan?",
    ]
    for query in queries:
        print(f"\nQuery: {query}")
        chunks = retrieve(query, top_k=3)
        for chunk in chunks:
            print(f"  [{chunk.citation}] similarity={chunk.similarity_score:.3f}")
            print(f"  {chunk.text[:150]}")
        print("-" * 60)


# Run with: uv run python -m rag.document_rag.retriever
if __name__ == "__main__":
    test_retrieval()
