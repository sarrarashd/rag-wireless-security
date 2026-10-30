PRAGMA foreign_keys = ON;

-- Metadata for each source document
CREATE TABLE IF NOT EXISTS documents (
doc_id        INTEGER PRIMARY KEY AUTOINCREMENT,
filename      TEXT NOT NULL UNIQUE,
title         TEXT NOT NULL,
publisher     TEXT NOT NULL,
series_number TEXT,
pub_year      INTEGER CHECK (pub_year BETWEEN 1990 AND 2100),
status        TEXT NOT NULL DEFAULT 'final'
CHECK (status IN ('final', 'draft', 'withdrawn')),
technology    TEXT NOT NULL,
source_url    TEXT,
num_pages     INTEGER,
added_at      TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Text chunks; chunk_size lets us store several chunking strategies
CREATE TABLE IF NOT EXISTS chunks (
chunk_id     INTEGER PRIMARY KEY AUTOINCREMENT,
doc_id       INTEGER NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
chunk_size   INTEGER NOT NULL,
chunk_index  INTEGER NOT NULL,
page_start   INTEGER,
page_end     INTEGER,
text         TEXT NOT NULL,
char_count   INTEGER,
UNIQUE (doc_id, chunk_size, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id, chunk_size);

-- Questions asked to the assistant (for evaluation and feedback)
CREATE TABLE IF NOT EXISTS query_log (
query_id      INTEGER PRIMARY KEY AUTOINCREMENT,
question      TEXT NOT NULL,
answer        TEXT,
cited_chunks  TEXT,
latency_ms    INTEGER,
feedback      INTEGER CHECK (feedback IN (-1, 0, 1)),
created_at    TEXT DEFAULT CURRENT_TIMESTAMP
);