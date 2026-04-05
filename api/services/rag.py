"""
RAG retrieval service.

Embeds a query using the same model as ingest_knowledge.py,
runs cosine similarity search against knowledge_chunks,
returns the top-k most relevant text chunks.
"""

from functools import lru_cache

from sentence_transformers import SentenceTransformer
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

MODEL_NAME = "all-MiniLM-L6-v2"
TOP_K      = 4   # chunks injected into Claude's context


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    """Load once, reuse across requests."""
    return SentenceTransformer(MODEL_NAME)


async def retrieve(query: str, db: AsyncSession, k: int = TOP_K) -> list[dict]:
    """
    Embed `query` and return the k most similar knowledge chunks.

    Returns a list of dicts: {source_title, content, similarity}
    """
    model     = _get_model()
    embedding = model.encode(query, normalize_embeddings=True).tolist()

    result = await db.execute(text("""
        SELECT source_title, content,
               1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
        FROM   knowledge_chunks
        ORDER  BY embedding <=> CAST(:embedding AS vector)
        LIMIT  :k
    """), {"embedding": str(embedding), "k": k})

    return [
        {"source_title": row.source_title, "content": row.content, "similarity": float(row.similarity)}
        for row in result.fetchall()
    ]
