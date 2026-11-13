"""Create the FTS5 keyword index (and its sync triggers) and fill it from existing chunks."""
import sqlite3
from config import DB_PATH, SCHEMA_PATH
