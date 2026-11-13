"""Create the FTS5 keyword index (and its sync triggers) and fill it from existing chunks."""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "db" / "metadata.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_PATH.read_text())  # adds chunks_fts and triggers if missing
    conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES ('rebuild')")
    conn.commit()
    n_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    n_index = conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
    triggers = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'trigger' ORDER BY name")]
    print(f"Chunks: {n_chunks}  |  Indexed for keyword search: {n_index}")
    print("Sync triggers:", ", ".join(triggers))
    conn.close()


if __name__ == "__main__":
    main()
