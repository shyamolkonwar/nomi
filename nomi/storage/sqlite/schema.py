import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from nomi.storage.exceptions import StorageError

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS code_units (
    id TEXT PRIMARY KEY,
    unit_kind TEXT NOT NULL,
    file_path TEXT NOT NULL,
    start_byte INTEGER NOT NULL,
    end_byte INTEGER NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    signature TEXT NOT NULL,
    body TEXT NOT NULL,
    docstring TEXT,
    language TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_code_units_file_path ON code_units(file_path);
CREATE INDEX IF NOT EXISTS idx_code_units_unit_kind ON code_units(unit_kind);
CREATE INDEX IF NOT EXISTS idx_code_units_language ON code_units(language);

CREATE TABLE IF NOT EXISTS dependencies (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    PRIMARY KEY (source_id, target_id, edge_type),
    FOREIGN KEY (source_id) REFERENCES code_units(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES code_units(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dependencies_source ON dependencies(source_id);
CREATE INDEX IF NOT EXISTS idx_dependencies_target ON dependencies(target_id);

CREATE TABLE IF NOT EXISTS symbols (
    name TEXT NOT NULL,
    code_unit_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    PRIMARY KEY (name, code_unit_id),
    FOREIGN KEY (code_unit_id) REFERENCES code_units(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_file_path ON symbols(file_path);

CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY,
    last_modified REAL NOT NULL,
    language TEXT NOT NULL,
    indexed_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_files_language ON files(language);
"""

DROP_TABLES_SQL = """
DROP TABLE IF EXISTS symbols;
DROP TABLE IF EXISTS dependencies;
DROP TABLE IF EXISTS code_units;
DROP TABLE IF EXISTS files;
"""


class DatabaseSchema:
    """Manages database schema creation and versioning."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection with proper configuration."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def create_tables(self) -> None:
        """Create all database tables and indexes."""
        try:
            with self.get_connection() as conn:
                conn.executescript(SCHEMA_SQL)
                conn.commit()
        except sqlite3.Error as e:
            raise StorageError(f"Failed to create database tables: {e}")

    def drop_tables(self) -> None:
        """Drop all database tables."""
        try:
            with self.get_connection() as conn:
                conn.executescript(DROP_TABLES_SQL)
                conn.commit()
        except sqlite3.Error as e:
            raise StorageError(f"Failed to drop database tables: {e}")

    def initialize_database(self) -> None:
        """Initialize database with schema if not exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.create_tables()


def create_tables(db_path: Path) -> None:
    """Create all database tables."""
    schema = DatabaseSchema(db_path)
    schema.create_tables()


def drop_tables(db_path: Path) -> None:
    """Drop all database tables."""
    schema = DatabaseSchema(db_path)
    schema.drop_tables()


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Get a configured SQLite connection."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn
