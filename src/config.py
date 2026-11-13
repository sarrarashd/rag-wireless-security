"""Paths and default settings shared by every script.

WISEC_DB and WISEC_CHROMA let tests point at a temporary copy instead of the real data.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
SCHEMA_PATH = ROOT / "db" / "schema.sql"
DB_PATH = Path(os.environ.get("WISEC_DB", ROOT / "db" / "metadata.db"))
CHROMA_PATH = Path(os.environ.get("WISEC_CHROMA", ROOT / "db" / "chroma"))

CHUNK_SIZES = (500, 1500)   # characters; two chunking strategies, compared in the evaluation
DEFAULT_CHUNK_SIZE = 500
DEFAULT_K = 5
