"""
Ingest Science/*.txt transcripts into knowledge_chunks table.

Chunks each file into ~300-token paragraphs, embeds with
sentence-transformers (all-MiniLM-L6-v2, 384-dim), stores in Postgres.

Usage:
    python ingest_knowledge.py              # ingest all files
    python ingest_knowledge.py --clear      # clear table first, then ingest
"""

import argparse
import os
import re
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values
from sentence_transformers import SentenceTransformer

from config import DB_HOST, DB_NAME, DB_USER, DB_PASSWORD

SCIENCE_DIR = Path(__file__).parent / "Science"
CHUNK_SIZE  = 300   # approximate tokens per chunk (words * ~1.3)
CHUNK_OVERLAP = 30  # words of overlap between chunks

MODEL_NAME = "all-MiniLM-L6-v2"  # 384-dim, fast, good for semantic search

# ── title inference from filename ────────────────────────────────────────────

def title_from_filename(path: Path) -> str:
    stem = path.stem.replace("_cleaned", "").replace("_", " ")
    return stem.title()

# ── chunking ─────────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_words: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping word-window chunks."""
    # Normalise whitespace
    text = re.sub(r"\s+", " ", text).strip()
    words = text.split()

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_words, len(words))
        chunk = " ".join(words[start:end])
        if len(chunk.strip()) > 40:   # skip near-empty tail chunks
            chunks.append(chunk)
        start += chunk_words - overlap

    return chunks

# ── main ─────────────────────────────────────────────────────────────────────

def main(clear: bool = False):
    print(f"Loading model {MODEL_NAME}…")
    model = SentenceTransformer(MODEL_NAME)

    conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD)
    cur  = conn.cursor()

    if clear:
        cur.execute("TRUNCATE knowledge_chunks RESTART IDENTITY;")
        conn.commit()
        print("Table cleared.")

    txt_files = sorted(SCIENCE_DIR.glob("*.txt"))
    if not txt_files:
        print(f"No .txt files found in {SCIENCE_DIR}")
        return

    total_chunks = 0

    for path in txt_files:
        title = title_from_filename(path)
        text  = path.read_text(encoding="utf-8")
        chunks = chunk_text(text)

        print(f"{path.name}: {len(chunks)} chunks", end="", flush=True)

        embeddings = model.encode(chunks, show_progress_bar=False, normalize_embeddings=True)

        rows = [
            (str(path.name), title, idx, chunk, embedding.tolist())
            for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]

        execute_values(cur, """
            INSERT INTO knowledge_chunks (source_file, source_title, chunk_index, content, embedding)
            VALUES %s
            ON CONFLICT DO NOTHING
        """, rows)
        conn.commit()

        total_chunks += len(chunks)
        print(f" done")

    # Rebuild index now that data exists
    cur.execute("REINDEX INDEX knowledge_chunks_embedding_idx;")
    conn.commit()

    cur.close()
    conn.close()
    print(f"\nDone — {total_chunks} chunks ingested from {len(txt_files)} files.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true", help="Clear table before ingesting")
    args = parser.parse_args()
    main(clear=args.clear)
