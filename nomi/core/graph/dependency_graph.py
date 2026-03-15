"""Dependency graph engine for Nomi."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Set

from nomi.storage.models import CodeUnit, DependencyEdge, EdgeType
from nomi.storage.sqlite.graph_store import GraphStore

from .edge_builder import EdgeBuilder
from .traversal import GraphTraversal


@dataclass
class DependencyTree:
    """Hierarchical tree structure for dependencies."""

    unit_id: str
    children: List["DependencyTree"] = field(default_factory=list)
    edge_type: str = ""


class DependencyGraph:
    """Manages the dependency graph for code analysis."""

    def __init__(self, db_path: str) -> None:
        self.graph_store = GraphStore(Path(db_path))
        self.edge_builder = EdgeBuilder()
        self.traversal = GraphTraversal(self.graph_store)

    def build_from_code_unit(self, unit: CodeUnit) -> List[DependencyEdge]:
        """Analyze unit.dependencies and create edges.

        Args:
            unit: The code unit to analyze

        Returns:
            List of created dependency edges
        """
        edges: List[DependencyEdge] = []

        for dep_id in unit.dependencies:
            edge = DependencyEdge(
                source_id=unit.id,
                target_id=dep_id,
                edge_type=EdgeType.CALLS,
            )
            edges.append(edge)
            self.graph_store.insert_edge(edge)

        return edges

    def build_for_file(
        self, file_path: str, code_units: List[CodeUnit]
    ) -> List[DependencyEdge]:
        """Build all edges for a file's code units.

        Args:
            file_path: Path to the source file
            code_units: List of code units in the file

        Returns:
            List of all created dependency edges
        """
        edges: List[DependencyEdge] = []

        define_edges = self.edge_builder.build_define_edges(file_path, code_units)
        for edge in define_edges:
            edges.append(edge)
            self.graph_store.insert_edge(edge)

        units_dict = {unit.id: unit for unit in code_units}
        file_units_dict = {file_path: code_units}

        interface_units = [
            unit for unit in code_units if unit.unit_kind.value == "INTERFACE"
        ]

        for unit in code_units:
            call_edges = self.edge_builder.build_call_edges(unit, units_dict)
            for edge in call_edges:
                edges.append(edge)
                self.graph_store.insert_edge(edge)

            import_edges = self.edge_builder.build_import_edges(unit, file_units_dict)
            for edge in import_edges:
                edges.append(edge)
                self.graph_store.insert_edge(edge)

            if unit.unit_kind.value == "CLASS":
                implement_edges = self.edge_builder.build_implement_edges(
                    unit, interface_units
                )
                for edge in implement_edges:
                    edges.append(edge)
                    self.graph_store.insert_edge(edge)

        return edges

    def get_dependencies(self, unit_id: str, depth: int = 1) -> List[str]:
        """Get dependencies with configurable depth.

        Args:
            unit_id: The code unit ID
            depth: Maximum depth to traverse

        Returns:
            List of dependency unit IDs
        """
        if depth == 1:
            return self.graph_store.get_dependencies(unit_id)

        return self.traversal.traverse_bfs(
            unit_id, max_depth=depth, edge_types=None
        )

    def get_dependents(self, unit_id: str, depth: int = 1) -> List[str]:
        """Get reverse dependencies (callers).

        Args:
            unit_id: The code unit ID
            depth: Maximum depth to traverse

        Returns:
            List of dependent unit IDs
        """
        if depth == 1:
            return self.graph_store.get_dependents(unit_id)

        visited: Set[str] = {unit_id}
        queue: List[tuple[str, int]] = [(unit_id, 0)]
        result: List[str] = []

        while queue:
            current_id, current_depth = queue.pop(0)

            if current_depth >= depth:
                continue

            try:
                dependents = self.graph_store.get_dependents(current_id)
            except Exception:
                continue

            for dep_id in dependents:
                if dep_id not in visited:
                    visited.add(dep_id)
                    result.append(dep_id)
                    queue.append((dep_id, current_depth + 1))

        return result

    def get_dependency_tree(
        self, unit_id: str, max_depth: int = 2
    ) -> DependencyTree:
        """Get hierarchical tree of dependencies.

        Args:
            unit_id: The root code unit ID
            max_depth: Maximum depth to traverse

        Returns:
            DependencyTree representing the dependency hierarchy
        """
        visited: Set[str] = set()

        def build_tree(current_id: str, depth: int) -> DependencyTree:
            tree = DependencyTree(unit_id=current_id)
            visited.add(current_id)

            if depth >= max_depth:
                return tree

            try:
                edges = self.graph_store.get_edges_for_unit(current_id)
            except Exception:
                return tree

            for edge in edges:
                if edge.source_id == current_id and edge.target_id not in visited:
                    child = build_tree(edge.target_id, depth + 1)
                    child.edge_type = edge.edge_type.value
                    tree.children.append(child)

            return tree

        return build_tree(unit_id, 0)

    def remove_file_edges(self, file_path: str) -> None:
        """Remove all edges for a file.

        Args:
            file_path: Path to the source file
        """
        self.graph_store.delete_edges_for_file(file_path)

    def get_traversal(self) -> GraphTraversal:
        """Get the graph traversal instance."""
        return self.traversal

    def get_edge_builder(self) -> EdgeBuilder:
        """Get the edge builder instance."""
        return self.edge_builder
