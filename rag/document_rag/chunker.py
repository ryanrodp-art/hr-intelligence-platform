from langchain_text_splitters import RecursiveCharacterTextSplitter
from rag.document_rag.ingestion import DocumentPage, load_all_documents
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    text: str
    source: str
    source_path: str
    page_number: int
    chunk_index: int
    total_chunks_in_page: int
    chunk_id: str


def create_splitter(
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )


def chunk_page(
    page: DocumentPage,
    splitter: RecursiveCharacterTextSplitter,
) -> list[DocumentChunk]:
    raw_chunks = splitter.split_text(page.text)
    raw_chunks = [c for c in raw_chunks if len(c) >= 50]
    stem = Path(page.source).stem if False else page.source.rsplit(".", 1)[0]
    chunks = [
        DocumentChunk(
            text=chunk,
            source=page.source,
            source_path=page.source_path,
            page_number=page.page_number,
            chunk_index=i,
            total_chunks_in_page=len(raw_chunks),
            chunk_id=f"{stem}_p{page.page_number}_c{i}",
        )
        for i, chunk in enumerate(raw_chunks)
    ]
    logger.info(f"Page {page.page_number} of {page.source}: {len(chunks)} chunks created")
    return chunks


def chunk_all_documents(
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> list[DocumentChunk]:
    pages = load_all_documents()
    splitter = create_splitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    all_chunks: list[DocumentChunk] = []
    for page in pages:
        all_chunks.extend(chunk_page(page, splitter))
    total_docs = len({c.source for c in all_chunks})
    logger.info(
        f"Chunking complete: {len(all_chunks)} chunks from "
        f"{len(pages)} pages across {total_docs} documents"
    )
    return all_chunks


def get_chunking_stats(chunks: list[DocumentChunk]) -> dict:
    sizes = [len(c.text) for c in chunks]
    counts: dict[str, int] = {}
    for chunk in chunks:
        counts[chunk.source] = counts.get(chunk.source, 0) + 1
    return {
        "total_chunks": len(chunks),
        "avg_chunk_size": sum(sizes) / len(sizes) if sizes else 0.0,
        "min_chunk_size": min(sizes) if sizes else 0,
        "max_chunk_size": max(sizes) if sizes else 0,
        "chunks_by_document": counts,
    }


# Run with: uv run python -m rag.document_rag.chunker
if __name__ == "__main__":
    chunks = chunk_all_documents()
    stats = get_chunking_stats(chunks)

    print(f"Total chunks: {stats['total_chunks']}")
    print(f"Average chunk size: {stats['avg_chunk_size']:.0f} chars")
    print(f"Min chunk size: {stats['min_chunk_size']} chars")
    print(f"Max chunk size: {stats['max_chunk_size']} chars")
    print("\nChunks by document:")
    for doc, count in stats["chunks_by_document"].items():
        print(f"  {doc}: {count} chunks")

    print("\nSample chunks:")
    for chunk in chunks[:3]:
        print(f"\n[{chunk.chunk_id}]")
        print(chunk.text[:200])
        print("---")
