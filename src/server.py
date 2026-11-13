"""MCP server that exposes the wireless security document search as tools."""
import sqlite3

from mcp.server.fastmcp import FastMCP

from search import DB_PATH, keyword_search, search

mcp = FastMCP(
    "wisec-assistant",
    log_level="WARNING",
    instructions=(
        "Search official NIST and NSA wireless security guidelines (Wi-Fi, Bluetooth, LTE, 5G). "
        "Use search_documents to find relevant passages, then get_document to read a section. "
        "Always cite the series number and pages, and warn the user when a source is withdrawn."
    ),
)


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _citation(series, page_start, page_end):
    if page_start == page_end:
        return f"{series}, p. {page_start}"
    return f"{series}, pp. {page_start}-{page_end}"


def _merge_overlapping(texts):
    """Join consecutive chunks, removing the text they share because of the overlap."""
    merged = ""
    for text in texts:
        start = merged.rfind(text[:60]) if merged else -1
        merged = merged[:start] + text if start != -1 else (merged + " " + text).strip()
    return merged


@mcp.tool()
def search_documents(query: str, k: int = 5, mode: str = "vector", chunk_size: int = 500) -> dict:
    """Find the passages in the wireless security guidelines most relevant to a question.

    Args:
        query: The question or topic, in plain English.
        k: Number of passages to return, from 1 to 10.
        mode: "vector" for semantic search by meaning (default), or "keyword" for exact-word search.
        chunk_size: 500 for short, precise passages (default) or 1500 for longer passages with more context.
    """
    if mode not in ("vector", "keyword"):
        raise ValueError('mode must be "vector" or "keyword"')
    if chunk_size not in (500, 1500):
        raise ValueError("chunk_size must be 500 or 1500")
    k = max(1, min(int(k), 10))
    hits = search(query, k, chunk_size) if mode == "vector" else keyword_search(query, k, chunk_size)
    return {
        "query": query,
        "mode": mode,
        "results": [
            {
                "rank": rank,
                "citation": _citation(h["series"], h["page_start"], h["page_end"]),
                "title": h["title"],
                "publisher": h["publisher"],
                "status": h["status"],
                "score": h["score"],
                "chunk_id": h["chunk_id"],
                "text": h["text"],
            }
            for rank, h in enumerate(hits, 1)
        ],
    }


@mcp.tool()
def get_document(document: str, page_start: int | None = None, page_end: int | None = None,
                 max_chars: int = 8000) -> dict:
    """Retrieve a document's details and text, or only a section of it by page range.

    Args:
        document: Series number (for example "SP 800-153" or "CSWP 36A"), file name, or document ID.
        page_start: First page of the section to read (optional).
        page_end: Last page of the section to read (optional; defaults to page_start).
        max_chars: Maximum characters of text to return (default 8000).
    """
    conn = _connect()
    key = document.strip()
    doc = conn.execute(
        """SELECT * FROM documents
           WHERE lower(series_number) = lower(?) OR filename = ? OR CAST(doc_id AS TEXT) = ?""",
        (key, key, key),
    ).fetchone()
    if doc is None:
        matches = conn.execute(
            "SELECT * FROM documents WHERE series_number LIKE ? OR title LIKE ?",
            (f"%{key}%", f"%{key}%"),
        ).fetchall()
        if len(matches) == 1:
            doc = matches[0]
        else:
            options = [r["series_number"] for r in conn.execute("SELECT series_number FROM documents")]
            conn.close()
            reason = "matches several documents" if matches else "was not found"
            raise ValueError(f'Document "{document}" {reason}. Available: {", ".join(options)}')

    first = page_start or 1
    last = page_end or page_start or doc["num_pages"] or 10**6
    rows = conn.execute(
        """SELECT text FROM chunks
           WHERE doc_id = ? AND chunk_size = 1500 AND page_end >= ? AND page_start <= ?
           ORDER BY chunk_index""",
        (doc["doc_id"], first, last),
    ).fetchall()
    conn.close()

    text = _merge_overlapping([r["text"] for r in rows])
    result = {
        "series": doc["series_number"],
        "title": doc["title"],
        "publisher": doc["publisher"],
        "year": doc["pub_year"],
        "status": doc["status"],
        "technology": doc["technology"],
        "total_pages": doc["num_pages"],
        "source_url": doc["source_url"],
        "pages_returned": f"{first}-{min(last, doc['num_pages'] or last)}",
        "truncated": len(text) > max_chars,
        "text": text[:max_chars],
    }
    if doc["status"] == "withdrawn":
        result["warning"] = "This publication has been withdrawn by its publisher and may be outdated."
    return result


@mcp.tool()
def list_documents() -> list[dict]:
    """List every document in the collection with its series number, title, year, status and size."""
    conn = _connect()
    rows = conn.execute(
        """SELECT d.series_number, d.title, d.publisher, d.pub_year, d.status, d.technology,
                  d.num_pages, COUNT(k.chunk_id) AS chunks
           FROM documents d LEFT JOIN chunks k ON k.doc_id = d.doc_id AND k.chunk_size = 500
           GROUP BY d.doc_id ORDER BY d.doc_id"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@mcp.tool()
def provide_feedback(question: str, answer: str, rating: int, cited_chunks: str = "") -> dict:
    """Record feedback on an answer, for evaluation.

    Args:
        question: The question that was asked.
        answer: The answer that was given.
        rating: 1 = helpful, 0 = partly helpful, -1 = not helpful.
        cited_chunks: Optional comma-separated chunk IDs that the answer cited.
    """
    if rating not in (-1, 0, 1):
        raise ValueError("rating must be -1, 0 or 1")
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO query_log (question, answer, cited_chunks, feedback) VALUES (?, ?, ?, ?)",
        (question, answer, cited_chunks, rating),
    )
    conn.commit()
    query_id = cur.lastrowid
    conn.close()
    return {"saved": True, "query_id": query_id}


if __name__ == "__main__":
    mcp.run()  # stdio transport
