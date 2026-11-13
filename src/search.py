"""Search the document chunks: semantic (Chroma vectors), keyword (SQLite FTS5) or hybrid."""
import argparse
import re
import sqlite3
import time
from functools import lru_cache

import chromadb
from chromadb.utils import embedding_functions

from config import CHROMA_PATH, CHUNK_SIZES, DB_PATH, DEFAULT_CHUNK_SIZE, DEFAULT_K

# all-MiniLM-L6-v2 (384 dimensions), run locally through ONNX; no API key needed
EMBED_FN = embedding_functions.DefaultEmbeddingFunction()

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "to", "of", "in", "on", "for",
    "and", "or", "with", "by", "at", "from", "as", "it", "its", "this", "that", "do",
    "does", "can", "could", "should", "would", "how", "what", "which", "when", "why",
    "who", "my", "i", "me", "we", "you", "your", "our", "if", "about", "using", "use",
}


def collection_name(chunk_size):
    return f"chunks_{chunk_size}"


@lru_cache(maxsize=None)
def get_collection(chunk_size):
    """Open the Chroma collection for one chunk size (cached, so it is opened once per process)."""
    if chunk_size not in CHUNK_SIZES:
        raise ValueError(f"chunk_size must be one of {CHUNK_SIZES}")
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    try:
        return client.get_collection(collection_name(chunk_size), embedding_function=EMBED_FN)
    except Exception as exc:  # Chroma raises different error types across versions
        raise RuntimeError(
            f"Vector index '{collection_name(chunk_size)}' not found in {CHROMA_PATH}. "
            "Build it first with: python src/embed.py"
        ) from exc


def _fetch_chunk(conn, chunk_id):
    return conn.execute(
        """SELECT d.series_number, d.title, d.status, d.publisher,
                  k.page_start, k.page_end, k.text, d.doc_id, d.pub_year
           FROM chunks k JOIN documents d ON d.doc_id = k.doc_id
           WHERE k.chunk_id = ?""",
        (chunk_id,),
    ).fetchone()


def _hit(chunk_id, score, row):
    return {
        "chunk_id": chunk_id, "score": score,
        "series": row[0], "title": row[1], "status": row[2], "publisher": row[3],
        "page_start": row[4], "page_end": row[5], "text": row[6],
        "doc_id": row[7], "year": row[8],
    }


def search(query, k=DEFAULT_K, chunk_size=DEFAULT_CHUNK_SIZE):
    """Semantic search: the k chunks closest in meaning to the query."""
    if not query.strip():
        return []
    result = get_collection(chunk_size).query(query_texts=[query], n_results=k)
    conn = sqlite3.connect(DB_PATH)
    hits = []
    for chunk_id, distance in zip(result["ids"][0], result["distances"][0]):
        row = _fetch_chunk(conn, int(chunk_id))
        if row is None:  # vector index is older than the chunks table
            conn.close()
            raise RuntimeError("Vector index is out of date. Rebuild it with: python src/embed.py")
        # cosine similarity: 1 = identical meaning, 0 = unrelated
        hits.append(_hit(int(chunk_id), round(1 - distance, 3), row))
    conn.close()
    return hits


def keyword_query(text):
    """Turn a natural question into a safe FTS5 query: content words joined by OR."""
    words = [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS]
    return " OR ".join(f'"{w}"' for w in dict.fromkeys(words))


def keyword_search(query, k=DEFAULT_K, chunk_size=DEFAULT_CHUNK_SIZE):
    """Keyword search: BM25 ranking over the FTS5 index (exact words, with stemming)."""
    fts_query = keyword_query(query)
    if not fts_query:
        return []
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """SELECT f.rowid, bm25(chunks_fts) AS rank
           FROM chunks_fts f JOIN chunks k ON k.chunk_id = f.rowid
           WHERE chunks_fts MATCH ? AND k.chunk_size = ?
           ORDER BY rank LIMIT ?""",
        (fts_query, chunk_size, k),
    ).fetchall()
    # bm25() is negative; flip the sign so higher = more relevant
    hits = [_hit(cid, round(-rank, 2), _fetch_chunk(conn, cid)) for cid, rank in rows]
    conn.close()
    return hits


def hybrid_search(query, k=DEFAULT_K, chunk_size=DEFAULT_CHUNK_SIZE, pool=20, rrf_k=60):
    """Hybrid search: merge the vector and keyword rankings with reciprocal rank fusion.

    Each method contributes its top `pool` chunks. A chunk scores 1 / (rrf_k + rank) in
    each list it appears in, so a chunk ranked well by both methods comes first. Only
    ranks are used, because cosine similarity and BM25 scores are not comparable.
    """
    fused, by_id = {}, {}
    for hits in (search(query, pool, chunk_size), keyword_search(query, pool, chunk_size)):
        for rank, h in enumerate(hits, 1):
            fused[h["chunk_id"]] = fused.get(h["chunk_id"], 0) + 1 / (rrf_k + rank)
            by_id.setdefault(h["chunk_id"], h)
    best = sorted(fused, key=fused.get, reverse=True)[:k]
    return [{**by_id[cid], "score": round(fused[cid], 4)} for cid in best]


MODES = ("vector", "keyword", "hybrid")


def retrieve(query, k=DEFAULT_K, chunk_size=DEFAULT_CHUNK_SIZE, mode="vector"):
    """Run one search in the chosen mode: "vector", "keyword" or "hybrid"."""
    if mode == "vector":
        return search(query, k, chunk_size)
    if mode == "keyword":
        return keyword_search(query, k, chunk_size)
    if mode == "hybrid":
        return hybrid_search(query, k, chunk_size)
    raise ValueError('mode must be "vector", "keyword" or "hybrid"')


def main():
    parser = argparse.ArgumentParser(description="Search the wireless security documents.")
    parser.add_argument("query", help="question, in quotes")
    parser.add_argument("-k", type=int, default=5, help="number of results (default 5)")
    parser.add_argument("-s", "--size", type=int, default=500, help="chunk size: 500 or 1500")
    parser.add_argument("-m", "--mode", choices=MODES, default="vector")
    args = parser.parse_args()

    start = time.perf_counter()
    hits = retrieve(args.query, args.k, args.size, args.mode)
    elapsed = time.perf_counter() - start

    print(f'Query: "{args.query}"  (mode={args.mode}, k={args.k}, chunk_size={args.size}, {elapsed:.2f} s)')
    if args.mode != "vector":
        print(f"FTS5 query: {keyword_query(args.query)}")
    print()
    if not hits:
        print("No results.")
    for rank, h in enumerate(hits, 1):
        flag = "  [WITHDRAWN]" if h["status"] == "withdrawn" else ""
        print(f'{rank}. score {h["score"]} | {h["series"]}, pages {h["page_start"]}-{h["page_end"]}{flag}')
        print(f'   {h["text"][:220]}...\n')


if __name__ == "__main__":
    main()
