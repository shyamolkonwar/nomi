"""Graph traversal algorithms for the dependency graph."""

from collections import deque
from typing import Dict, List, Optional, Set, Tuple

from nomi.storage.sqlite.graph_store import GraphStore


class GraphTraversal:
    """Graph traversal algorithms for dependency analysis."""

    def __init__(self, graph_store: GraphStore) -> None:
        self.graph_store = graph_store

    def traverse_bfs(
        self,
        start_unit_id: str,
        max_depth: int = 2,
        edge_types: Optional[List[str]] = None,
    ) -> List[str]:
        """Breadth-first traversal from a starting unit.

        Args:
            start_unit_id: The starting code unit ID
            max_depth: Maximum depth to traverse
            edge_types: Optional list of edge types to follow

        Returns:
            List of unit IDs reachable from start_unit_id
        """
        if max_depth < 0:
            return []

        visited: Set[str] = {start_unit_id}
        queue: deque[Tuple[str, int]] = deque([(start_unit_id, 0)])
        result: List[str] = [start_unit_id]

        while queue:
            current_id, current_depth = queue.popleft()

            if current_depth >= max_depth:
                continue

            try:
                edges = self.graph_store.get_edges_for_unit(current_id)
            except Exception:
                continue

            for edge in edges:
                if edge.source_id != current_id:
                    continue

                if edge_types is not None and edge.edge_type.value not in edge_types:
                    continue

                if edge.target_id not in visited:
                    visited.add(edge.target_id)
                    result.append(edge.target_id)
                    queue.append((edge.target_id, current_depth + 1))

        return result

    def traverse_dfs(
        self,
        start_unit_id: str,
        max_depth: int = 2,
        edge_types: Optional[List[str]] = None,
    ) -> List[str]:
        """Depth-first traversal from a starting unit.

        Args:
            start_unit_id: The starting code unit ID
            max_depth: Maximum depth to traverse
            edge_types: Optional list of edge types to follow

        Returns:
            List of unit IDs reachable from start_unit_id in DFS order
        """
        if max_depth < 0:
            return []

        visited: Set[str] = set()
        result: List[str] = []

        def dfs_recursive(unit_id: str, depth: int) -> None:
            if depth > max_depth or unit_id in visited:
                return

            visited.add(unit_id)
            result.append(unit_id)

            try:
                edges = self.graph_store.get_edges_for_unit(unit_id)
            except Exception:
                return

            for edge in edges:
                if edge.source_id != unit_id:
                    continue

                if edge_types is not None and edge.edge_type.value not in edge_types:
                    continue

                dfs_recursive(edge.target_id, depth + 1)

        dfs_recursive(start_unit_id, 0)
        return result

    def find_shortest_path(self, from_unit_id: str, to_unit_id: str) -> Optional[List[str]]:
        """Find the shortest path between two units using BFS.

        Args:
            from_unit_id: Starting unit ID
            to_unit_id: Target unit ID

        Returns:
            List of unit IDs representing the path, or None if no path exists
        """
        if from_unit_id == to_unit_id:
            return [from_unit_id]

        visited: Set[str] = {from_unit_id}
        queue: deque[Tuple[str, List[str]]] = deque([(from_unit_id, [from_unit_id])])

        while queue:
            current_id, path = queue.popleft()

            try:
                edges = self.graph_store.get_edges_for_unit(current_id)
            except Exception:
                continue

            for edge in edges:
                if edge.source_id != current_id:
                    continue

                next_id = edge.target_id

                if next_id == to_unit_id:
                    return path + [next_id]

                if next_id not in visited:
                    visited.add(next_id)
                    queue.append((next_id, path + [next_id]))

        return None

    def find_cycles(self) -> List[List[str]]:
        """Detect all cycles in the dependency graph.

        Returns:
            List of cycles, where each cycle is a list of unit IDs
        """
        cycles: List[List[str]] = []
        all_edges = self.graph_store.get_all_edges()

        graph: Dict[str, Set[str]] = {}
        for edge in all_edges:
            if edge.source_id not in graph:
                graph[edge.source_id] = set()
            graph[edge.source_id].add(edge.target_id)

        def find_cycles_from_node(start: str, current: str, path: List[str], visited: Set[str]) -> None:
            if current in path:
                cycle_start = path.index(current)
                cycle = path[cycle_start:] + [current]
                normalized = self._normalize_cycle(cycle)
                if normalized not in [self._normalize_cycle(c) for c in cycles]:
                    cycles.append(cycle)
                return

            if current in visited:
                return

            visited.add(current)

            if current in graph:
                for neighbor in graph[current]:
                    find_cycles_from_node(start, neighbor, path + [current], visited)

        visited_global: Set[str] = set()
        for node in graph:
            if node not in visited_global:
                find_cycles_from_node(node, node, [], set())
                visited_global.add(node)

        return cycles

    def _normalize_cycle(self, cycle: List[str]) -> Tuple[str, ...]:
        """Normalize a cycle for deduplication by rotating to start with minimum element."""
        if not cycle:
            return tuple()
        min_idx = cycle.index(min(cycle[:-1]))
        return tuple(cycle[min_idx:-1] + cycle[:min_idx] + [cycle[min_idx]])

    def get_connected_components(self) -> List[Set[str]]:
        """Find all connected components in the graph.

        Returns:
            List of sets, where each set contains unit IDs in a component
        """
        all_edges = self.graph_store.get_all_edges()

        graph: Dict[str, Set[str]] = {}
        nodes: Set[str] = set()

        for edge in all_edges:
            nodes.add(edge.source_id)
            nodes.add(edge.target_id)
            if edge.source_id not in graph:
                graph[edge.source_id] = set()
            if edge.target_id not in graph:
                graph[edge.target_id] = set()
            graph[edge.source_id].add(edge.target_id)
            graph[edge.target_id].add(edge.source_id)

        visited: Set[str] = set()
        components: List[Set[str]] = []

        def bfs_component(start: str) -> Set[str]:
            component: Set[str] = set()
            queue: deque[str] = deque([start])

            while queue:
                node = queue.popleft()
                if node in visited:
                    continue
                visited.add(node)
                component.add(node)

                if node in graph:
                    for neighbor in graph[node]:
                        if neighbor not in visited:
                            queue.append(neighbor)

            return component

        for node in nodes:
            if node not in visited:
                components.append(bfs_component(node))

        return components

    def calculate_centrality(self) -> Dict[str, float]:
        """Calculate PageRank-like centrality for all nodes.

        Returns:
            Dictionary mapping unit IDs to their centrality scores
        """
        all_edges = self.graph_store.get_all_edges()

        graph: Dict[str, Set[str]] = {}
        nodes: Set[str] = set()

        for edge in all_edges:
            nodes.add(edge.source_id)
            nodes.add(edge.target_id)
            if edge.source_id not in graph:
                graph[edge.source_id] = set()
            graph[edge.source_id].add(edge.target_id)

        if not nodes:
            return {}

        damping = 0.85
        iterations = 100
        tolerance = 1e-8

        scores: Dict[str, float] = {node: 1.0 / len(nodes) for node in nodes}

        for _ in range(iterations):
            new_scores: Dict[str, float] = {}
            max_change = 0.0

            for node in nodes:
                rank = (1.0 - damping) / len(nodes)

                for other in nodes:
                    if node in graph.get(other, set()):
                        out_degree = len(graph.get(other, set()))
                        if out_degree > 0:
                            rank += damping * scores[other] / out_degree

                new_scores[node] = rank
                max_change = max(max_change, abs(scores[node] - rank))

            scores = new_scores

            if max_change < tolerance:
                break

        return scores
