import fitz
from pathlib import Path
import logging
import re
from typing import Generator
from dataclasses import dataclass

logger = logging.getLogger(__name__)

DOCUMENTS_DIR = Path("documents")
SUPPORTED_EXTENSIONS = {".pdf"}


@dataclass
class DocumentPage:
    text: str
    source: str
    source_path: str
    page_number: int
    total_pages: int


def clean_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r" {2,}", " ", text)
    lines = text.split("\n")
    filtered = [line for line in lines if len(line.strip()) >= 3 or not line.strip().isdigit()]
    text = "\n".join(filtered)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def extract_pages(pdf_path: Path) -> Generator[DocumentPage, None, None]:
    doc = fitz.open(pdf_path)
    logger.info(f"Extracting {pdf_path.name} ({doc.page_count} pages)")
    total_pages = doc.page_count
    for i, page in enumerate(doc):
        raw = page.get_text()
        cleaned = clean_text(raw)
        if not cleaned or len(cleaned) < 50:
            continue
        yield DocumentPage(
            text=cleaned,
            source=pdf_path.name,
            source_path=str(pdf_path),
            page_number=i + 1,
            total_pages=total_pages,
        )
    doc.close()


def load_all_documents() -> list[DocumentPage]:
    pdf_files = list(DOCUMENTS_DIR.rglob("*.pdf"))
    pages: list[DocumentPage] = []
    for pdf_path in pdf_files:
        pages.extend(extract_pages(pdf_path))
    logger.info(f"Loaded {len(pages)} pages from {len(pdf_files)} documents")
    return pages


def get_document_stats() -> dict:
    pages = load_all_documents()
    counts: dict[str, int] = {}
    for page in pages:
        counts[page.source] = counts.get(page.source, 0) + 1
    return {
        "total_documents": len(counts),
        "total_pages": len(pages),
        "documents": [{"name": name, "pages": count} for name, count in counts.items()],
    }


if __name__ == "__main__":
    stats = get_document_stats()
    print(f"Documents found: {stats['total_documents']}")
    print(f"Total pages: {stats['total_pages']}")
    for doc in stats["documents"]:
        print(f"  {doc['name']}: {doc['pages']} pages")

    pages = load_all_documents()
    if pages:
        print(f"\nSample text from {pages[0].source} page {pages[0].page_number}:")
        print(pages[0].text[:300])
