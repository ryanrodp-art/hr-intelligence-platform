from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from rag.document_rag.retriever import retrieve_with_context
from config.settings import settings
import logging
from dataclasses import dataclass, field
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

RAG_SYSTEM_PROMPT = (
    "You are ARIA, an HR Intelligence Assistant for Acme Corp.\n"
    "You answer questions based ONLY on the provided company documents.\n\n"
    "Rules:\n"
    "- Answer using ONLY the information in the Context section below\n"
    "- Always mention which document your answer comes from\n"
    "- If the context does not contain enough information to answer\n"
    "  the question, say: 'I don't have specific information about\n"
    "  that in our company documents. Please contact HR at\n"
    "  hr@acmecorp.com or ext. 4100 for assistance.'\n"
    "- Never make up information not present in the context\n"
    "- Be concise and direct — employees need clear answers\n"
    "- Format your answer clearly with the key information first"
)

_FALLBACK = (
    "I don't have specific information about that in our company documents. "
    "Please contact HR at hr@acmecorp.com or ext. 4100."
)


@dataclass
class RAGResponse:
    answer: str
    sources: list[str]
    chunks_used: int
    query: str


def build_rag_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", RAG_SYSTEM_PROMPT),
        ("human", (
            "Context from Acme Corp documents:\n\n"
            "{context}\n\n"
            "Employee question: {question}\n\n"
            "Please answer based on the context above."
        )),
    ])


def get_rag_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.openai_model,
        temperature=0.1,
        api_key=settings.openai_api_key,
    )


async def rag_query(question: str) -> RAGResponse:
    retrieval_result = retrieve_with_context(question, top_k=3)
    chunks = retrieval_result["chunks"]

    if not chunks:
        return RAGResponse(
            answer=_FALLBACK,
            sources=[],
            chunks_used=0,
            query=question,
        )

    prompt = build_rag_prompt()
    llm = get_rag_llm()
    chain = prompt | llm | StrOutputParser()

    generated_answer = await chain.ainvoke({
        "context": retrieval_result["context_text"],
        "question": question,
    })

    sources = retrieval_result["sources"]
    logger.info(f"RAG query answered from {len(chunks)} chunks, sources: {sources}")

    return RAGResponse(
        answer=generated_answer,
        sources=sources,
        chunks_used=len(chunks),
        query=question,
    )


async def rag_query_stream(question: str) -> AsyncGenerator[str, None]:
    retrieval_result = retrieve_with_context(question, top_k=3)
    chunks = retrieval_result["chunks"]

    if not chunks:
        yield _FALLBACK
        return

    prompt = build_rag_prompt()
    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=0.1,
        streaming=True,
        api_key=settings.openai_api_key,
    )
    chain = prompt | llm | StrOutputParser()

    async for chunk in chain.astream({
        "context": retrieval_result["context_text"],
        "question": question,
    }):
        if chunk:
            yield chunk

    sources = retrieval_result["sources"]
    logger.info(f"RAG stream completed, sources: {sources}")


# Run with: uv run python -m rag.document_rag.chain
if __name__ == "__main__":
    import asyncio

    test_questions = [
        "How many days of annual leave do I get?",
        "What is the parental leave policy at Acme Corp?",
        "What is the remote work policy?",
        "How do I report a harassment complaint?",
        "What does the company contribute to the retirement plan?",
    ]

    async def run_tests():
        for question in test_questions:
            print(f"\nQ: {question}")
            result = await rag_query(question)
            print(f"A: {result.answer}")
            print(f"Sources: {result.sources}")
            print(f"Chunks used: {result.chunks_used}")
            print("-" * 60)

    asyncio.run(run_tests())
