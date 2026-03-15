"""Module-level dependency graph for architecture analysis."""

from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from nomi.storage.models import DependencyEdge
from nomi.storage.sqlite.graph_store import GraphStore


@dataclass
class ModuleNode:
    """Represents a module in the module-level graph."""

    name: str
    path: str
    unit_ids: Set[str] = field(default_factory=set)
    outgoing: Set[str] = field(default_factory=set)
    incoming: Set[str] = field(default_factory=set)


class ModuleGraph:
    """Module-level dependency graph for analyzing architecture."""

    def __init__(self) -> None:
        self.modules: Dict[str, ModuleNode] = {}
        self._module_by_unit: Dict[str, str] = {}

    @classmethod
    def build_from_dependency_graph(cls, graph_store: GraphStore) -> "ModuleGraph":
        """Build module graph from dependency graph.

        Args:
            graph_store: The graph store containing dependency edges

        Returns:
            ModuleGraph with module-level dependencies
        """
        module_graph = cls()
        all_edges = graph_store.get_all_edges()

        module_graph._build_module_index(all_edges)
        module_graph._build_module_dependencies(all_edges)

        return module_graph

    def _build_module_index(self, edges: List[DependencyEdge]) -> None:
        """Build index mapping units to their modules."""
        unit_ids: Set[str] = set()

        for edge in edges:
            unit_ids.add(edge.source_id)
            unit_ids.add(edge.target_id)

        for unit_id in unit_ids:
            module_path = self._extract_module_path(unit_id)
            self._module_by_unit[unit_id] = module_path

            if module_path not in self.modules:
                self.modules[module_path] = ModuleNode(
                    name=Path(module_path).name or module_path,
                    path=module_path,
                )

            self.modules[module_path].unit_ids.add(unit_id)

    def _build_module_dependencies(self, edges: List[DependencyEdge]) -> None:
        """Build inter-module dependencies from unit-level edges."""
        for edge in edges:
            source_module = self._module_by_unit.get(edge.source_id)
            target_module = self._module_by_unit.get(edge.target_id)

            if source_module and target_module and source_module != target_module:
                self.modules[source_module].outgoing.add(target_module)
                self.modules[target_module].incoming.add(source_module)

    def _extract_module_path(self, unit_id: str) -> str:
        """Extract module path from unit ID."""
        if ":" in unit_id:
            file_path = unit_id.rsplit(":", 1)[0]
        else:
            file_path = unit_id

        path = Path(file_path)

        if path.name == "__init__.py":
            return str(path.parent)

        if path.suffix in (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs"):
            return str(path.parent)

        return str(path.parent) if path.parent != Path(".") else "."

    def get_module_dependencies(self, module_name: str) -> List[str]:
        """Get modules that this module imports/depends on.

        Args:
            module_name: Name or path of the module

        Returns:
            List of module names this module depends on
        """
        module = self._find_module(module_name)
        if module:
            return sorted(list(module.outgoing))
        return []

    def get_module_dependents(self, module_name: str) -> List[str]:
        """Get modules that import/depend on this module.

        Args:
            module_name: Name or path of the module

        Returns:
            List of module names that depend on this module
        """
        module = self._find_module(module_name)
        if module:
            return sorted(list(module.incoming))
        return []

    def _find_module(self, module_name: str) -> Optional[ModuleNode]:
        """Find a module by name or path."""
        if module_name in self.modules:
            return self.modules[module_name]

        for module in self.modules.values():
            if module.name == module_name:
                return module

        return None

    def detect_cycles(self) -> List[List[str]]:
        """Detect circular dependencies between modules.

        Returns:
            List of cycles, where each cycle is a list of module paths
        """
        cycles: List[List[str]] = []
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def dfs(node: str, path: List[str]) -> None:
            visited.add(node)
            rec_stack.add(node)

            if node in self.modules:
                for neighbor in self.modules[node].outgoing:
                    if neighbor not in visited:
                        dfs(neighbor, path + [neighbor])
                    elif neighbor in rec_stack:
                        cycle_start = path.index(neighbor)
                        cycle = path[cycle_start:] + [neighbor]
                        normalized = self._normalize_cycle(cycle)
                        if normalized not in [self._normalize_cycle(c) for c in cycles]:
                            cycles.append(cycle)

            rec_stack.remove(node)

        for module_path in self.modules:
            if module_path not in visited:
                dfs(module_path, [module_path])

        return cycles

    def _normalize_cycle(self, cycle: List[str]) -> Tuple[str, ...]:
        """Normalize a cycle for deduplication."""
        if not cycle:
            return tuple()

        min_idx = 0
        min_val = cycle[0]
        for i, val in enumerate(cycle[:-1]):
            if val < min_val:
                min_val = val
                min_idx = i

        return tuple(cycle[min_idx:-1] + cycle[:min_idx] + [cycle[min_idx]])

    def get_architecture_layers(self) -> List[List[str]]:
        """Detect architecture layers (core, utils, features).

        Returns:
            List of layers, where each layer is a list of module paths
        """
        in_degree: Dict[str, int] = {path: len(module.incoming) for path, module in self.modules.items()}

        zero_in_degree = deque([path for path, degree in in_degree.items() if degree == 0])

        layers: List[List[str]] = []
        processed: Set[str] = set()

        while zero_in_degree:
            current_layer: List[str] = []
            next_layer_candidates: List[str] = []

            while zero_in_degree:
                module_path = zero_in_degree.popleft()
                if module_path not in processed:
                    current_layer.append(module_path)
                    processed.add(module_path)

                    if module_path in self.modules:
                        for neighbor in self.modules[module_path].outgoing:
                            in_degree[neighbor] -= 1
                            if in_degree[neighbor] == 0:
                                next_layer_candidates.append(neighbor)

            if current_layer:
                layers.append(sorted(current_layer))

            for candidate in next_layer_candidates:
                if candidate not in processed and in_degree[candidate] == 0:
                    zero_in_degree.append(candidate)

        remaining = set(self.modules.keys()) - processed
        if remaining:
            layers.append(sorted(list(remaining)))

        return layers

    def calculate_module_centrality(self) -> Dict[str, float]:
        """Calculate PageRank centrality for modules.

        Returns:
            Dictionary mapping module paths to centrality scores
        """
        if not self.modules:
            return {}

        damping = 0.85
        iterations = 100
        tolerance = 1e-8

        module_paths = list(self.modules.keys())
        n = len(module_paths)

        scores: Dict[str, float] = {path: 1.0 / n for path in module_paths}

        for _ in range(iterations):
            new_scores: Dict[str, float] = {}
            max_change = 0.0

            for module_path in module_paths:
                rank = (1.0 - damping) / n

                for other_path in module_paths:
                    other = self.modules[other_path]
                    if module_path in other.outgoing:
                        out_degree = len(other.outgoing)
                        if out_degree > 0:
                            rank += damping * scores[other_path] / out_degree

                new_scores[module_path] = rank
                max_change = max(max_change, abs(scores[module_path] - rank))

            scores = new_scores

            if max_change < tolerance:
                break

        return scores

    def get_module_count(self) -> int:
        """Get total number of modules."""
        return len(self.modules)

    def get_dependency_count(self) -> int:
        """Get total number of inter-module dependencies."""
        count = 0
        for module in self.modules.values():
            count += len(module.outgoing)
        return count

    def get_most_connected_modules(self, n: int = 10) -> List[Tuple[str, int]]:
        """Get the most connected modules by total degree.

        Args:
            n: Number of top modules to return

        Returns:
            List of tuples (module_path, total_connections)
        """
        connections: List[Tuple[str, int]] = []

        for path, module in self.modules.items():
            total = len(module.incoming) + len(module.outgoing)
            connections.append((path, total))

        connections.sort(key=lambda x: x[1], reverse=True)
        return connections[:n]

    def get_leaf_modules(self) -> List[str]:
        """Get modules with no outgoing dependencies (leaf modules).

        Returns:
            List of module paths
        """
        return [path for path, module in self.modules.items() if not module.outgoing and module.incoming]

    def get_root_modules(self) -> List[str]:
        """Get modules with no incoming dependencies (root modules).

        Returns:
            List of module paths
        """
        return [path for path, module in self.modules.items() if not module.incoming and module.outgoing]
