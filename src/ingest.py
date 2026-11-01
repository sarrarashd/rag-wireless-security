"""Load, clean and chunk the source PDFs into the chunks table."""
import bisect
import re
import sqlite3
from collections import Counter
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "metadata.db"
RAW_DIR = ROOT / "data" / "raw"

CHUNK_SIZES = [500, 1500]   # characters; two strategies for the evaluation
OVERLAP_RATIO = 0.15        # each chunk repeats the last 15% of the previous one


def extract_pages(pdf_path):
    """Return the raw text of every page."""
    reader = PdfReader(pdf_path)
    return [page.extract_text() or "" for page in reader.pages]


def find_repeated_lines(pages, min_share=0.5):
    """Lines that appear on at least half of the pages are headers or footers."""
    counts = Counter()
    for text in pages:
        counts.update({line.strip() for line in text.splitlines() if line.strip()})
    limit = max(3, int(len(pages) * min_share))
    return {line for line, n in counts.items() if n >= limit}


def clean_page(text, repeated):
    """Remove headers, footers and page numbers, then normalize whitespace."""
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s in repeated:
            continue
        if re.fullmatch(r"(page\s*)?\d+|[ivxlc]+", s, flags=re.IGNORECASE):
            continue  # a line that is only a page number
        lines.append(s)
    text = "\n".join(lines)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # re-join words split across lines
    text = re.sub(r"\s*\n\s*", " ", text)          # join lines into running text
    text = re.sub(r"\.{4,}", " ", text)            # table-of-contents dot leaders
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def page_of(offset, starts):
    """1-based page number that contains a character offset."""
    return bisect.bisect_right(starts, offset)


def chunk_document(pages, size):
    """Split cleaned text into overlapping chunks, ending at sentences when possible."""
    full, starts = "", []
    for text in pages:
        starts.append(len(full))
        full += text + " "
    overlap = int(size * OVERLAP_RATIO)
    chunks, pos = [], 0
    while pos < len(full):
        end = min(pos + size, len(full))
        if end < len(full):
            cut = full.rfind(". ", pos + size // 2, end)
            if cut != -1:
                end = cut + 1
        text = full[pos:end].strip()
        if len(text) >= 50:
            chunks.append((page_of(pos, starts), page_of(end - 1, starts), text))
        if end >= len(full):
            break
        nxt = end - overlap
        space = full.find(" ", nxt, end)
        pos = space + 1 if space != -1 else nxt
    return chunks


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    docs = conn.execute(
        "SELECT doc_id, filename, series_number FROM documents ORDER BY doc_id"
    ).fetchall()

    print(f"{'Document':<22}{'Pages':>6}" + "".join(f"{'Chunks@' + str(s):>12}" for s in CHUNK_SIZES))
    totals = Counter()
    for doc_id, filename, series in docs:
        raw = extract_pages(RAW_DIR / filename)
        repeated = find_repeated_lines(raw)
        pages = [clean_page(p, repeated) for p in raw]
        conn.execute("UPDATE documents SET num_pages = ? WHERE doc_id = ?", (len(raw), doc_id))

        counts = []
        for size in CHUNK_SIZES:
            chunks = chunk_document(pages, size)
            conn.execute("DELETE FROM chunks WHERE doc_id = ? AND chunk_size = ?", (doc_id, size))
            conn.executemany(
                """INSERT INTO chunks
                   (doc_id, chunk_size, chunk_index, page_start, page_end, text, char_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [(doc_id, size, i, ps, pe, t, len(t)) for i, (ps, pe, t) in enumerate(chunks)],
            )
            counts.append(len(chunks))
            totals[size] += len(chunks)
        print(f"{series:<22}{len(raw):>6}" + "".join(f"{c:>12}" for c in counts))

    conn.commit()
    print(f"{'TOTAL':<28}" + "".join(f"{totals[s]:>12}" for s in CHUNK_SIZES))
    conn.close()


if __name__ == "__main__":
    main()
