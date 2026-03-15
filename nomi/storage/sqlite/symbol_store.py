import sqlite3
from pathlib import Path
from typing import List, Optional

from nomi.storage.exceptions import StorageError
from nomi.storage.models import CodeUnit
from nomi.storage.sqlite.schema import DatabaseSchema


class SymbolStore:
    """Storage for code symbols and their metadata."""

    def __init__(self, db_path: Path) -> None:
        self.schema = DatabaseSchema(db_path)
        self.schema.initialize_database()
        self.db_path = db_path

    def _extract_symbol_name(self, unit_id: str) -> str:
        """Extract symbol name from unit ID (format: repo_path/file:symbol_name)."""
        if ":" in unit_id:
            return unit_id.split(":")[-1]
        return unit_id

    def insert_code_unit(self, code_unit: CodeUnit) -> None:
        """Insert or update a code unit in the database."""
        try:
            with self.schema.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO code_units (
                        id, unit_kind, file_path, start_byte, end_byte,
                        start_line, end_line, signature, body, docstring, language
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        code_unit.id,
                        code_unit.unit_kind.value,
                        code_unit.file_path,
                        code_unit.byte_range[0],
                        code_unit.byte_range[1],
                        code_unit.line_range[0],
                        code_unit.line_range[1],
                        code_unit.signature,
                        code_unit.body,
                        code_unit.docstring,
                        code_unit.language,
                    ),
                )

                symbol_name = self._extract_symbol_name(code_unit.id)
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO symbols (name, code_unit_id, file_path)
                    VALUES (?, ?, ?)
                    """,
                    (symbol_name, code_unit.id, code_unit.file_path),
                )

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO files (path, last_modified, language, indexed_at)
                    VALUES (
                        ?,
                        COALESCE((SELECT last_modified FROM files WHERE path = ?), 0),
                        ?,
                        COALESCE((SELECT indexed_at FROM files WHERE path = ?), 0)
                    )
                    """,
                    (
                        code_unit.file_path,
                        code_unit.file_path,
                        code_unit.language,
                        code_unit.file_path,
                    ),
                )

                conn.commit()
        except sqlite3.Error as e:
            raise StorageError(
                f"Failed to insert code unit {code_unit.id}: {e}"
            )

    def get_code_unit_by_id(self, unit_id: str) -> Optional[CodeUnit]:
        """Retrieve a code unit by its ID."""
        try:
            with self.schema.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, unit_kind, file_path, start_byte, end_byte,
                           start_line, end_line, signature, body, docstring, language
                    FROM code_units
                    WHERE id = ?
                    """,
                    (unit_id,),
                )
                row = cursor.fetchone()

                if row is None:
                    return None

                return self._row_to_code_unit(row)
        except sqlite3.Error as e:
            raise StorageError(f"Failed to retrieve code unit {unit_id}: {e}")

    def search_symbols(self, query: str, file_path: Optional[str] = None) -> List[CodeUnit]:
        """Search for symbols matching the query."""
        try:
            with self.schema.get_connection() as conn:
                cursor = conn.cursor()

                if file_path:
                    cursor.execute(
                        """
                        SELECT cu.id, cu.unit_kind, cu.file_path, cu.start_byte, cu.end_byte,
                               cu.start_line, cu.end_line, cu.signature, cu.body, cu.docstring, cu.language
                        FROM code_units cu
                        JOIN symbols s ON cu.id = s.code_unit_id
                        WHERE s.name LIKE ? AND cu.file_path = ?
                        LIMIT 100
                        """,
                        (f"%{query}%", file_path),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT cu.id, cu.unit_kind, cu.file_path, cu.start_byte, cu.end_byte,
                               cu.start_line, cu.end_line, cu.signature, cu.body, cu.docstring, cu.language
                        FROM code_units cu
                        JOIN symbols s ON cu.id = s.code_unit_id
                        WHERE s.name LIKE ?
                        LIMIT 100
                        """,
                        (f"%{query}%",),
                    )

                rows = cursor.fetchall()
                return [self._row_to_code_unit(row) for row in rows]
        except sqlite3.Error as e:
            raise StorageError(f"Failed to search symbols: {e}")

    def get_symbols_by_file(self, file_path: str) -> List[CodeUnit]:
        """Get all code units from a specific file."""
        try:
            with self.schema.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT id, unit_kind, file_path, start_byte, end_byte,
                           start_line, end_line, signature, body, docstring, language
                    FROM code_units
                    WHERE file_path = ?
                    ORDER BY start_line
                    """,
                    (file_path,),
                )
                rows = cursor.fetchall()
                return [self._row_to_code_unit(row) for row in rows]
        except sqlite3.Error as e:
            raise StorageError(f"Failed to get symbols for file {file_path}: {e}")

    def delete_by_file(self, file_path: str) -> None:
        """Delete all code units and associated data for a file."""
        try:
            with self.schema.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "DELETE FROM symbols WHERE file_path = ?",
                    (file_path,),
                )
                cursor.execute(
                    "DELETE FROM code_units WHERE file_path = ?",
                    (file_path,),
                )
                cursor.execute(
                    "DELETE FROM files WHERE path = ?",
                    (file_path,),
                )

                conn.commit()
        except sqlite3.Error as e:
            raise StorageError(f"Failed to delete file {file_path}: {e}")

    def get_all_symbols(self) -> List[str]:
        """Get all symbol names."""
        try:
            with self.schema.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT name FROM symbols ORDER BY name")
                return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            raise StorageError(f"Failed to get all symbols: {e}")

    def _row_to_code_unit(self, row: sqlite3.Row) -> CodeUnit:
        """Convert a database row to a CodeUnit object."""
        from nomi.storage.models import UnitKind

        return CodeUnit(
            id=row[0],
            unit_kind=UnitKind(row[1]),
            file_path=row[2],
            byte_range=(row[3], row[4]),
            line_range=(row[5], row[6]),
            signature=row[7],
            body=row[8],
            docstring=row[9],
            language=row[10],
        )
