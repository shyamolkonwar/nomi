"""Edge construction logic for the dependency graph."""

import re
from typing import Dict, List, Optional

from nomi.storage.models import CodeUnit, DependencyEdge, EdgeType


class EdgeBuilder:
    """Builds dependency edges between code units."""

    def build_call_edges(
        self, unit: CodeUnit, all_units: Dict[str, CodeUnit]
    ) -> List[DependencyEdge]:
        """Find CALLS edges by matching unit body against other unit names.

        Args:
            unit: The code unit to analyze
            all_units: Dictionary of all code units by ID

        Returns:
            List of CALLS dependency edges
        """
        edges: List[DependencyEdge] = []

        for other_id, other_unit in all_units.items():
            if other_id == unit.id:
                continue

            symbol_name = self._extract_symbol_name(other_id)
            if not symbol_name:
                continue

            pattern = self._get_call_pattern(symbol_name)
            if pattern.search(unit.body):
                edges.append(
                    DependencyEdge(
                        source_id=unit.id,
                        target_id=other_id,
                        edge_type=EdgeType.CALLS,
                    )
                )

        return edges

    def build_import_edges(
        self, unit: CodeUnit, file_units: Dict[str, List[CodeUnit]]
    ) -> List[DependencyEdge]:
        """Find IMPORTS edges from import statements in unit body.

        Args:
            unit: The code unit to analyze
            file_units: Dictionary mapping file paths to their code units

        Returns:
            List of IMPORTS dependency edges
        """
        edges: List[DependencyEdge] = []

        import_patterns = [
            r'import\s+(\w+)',
            r'from\s+(\S+)\s+import',
            r'require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
            r'import\s+[\'"]([^\'"]+)[\'"]',
        ]

        for pattern in import_patterns:
            for match in re.finditer(pattern, unit.body):
                import_path = match.group(1)
                resolved = self._resolve_import_path(import_path, unit.file_path, file_units)
                if resolved:
                    edges.append(
                        DependencyEdge(
                            source_id=unit.id,
                            target_id=resolved,
                            edge_type=EdgeType.IMPORTS,
                        )
                    )

        return edges

    def build_define_edges(
        self, file_path: str, units: List[CodeUnit]
    ) -> List[DependencyEdge]:
        """Create DEFINES edges from file to its code units.

        Args:
            file_path: Path to the source file
            units: List of code units defined in the file

        Returns:
            List of DEFINES dependency edges
        """
        edges: List[DependencyEdge] = []

        for unit in units:
            edges.append(
                DependencyEdge(
                    source_id=file_path,
                    target_id=unit.id,
                    edge_type=EdgeType.DEFINES,
                )
            )

        return edges

    def build_implement_edges(
        self, unit: CodeUnit, interface_units: List[CodeUnit]
    ) -> List[DependencyEdge]:
        """Find IMPLEMENTS edges for class-to-interface relationships.

        Args:
            unit: The class code unit to analyze
            interface_units: List of interface code units

        Returns:
            List of IMPLEMENTS dependency edges
        """
        edges: List[DependencyEdge] = []

        if unit.unit_kind.value not in ("CLASS", "METHOD"):
            return edges

        for interface in interface_units:
            interface_name = self._extract_symbol_name(interface.id)
            if not interface_name:
                continue

            implement_patterns = [
                rf'class\s+\w+\s*\([^)]*\b{re.escape(interface_name)}\b',
                rf'implements\s+{re.escape(interface_name)}\b',
                rf'extends\s+{re.escape(interface_name)}\b',
            ]

            for pattern in implement_patterns:
                if re.search(pattern, unit.body):
                    edges.append(
                        DependencyEdge(
                            source_id=unit.id,
                            target_id=interface.id,
                            edge_type=EdgeType.IMPLEMENTS,
                        )
                    )
                    break

        return edges

    def resolve_symbol_reference(
        self, symbol_name: str, context_file: str, all_units: Dict[str, CodeUnit]
    ) -> Optional[str]:
        """Resolve a symbol name to a unit ID.

        Args:
            symbol_name: The symbol name to resolve
            context_file: The file path where the symbol is referenced
            all_units: Dictionary of all code units by ID

        Returns:
            The unit ID if found, None otherwise
        """
        for unit_id, unit in all_units.items():
            if unit_id.endswith(f":{symbol_name}"):
                return unit_id

        context_dir = context_file.rsplit("/", 1)[0] if "/" in context_file else ""
        for unit_id, unit in all_units.items():
            if unit.file_path.startswith(context_dir) and unit_id.endswith(f":{symbol_name}"):
                return unit_id

        return None

    def _extract_symbol_name(self, unit_id: str) -> Optional[str]:
        """Extract the symbol name from a unit ID."""
        if ":" in unit_id:
            return unit_id.rsplit(":", 1)[1]
        return None

    def _get_call_pattern(self, symbol_name: str) -> re.Pattern:
        """Get a regex pattern to detect calls to a symbol."""
        return re.compile(rf'\b{re.escape(symbol_name)}\s*\(')

    def _resolve_import_path(
        self,
        import_path: str,
        context_file: str,
        file_units: Dict[str, List[CodeUnit]],
    ) -> Optional[str]:
        """Resolve an import path to a unit ID."""
        for file_path, units in file_units.items():
            if import_path in file_path or file_path.endswith(f"/{import_path.replace('.', '/')}"):
                if units:
                    return units[0].id

        for file_path, units in file_units.items():
            for unit in units:
                if unit.id.endswith(f":{import_path.split('.')[-1]}"):
                    return unit.id

        return None
