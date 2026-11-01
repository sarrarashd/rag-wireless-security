"""Semantic search over the document chunks (Chroma + SQLite)."""
import sqlite3
import sys
import time
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "metadata.db"
CHROMA_PATH = ROOT / "db" / "chroma"

# all-MiniLM-L6-v2 (384 dimensions), run locally through ONNX; no API key needed
EMBED_FN = embedding_functions.DefaultEmbeddingFunction()


def collection_name(chunk_size):
    return f"chunks_{chunk_size}"


def get_collection(chunk_size, client=None):
    client = client or chromadb.PersistentClient(path=str(CHROMA_PATH))
    return client.get_collection(collection_name(chunk_size), embedding_function=EMBED_FN)


def search(query, k=5, chunk_size=500):
    """Return the k chunks most similar in meaning to the query, with citation data."""
    collection = get_collection(chunk_size)
    result = collection.query(query_texts=[query], n_results=k)
    conn = sqlite3.connect(DB_PATH)
    hits = []
    for chunk_id, distance in zip(result["ids"][0], result["distances"][0]):
        row = conn.execute(
            """SELECT d.series_number, d.title, d.status, d.publisher,
                      k.page_start, k.page_end, k.text
               FROM chunks k JOIN documents d ON d.doc_id = k.doc_id
               WHERE k.chunk_id = ?""",
            (int(chunk_id),),
        ).fetchone()
        hits.append({
            "chunk_id": int(chunk_id),
            "score": round(1 - distance, 3),  # cosine similarity: 1 = identical meaning
            "series": row[0], "title": row[1], "status": row[2], "publisher": row[3],
            "page_start": row[4], "page_end": row[5], "text": row[6],
        })
    conn.close()
    return hits


def main():
    if len(sys.argv) < 2:
        print('Usage: python3 src/search.py "your question" [k] [chunk_size]')
        return
    query = sys.argv[1]
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    size = int(sys.argv[3]) if len(sys.argv) > 3 else 500
    start = time.perf_counter()
    hits = search(query, k, size)
    elapsed = time.perf_counter() - start
    print(f'Query: "{query}"  (k={k}, chunk_size={size}, {elapsed:.2f} s)\n')
    for rank, h in enumerate(hits, 1):
        flag = "  [WITHDRAWN]" if h["status"] == "withdrawn" else ""
        print(f'{rank}. score {h["score"]:.3f} | {h["series"]}, pages {h["page_start"]}-{h["page_end"]}{flag}')
        print(f'   {h["text"][:220]}...\n')


if __name__ == "__main__":
    main()
