from vector_store.store import vector_store
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    text: str
    source: str
    page_number: int
    chunk_id: str
    score: float
    citation: str


def semantic_search(
    query: str,
    n_results: int = 3,
    min_score: float = 0.0,
) -> list[SearchResult]:
    """Query ChromaDB and return ranked SearchResult objects.

    Cosine distance from ChromaDB is converted to similarity score via
    score = 1 - distance, so 1.0 = identical, 0.0 = maximally different.
    """
    try:
        raw = vector_store.query(question=query, top_k=n_results)

        results = []
        for item in raw:
            score = 1.0 - item["distance"]
            if score < min_score:
                continue
            source = item["source"]
            page = item["page_number"]
            results.append(SearchResult(
                text=item["text"],
                source=source,
                page_number=page,
                chunk_id=f"{source}_chunk_{item['chunk_index']}",
                score=score,
                citation=f"{source} (Page {page})",
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        logger.info(f"semantic_search: query={query!r} → {len(results)} results")
        return results

    except Exception as e:
        logger.error(f"semantic_search failed for query={query!r}: {e}")
        return []


def format_search_results(results: list[SearchResult]) -> str:
    """Format a list of SearchResults into a single string for LLM consumption."""
    if not results:
        return "No relevant information found."
    return "\n\n---\n\n".join(
        f"[Source: {r.citation}]\n{r.text}" for r in results
    )


def search_and_format(
    query: str,
    n_results: int = 3,
) -> str:
    """Convenience wrapper: semantic_search → format_search_results."""
    return format_search_results(semantic_search(query, n_results=n_results))


if __name__ == "__main__":
    test_queries = [
        "What is the parental leave policy?",
        "How many days of annual leave do employees get?",
        "What is the remote work policy?",
        "401k retirement benefits",
    ]
    for query in test_queries:
        print(f"\nQuery: {query}")
        results = semantic_search(query, n_results=2)
        print(f"Results: {len(results)}")
        for r in results:
            print(f"  [{r.score:.3f}] {r.citation}")
            print(f"  {r.text[:100]}...")
