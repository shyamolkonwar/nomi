import sqlite3
from pathlib import Path
from typing import List, Optional

from nomi.storage.exceptions import StorageError
from nomi.storage.models import DependencyEdge, EdgeType
from nomi.storage.sqlite.schema import DatabaseSchema


class GraphStore:
    """Storage for dependency graph edges."""

    def __init__(self, db_path: Path) -> None:
        self.schema = DatabaseSchema(db_path)
        self.schema.initialize_database()
        self.db_path = db_path

    def insert_edge(self, edge: DependencyEdge) -> None:
        """Insert a dependency edge into the database."""
        try:
            with self.schema.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO dependencies (source_id, target_id, edge_type)
                    VALUES (?, ?, ?)
                    """,
                    (edge.source_id, edge.target_id, edge.edge_type.value),
                )
                conn.commit()
        except sqlite3.Error as e:
            raise StorageError(
                f"Failed to insert edge {edge.source_id} -> {edge.target_id}: {e}"
            )

    def get_dependencies(
        self, unit_id: str, edge_type: Optional[str] = None
    ) -> List[str]:
        """Get all dependencies (outgoing edges) for a code unit."""
        try:
            with self.schema.get_connection() as conn:
                cursor = conn.cursor()

                if edge_type:
                    cursor.execute(
                        """
                        SELECT target_id FROM dependencies
                        WHERE source_id = ? AND edge_type = ?
                        """,
                        (unit_id, edge_type),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT target_id FROM dependencies
                        WHERE source_id = ?
                        """,
                        (unit_id,),
                    )

                return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            raise StorageError(f"Failed to get dependencies for {unit_id}: {e}")

    def get_dependents(self, unit_id: str) -> List[str]:
        """Get all dependents (incoming edges) for a code unit."""
        try:
            with self.schema.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT source_id FROM dependencies
                    WHERE target_id = ?
                    """,
                    (unit_id,),
                )
                return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            raise StorageError(f"Failed to get dependents for {unit_id}: {e}")

    def get_edges_for_unit(self, unit_id: str) -> List[DependencyEdge]:
        """Get all edges (both directions) for a code unit."""
        try:
            with self.schema.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT source_id, target_id, edge_type FROM dependencies
                    WHERE source_id = ? OR target_id = ?
                    """,
                    (unit_id, unit_id),
                )
                return [
                    DependencyEdge(
                        source_id=row[0],
                        target_id=row[1],
                        edge_type=EdgeType(row[2]),
                    )
                    for row in cursor.fetchall()
                ]
        except sqlite3.Error as e:
            raise StorageError(f"Failed to get edges for {unit_id}: {e}")

    def delete_edges_for_file(self, file_path: str) -> None:
        """Delete all edges involving code units from a specific file."""
        try:
            with self.schema.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    DELETE FROM dependencies
                    WHERE source_id IN (
                        SELECT id FROM code_units WHERE file_path = ?
                    )
                    OR target_id IN (
                        SELECT id FROM code_units WHERE file_path = ?
                    )
                    """,
                    (file_path, file_path),
                )
                conn.commit()
        except sqlite3.Error as e:
            raise StorageError(f"Failed to delete edges for file {file_path}: {e}")

    def get_all_edges(self) -> List[DependencyEdge]:
        """Get all dependency edges in the database."""
        try:
            with self.schema.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT source_id, target_id, edge_type FROM dependencies"
                )
                return [
                    DependencyEdge(
                        source_id=row[0],
                        target_id=row[1],
                        edge_type=EdgeType(row[2]),
                    )
                    for row in cursor.fetchall()
                ]
        except sqlite3.Error as e:
            raise StorageError(f"Failed to get all edges: {e}")
