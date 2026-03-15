"""Tests for repository map generation."""

import pytest
from datetime import datetime
from unittest.mock import Mock

from nomi.repo_map.map_builder import (
    MapEntry,
    ModuleSummary,
    RepoMapBuilder,
    RepositoryMap,
)
from nomi.repo_map.module_graph import ModuleGraph, ModuleNode
from nomi.storage.models import UnitKind, DependencyEdge, EdgeType


class TestMapEntry:
    """Test MapEntry dataclass."""

    def test_map_entry_creation(self):
        """Test creating a MapEntry."""
        entry = MapEntry(
            symbol_name="test_function",
            unit_id="test.py:test_function",
            unit_kind="FUNCTION",
            file_path="/test.py",
            line_number=10,
            importance_score=0.85,
            is_exported=True,
        )

        assert entry.symbol_name == "test_function"
        assert entry.unit_id == "test.py:test_function"
        assert entry.unit_kind == "FUNCTION"
        assert entry.importance_score == 0.85
        assert entry.is_exported is True


class TestModuleSummary:
    """Test ModuleSummary dataclass."""

    def test_module_summary_creation(self):
        """Test creating a ModuleSummary."""
        entry = MapEntry(
            symbol_name="test_function",
            unit_id="test.py:test_function",
            unit_kind="FUNCTION",
            file_path="/test.py",
            line_number=10,
            importance_score=0.85,
            is_exported=True,
        )

        summary = ModuleSummary(
            name="test_module",
            path="/path/to/test_module",
            symbols=[entry],
            symbol_count=1,
            importance_score=0.9,
        )

        assert summary.name == "test_module"
        assert summary.symbol_count == 1
        assert len(summary.symbols) == 1


class TestRepositoryMap:
    """Test RepositoryMap dataclass."""

    def test_repository_map_creation(self):
        """Test creating a RepositoryMap."""
        repo_map = RepositoryMap(
            modules=[],
            total_modules=5,
            total_symbols=100,
            top_level_symbols=[],
            generated_at=datetime.now(),
            token_estimate=1500,
        )

        assert repo_map.total_modules == 5
        assert repo_map.total_symbols == 100
        assert repo_map.token_estimate == 1500


class TestRepoMapBuilder:
    """Test RepoMapBuilder functionality."""

    @pytest.fixture
    def mock_graph_traversal(self):
        """Create a mock GraphTraversal."""
        mock = Mock()
        mock.calculate_centrality.return_value = {
            "test.py:func1": 0.9,
            "test.py:func2": 0.5,
        }
        mock.graph_store = Mock()
        mock.graph_store.get_dependents.return_value = []
        return mock

    @pytest.fixture
    def mock_symbol_store(self):
        """Create a mock SymbolStore."""
        mock = Mock()
        mock.get_all_symbols.return_value = ["func1", "func2"]

        code_unit1 = Mock()
        code_unit1.id = "test.py:func1"
        code_unit1.unit_kind = UnitKind.FUNCTION
        code_unit1.file_path = "/test.py"
        code_unit1.line_range = (10, 20)
        code_unit1.docstring = None

        code_unit2 = Mock()
        code_unit2.id = "test.py:func2"
        code_unit2.unit_kind = UnitKind.FUNCTION
        code_unit2.file_path = "/test.py"
        code_unit2.line_range = (30, 40)
        code_unit2.docstring = "Documentation"

        mock.search_symbols.side_effect = lambda name: {
            "func1": [code_unit1],
            "func2": [code_unit2],
        }.get(name, [])

        mock.get_code_unit_by_id.side_effect = lambda uid: {
            "test.py:func1": code_unit1,
            "test.py:func2": code_unit2,
        }.get(uid)

        return mock

    def test_build_map(self, mock_graph_traversal, mock_symbol_store):
        """Test building a repository map."""
        builder = RepoMapBuilder(mock_graph_traversal, mock_symbol_store)
        repo_map = builder.build_map(max_entries=10)

        assert isinstance(repo_map, RepositoryMap)
        assert repo_map.total_symbols == 2
        assert len(repo_map.modules) > 0
        assert repo_map.generated_at is not None
        assert repo_map.token_estimate > 0

    def test_calculate_importance_scores(self, mock_graph_traversal, mock_symbol_store):
        """Test importance score calculation."""
        builder = RepoMapBuilder(mock_graph_traversal, mock_symbol_store)
        scores = builder.calculate_importance_scores()

        assert "test.py:func1" in scores
        assert "test.py:func2" in scores
        assert scores["test.py:func1"] > scores["test.py:func2"]

    def test_group_by_module(self, mock_graph_traversal, mock_symbol_store):
        """Test grouping units by module."""
        builder = RepoMapBuilder(mock_graph_traversal, mock_symbol_store)
        unit_ids = ["test.py:func1", "test.py:func2"]
        grouped = builder._group_by_module(unit_ids)

        assert "/" in grouped or "." in grouped

    def test_cache_functionality(self, mock_graph_traversal, mock_symbol_store):
        """Test that importance scores are cached."""
        builder = RepoMapBuilder(mock_graph_traversal, mock_symbol_store)

        scores1 = builder.calculate_importance_scores()
        scores2 = builder.calculate_importance_scores()

        assert scores1 == scores2
        mock_graph_traversal.calculate_centrality.assert_called_once()

    def test_invalidate_cache(self, mock_graph_traversal, mock_symbol_store):
        """Test cache invalidation."""
        builder = RepoMapBuilder(mock_graph_traversal, mock_symbol_store)

        builder.calculate_importance_scores()
        builder.invalidate_cache()

        builder.calculate_importance_scores()
        assert mock_graph_traversal.calculate_centrality.call_count == 2


class TestModuleGraph:
    """Test ModuleGraph functionality."""

    @pytest.fixture
    def sample_edges(self):
        """Create sample dependency edges."""
        return [
            DependencyEdge(
                source_id="module_a/file1.py:func1",
                target_id="module_b/file2.py:func2",
                edge_type=EdgeType.CALLS,
            ),
            DependencyEdge(
                source_id="module_b/file2.py:func2",
                target_id="module_c/file3.py:func3",
                edge_type=EdgeType.CALLS,
            ),
        ]

    @pytest.fixture
    def mock_graph_store(self, sample_edges):
        """Create a mock GraphStore."""
        mock = Mock()
        mock.get_all_edges.return_value = sample_edges
        return mock

    def test_build_from_dependency_graph(self, mock_graph_store):
        """Test building module graph from dependency graph."""
        module_graph = ModuleGraph.build_from_dependency_graph(mock_graph_store)

        assert isinstance(module_graph, ModuleGraph)
        assert module_graph.get_module_count() > 0

    def test_get_module_dependencies(self, mock_graph_store):
        """Test getting module dependencies."""
        module_graph = ModuleGraph.build_from_dependency_graph(mock_graph_store)

        deps = module_graph.get_module_dependencies("module_a")
        assert isinstance(deps, list)

    def test_get_module_dependents(self, mock_graph_store):
        """Test getting module dependents."""
        module_graph = ModuleGraph.build_from_dependency_graph(mock_graph_store)

        dependents = module_graph.get_module_dependents("module_b")
        assert isinstance(dependents, list)

    def test_detect_cycles_no_cycles(self, mock_graph_store):
        """Test cycle detection with no cycles."""
        module_graph = ModuleGraph.build_from_dependency_graph(mock_graph_store)
        cycles = module_graph.detect_cycles()

        assert isinstance(cycles, list)

    def test_detect_cycles_with_cycle(self):
        """Test cycle detection with a cycle."""
        edges = [
            DependencyEdge(
                source_id="module_a/file1.py:func1",
                target_id="module_b/file2.py:func2",
                edge_type=EdgeType.CALLS,
            ),
            DependencyEdge(
                source_id="module_b/file2.py:func2",
                target_id="module_a/file1.py:func1",
                edge_type=EdgeType.CALLS,
            ),
        ]

        mock_store = Mock()
        mock_store.get_all_edges.return_value = edges

        module_graph = ModuleGraph.build_from_dependency_graph(mock_store)
        cycles = module_graph.detect_cycles()

        assert len(cycles) > 0

    def test_get_architecture_layers(self, mock_graph_store):
        """Test architecture layer detection."""
        module_graph = ModuleGraph.build_from_dependency_graph(mock_graph_store)
        layers = module_graph.get_architecture_layers()

        assert isinstance(layers, list)
        assert len(layers) > 0

    def test_calculate_module_centrality(self, mock_graph_store):
        """Test module centrality calculation."""
        module_graph = ModuleGraph.build_from_dependency_graph(mock_graph_store)
        centrality = module_graph.calculate_module_centrality()

        assert isinstance(centrality, dict)
        assert len(centrality) > 0

        # Check that all scores are positive and within reasonable bounds
        for score in centrality.values():
            assert score >= 0
            assert score <= 1

    def test_get_most_connected_modules(self, mock_graph_store):
        """Test getting most connected modules."""
        module_graph = ModuleGraph.build_from_dependency_graph(mock_graph_store)
        connected = module_graph.get_most_connected_modules(n=2)

        assert isinstance(connected, list)
        assert len(connected) <= 2

    def test_get_leaf_modules(self, mock_graph_store):
        """Test getting leaf modules."""
        module_graph = ModuleGraph.build_from_dependency_graph(mock_graph_store)
        leaves = module_graph.get_leaf_modules()

        assert isinstance(leaves, list)

    def test_get_root_modules(self, mock_graph_store):
        """Test getting root modules."""
        module_graph = ModuleGraph.build_from_dependency_graph(mock_graph_store)
        roots = module_graph.get_root_modules()

        assert isinstance(roots, list)

    def test_module_node_creation(self):
        """Test ModuleNode dataclass."""
        node = ModuleNode(
            name="test_module",
            path="/path/to/test",
            unit_ids={"unit1", "unit2"},
            outgoing={"other1"},
            incoming={"other2"},
        )

        assert node.name == "test_module"
        assert len(node.unit_ids) == 2
        assert "other1" in node.outgoing
        assert "other2" in node.incoming
