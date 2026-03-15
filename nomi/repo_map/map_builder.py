"""Repository map builder for generating compact codebase overviews."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from nomi.core.graph.traversal import GraphTraversal
from nomi.storage.models import UnitKind
from nomi.storage.sqlite.symbol_store import SymbolStore


@dataclass
class MapEntry:
    """Represents a single symbol entry in the repository map."""

    symbol_name: str
    unit_id: str
    unit_kind: str
    file_path: str
    line_number: int
    importance_score: float
    is_exported: bool = False


@dataclass
class ModuleSummary:
    """Summary of a module/directory in the repository."""

    name: str
    path: str
    symbols: List[MapEntry] = field(default_factory=list)
    symbol_count: int = 0
    importance_score: float = 0.0


@dataclass
class RepositoryMap:
    """Complete repository map with important symbols and module structure."""

    modules: List[ModuleSummary] = field(default_factory=list)
    total_modules: int = 0
    total_symbols: int = 0
    top_level_symbols: List[MapEntry] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)
    token_estimate: int = 0


class RepoMapBuilder:
    """Builds a compact repository map using PageRank-based importance scores."""

    def __init__(self, graph_traversal: GraphTraversal, symbol_store: SymbolStore) -> None:
        self.graph_traversal = graph_traversal
        self.symbol_store = symbol_store
        self._importance_cache: Optional[Dict[str, float]] = None
        self._cache_timestamp: Optional[datetime] = None

    def build_map(self, max_entries: int = 100, max_symbols_per_module: int = 10) -> RepositoryMap:
        """Build a repository map with top important symbols.

        Args:
            max_entries: Maximum total symbols to include
            max_symbols_per_module: Maximum symbols per module

        Returns:
            RepositoryMap containing the compact overview
        """
        all_unit_ids = self._get_all_unit_ids()
        importance_scores = self.calculate_importance_scores()

        sorted_units = sorted(
            all_unit_ids,
            key=lambda uid: importance_scores.get(uid, 0.0),
            reverse=True,
        )

        modules_by_path = self._group_by_module(sorted_units)
        module_importance = self._calculate_module_importance(modules_by_path, importance_scores)

        sorted_modules = sorted(
            modules_by_path.keys(),
            key=lambda m: module_importance.get(m, 0.0),
            reverse=True,
        )

        repo_map = RepositoryMap()
        repo_map.total_modules = len(modules_by_path)
        repo_map.total_symbols = len(all_unit_ids)
        repo_map.generated_at = datetime.now()

        entry_count = 0
        top_level_symbols: List[MapEntry] = []

        for module_path in sorted_modules:
            if entry_count >= max_entries:
                break

            unit_ids = modules_by_path[module_path]
            sorted_module_units = sorted(
                unit_ids,
                key=lambda uid: importance_scores.get(uid, 0.0),
                reverse=True,
            )

            symbols_in_module: List[MapEntry] = []
            for unit_id in sorted_module_units[:max_symbols_per_module]:
                if entry_count >= max_entries:
                    break

                entry = self._create_map_entry(unit_id, importance_scores)
                if entry:
                    symbols_in_module.append(entry)
                    entry_count += 1

                    if len(top_level_symbols) < 20:
                        top_level_symbols.append(entry)

            if symbols_in_module:
                module_summary = ModuleSummary(
                    name=Path(module_path).name or module_path,
                    path=module_path,
                    symbols=symbols_in_module,
                    symbol_count=len(unit_ids),
                    importance_score=module_importance.get(module_path, 0.0),
                )
                repo_map.modules.append(module_summary)

        repo_map.top_level_symbols = top_level_symbols
        repo_map.token_estimate = self._estimate_tokens(repo_map)

        return repo_map

    def build_module_map(self) -> Dict[str, List[MapEntry]]:
        """Build a map of modules to their symbols.

        Returns:
            Dictionary mapping module paths to lists of MapEntry objects
        """
        all_unit_ids = self._get_all_unit_ids()
        importance_scores = self.calculate_importance_scores()
        modules_by_path = self._group_by_module(all_unit_ids)

        result: Dict[str, List[MapEntry]] = {}
        for module_path, unit_ids in modules_by_path.items():
            entries: List[MapEntry] = []
            for unit_id in unit_ids:
                entry = self._create_map_entry(unit_id, importance_scores)
                if entry:
                    entries.append(entry)

            entries.sort(key=lambda e: e.importance_score, reverse=True)
            result[module_path] = entries

        return result

    def calculate_importance_scores(self) -> Dict[str, float]:
        """Calculate PageRank-based importance scores for all symbols.

        Returns:
            Dictionary mapping unit IDs to importance scores
        """
        if self._importance_cache is not None:
            cache_age = datetime.now() - (self._cache_timestamp or datetime.now())
            if cache_age.total_seconds() < 300:
                return self._importance_cache

        centrality_scores = self.graph_traversal.calculate_centrality()

        adjusted_scores: Dict[str, float] = {}
        for unit_id, score in centrality_scores.items():
            adjusted_scores[unit_id] = self._boost_symbol_score(unit_id, score)

        self._importance_cache = adjusted_scores
        self._cache_timestamp = datetime.now()

        return adjusted_scores

    def _group_by_module(self, unit_ids: List[str]) -> Dict[str, List[str]]:
        """Group unit IDs by their module/directory.

        Args:
            unit_ids: List of unit IDs to group

        Returns:
            Dictionary mapping module paths to lists of unit IDs
        """
        modules: Dict[str, List[str]] = {}

        for unit_id in unit_ids:
            module_path = self._extract_module_path(unit_id)
            if module_path not in modules:
                modules[module_path] = []
            modules[module_path].append(unit_id)

        return modules

    def _extract_module_path(self, unit_id: str) -> str:
        """Extract module/directory path from unit ID.

        Unit ID format: repo_path/file:symbol_name
        """
        if ":" in unit_id:
            file_path = unit_id.rsplit(":", 1)[0]
        else:
            file_path = unit_id

        path = Path(file_path)
        return str(path.parent) if path.parent != Path(".") else "."

    def _extract_symbol_name(self, unit_id: str) -> str:
        """Extract symbol name from unit ID."""
        if ":" in unit_id:
            return unit_id.rsplit(":", 1)[-1]
        return Path(unit_id).stem

    def _get_all_unit_ids(self) -> List[str]:
        """Get all unit IDs from the symbol store."""
        try:
            all_symbols = self.symbol_store.get_all_symbols()
            unit_ids: List[str] = []

            for symbol_name in all_symbols:
                units = self.symbol_store.search_symbols(symbol_name)
                for unit in units:
                    unit_ids.append(unit.id)

            return list(set(unit_ids))
        except Exception:
            return []

    def _create_map_entry(self, unit_id: str, importance_scores: Dict[str, float]) -> Optional[MapEntry]:
        """Create a MapEntry from a unit ID."""
        try:
            code_unit = self.symbol_store.get_code_unit_by_id(unit_id)
            if not code_unit:
                return None

            symbol_name = self._extract_symbol_name(unit_id)

            is_exported = self._is_exported_symbol(code_unit, symbol_name)

            return MapEntry(
                symbol_name=symbol_name,
                unit_id=unit_id,
                unit_kind=code_unit.unit_kind.value,
                file_path=code_unit.file_path,
                line_number=code_unit.line_range[0],
                importance_score=importance_scores.get(unit_id, 0.0),
                is_exported=is_exported,
            )
        except Exception:
            return None

    def _is_exported_symbol(self, code_unit, symbol_name: str) -> bool:
        """Determine if a symbol is exported/public."""
        file_path = code_unit.file_path

        if file_path.endswith(".py"):
            return not symbol_name.startswith("_")

        if file_path.endswith((".ts", ".tsx", ".js", ".jsx")):
            return "export" in (code_unit.signature or "")

        if file_path.endswith(".go"):
            first_char = symbol_name[0] if symbol_name else ""
            return first_char.isupper()

        return True

    def _boost_symbol_score(self, unit_id: str, base_score: float) -> float:
        """Boost importance score based on symbol characteristics."""
        boosted = base_score

        code_unit = self.symbol_store.get_code_unit_by_id(unit_id)
        if not code_unit:
            return boosted

        dependents = self.graph_traversal.graph_store.get_dependents(unit_id)
        if len(dependents) > 10:
            boosted *= 1.5
        elif len(dependents) > 5:
            boosted *= 1.3
        elif len(dependents) > 0:
            boosted *= 1.1

        if code_unit.docstring:
            boosted *= 1.1

        if code_unit.unit_kind == UnitKind.CLASS:
            boosted *= 1.2

        return boosted

    def _calculate_module_importance(
        self,
        modules_by_path: Dict[str, List[str]],
        importance_scores: Dict[str, float],
    ) -> Dict[str, float]:
        """Calculate aggregated importance score for each module."""
        module_scores: Dict[str, float] = {}

        for module_path, unit_ids in modules_by_path.items():
            total_score = sum(importance_scores.get(uid, 0.0) for uid in unit_ids)
            module_scores[module_path] = total_score / max(len(unit_ids), 1)

        return module_scores

    def _estimate_tokens(self, repo_map: RepositoryMap) -> int:
        """Estimate token count for the repository map."""
        total_chars = 0

        for module in repo_map.modules:
            total_chars += len(module.name) + len(module.path) + 50
            for symbol in module.symbols:
                total_chars += len(symbol.symbol_name) + len(symbol.unit_kind) + 30

        for symbol in repo_map.top_level_symbols:
            total_chars += len(symbol.symbol_name) + len(symbol.unit_kind) + 30

        return total_chars // 4

    def invalidate_cache(self) -> None:
        """Invalidate the importance scores cache."""
        self._importance_cache = None
        self._cache_timestamp = None
