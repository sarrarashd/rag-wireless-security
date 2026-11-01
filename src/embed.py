"""Embed every chunk and store the vectors in Chroma, one collection per chunk size."""
import sqlite3
import time

import chromadb

from search import CHROMA_PATH, DB_PATH, EMBED_FN, collection_name

BATCH = 128


def main():
    conn = sqlite3.connect(DB_PATH)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    sizes = [r[0] for r in conn.execute("SELECT DISTINCT chunk_size FROM chunks ORDER BY chunk_size")]

    for size in sizes:
        name = collection_name(size)
        if name in [c.name for c in client.list_collections()]:
            client.delete_collection(name)  # rebuild from scratch so the script can be re-run
        collection = client.create_collection(
            name, embedding_function=EMBED_FN, metadata={"hnsw:space": "cosine"}
        )
        rows = conn.execute(
            """SELECT k.chunk_id, k.text, k.doc_id, d.series_number, d.status,
                      k.page_start, k.page_end
               FROM chunks k JOIN documents d ON d.doc_id = k.doc_id
               WHERE k.chunk_size = ? ORDER BY k.chunk_id""",
            (size,),
        ).fetchall()

        start = time.perf_counter()
        for i in range(0, len(rows), BATCH):
            batch = rows[i:i + BATCH]
            collection.add(
                ids=[str(r[0]) for r in batch],
                documents=[r[1] for r in batch],
                metadatas=[{"doc_id": r[2], "series": r[3], "status": r[4],
                            "page_start": r[5] or 0, "page_end": r[6] or 0} for r in batch],
            )
            print(f"  {name}: {min(i + BATCH, len(rows))}/{len(rows)}", end="\r")
        print(f"  {name}: {collection.count()} vectors in {time.perf_counter() - start:.0f} s   ")
    conn.close()


if __name__ == "__main__":
    main()
