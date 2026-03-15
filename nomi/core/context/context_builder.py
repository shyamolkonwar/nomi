"""Context builder engine for Nomi.

This module provides the main context assembly logic, implementing the
5-stage retrieval pipeline for building context bundles.
"""

import logging
import time
from dataclasses import dataclass
from typing import List, Optional, Set

from nomi.core.context.context_bundle import (
    CodeUnitSkeleton,
    ContextBundle,
    ContextMetadata,
    RepositoryMap,
)
from nomi.core.context.resolver import ContextResolver
from nomi.core.graph.dependency_graph import DependencyGraph
from nomi.core.index.lookup import SymbolLookup
from nomi.core.index.search import SymbolSearch
from nomi.storage.models import CodeUnit

logger = logging.getLogger(__name__)


@dataclass
class BuildConfig:
    """Configuration for context bundle building.

    Controls dependency expansion depth, token budgets, and feature flags.

    Attributes:
        dependency_depth: How many hops to follow in dependency graph (default: 1).
        max_context_tokens: Maximum estimated tokens for the bundle (default: 4000).
        include_repo_map: Whether to include repository structure (default: True).
        skeletonize_dependencies: Whether to remove bodies from non-focal units (default: True).
        prioritize_same_file: Whether to boost same-file dependencies (default: True).
    """

    dependency_depth: int = 1
    max_context_tokens: int = 4000
    include_repo_map: bool = True
    skeletonize_dependencies: bool = True
    prioritize_same_file: bool = True


class ContextBuilder:
    """Builds context bundles for AI coding agents.

    Implements the 5-stage retrieval pipeline:
    1. Query resolution: Parse and resolve symbols from query
    2. Focal unit retrieval: Get full CodeUnits for resolved symbols
    3. Dependency expansion: Follow dependency graph with depth limiting
    4. Skeleton creation: Create lightweight skeletons for non-focal units
    5. Bundle assembly: Combine all components into ContextBundle

    Attributes:
        symbol_search: Fuzzy search for symbol discovery.
        dependency_graph: Graph for dependency traversal.
        config: Build configuration options.
        resolver: Query resolution helper.
    """

    # Estimated tokens per character (conservative estimate)
    TOKENS_PER_CHAR = 0.25

    def __init__(
        self,
        symbol_search: SymbolSearch,
        dependency_graph: DependencyGraph,
        symbol_lookup: SymbolLookup,
        config: Optional[BuildConfig] = None,
    ) -> None:
        """Initialize the context builder.

        Args:
            symbol_search: The SymbolSearch instance for fuzzy matching.
            dependency_graph: The DependencyGraph for dependency traversal.
            symbol_lookup: The SymbolLookup instance for exact lookups.
            config: Optional build configuration (uses defaults if not provided).
        """
        self.symbol_search = symbol_search
        self.dependency_graph = dependency_graph
        self.symbol_lookup = symbol_lookup
        self.config = config or BuildConfig()
        self.resolver = ContextResolver(symbol_search, symbol_lookup)

    def build(self, query: str) -> ContextBundle:
        """Build a context bundle from a developer query.

        Executes the 5-stage retrieval pipeline:
        Stage 1: Resolve symbols from query
        Stage 2: Get focal units
        Stage 3: Expand dependencies (with depth limit)
        Stage 4: Create skeletons for non-focal units
        Stage 5: Assemble bundle

        Args:
            query: The developer's natural language query.

        Returns:
            Assembled ContextBundle with all relevant context.
        """
        start_time = time.time()

        logger.info(f"Building context bundle for query: {query}")

        # Stage 1: Resolve symbols from query
        focal_units = self.resolver.resolve_from_query(query)

        if not focal_units:
            logger.warning(f"No focal units found for query: {query}")
            return self._create_empty_bundle(query, start_time)

        logger.debug(f"Resolved {len(focal_units)} focal units")

        # Stage 2 & 3: Get dependencies with depth limiting
        dependency_units = self._expand_dependencies(focal_units)
        logger.debug(f"Expanded to {len(dependency_units)} dependency units")

        # Stage 4: Create skeletons for non-focal dependencies
        focal_ids = {unit.id for unit in focal_units}
        non_focal_deps = [u for u in dependency_units if u.id not in focal_ids]

        if self.config.skeletonize_dependencies:
            skeletons = self._create_skeletons(non_focal_deps)
        else:
            # Include full units if skeletonization disabled
            skeletons = [
                CodeUnitSkeleton(
                    id=unit.id,
                    unit_kind=unit.unit_kind.value,
                    signature=unit.signature,
                    file_path=unit.file_path,
                    line_range=unit.line_range,
                    docstring=unit.docstring,
                )
                for unit in non_focal_deps
            ]

        logger.debug(f"Created {len(skeletons)} dependency skeletons")

        # Stage 5: Assemble bundle
        bundle = self._assemble_bundle(
            query=query,
            focal_units=focal_units,
            skeletons=skeletons,
            start_time=start_time,
        )

        logger.info(
            "Context bundle built successfully",
            extra={
                "focal_count": len(focal_units),
                "dependency_count": len(skeletons),
                "total_tokens": bundle.metadata.total_tokens,
                "duration_ms": bundle.metadata.search_duration_ms,
            },
        )

        return bundle

    def build_for_symbol(self, symbol_name: str) -> ContextBundle:
        """Build a context bundle for a specific symbol.

        Args:
            symbol_name: The exact symbol name to build context for.

        Returns:
            Assembled ContextBundle centered on the specified symbol.
        """
        start_time = time.time()

        logger.info(f"Building context bundle for symbol: {symbol_name}")

        # Resolve the symbol
        unit = self.resolver.resolve_from_symbol_name(symbol_name)

        if not unit:
            logger.warning(f"Symbol not found: {symbol_name}")
            return self._create_empty_bundle(f"symbol:{symbol_name}", start_time)

        focal_units = [unit]

        # Expand dependencies
        dependency_units = self._expand_dependencies(focal_units)

        # Create skeletons
        focal_ids = {unit.id for unit in focal_units}
        non_focal_deps = [u for u in dependency_units if u.id not in focal_ids]

        if self.config.skeletonize_dependencies:
            skeletons = self._create_skeletons(non_focal_deps)
        else:
            skeletons = [
                CodeUnitSkeleton(
                    id=unit.id,
                    unit_kind=unit.unit_kind.value,
                    signature=unit.signature,
                    file_path=unit.file_path,
                    line_range=unit.line_range,
                    docstring=unit.docstring,
                )
                for unit in non_focal_deps
            ]

        # Assemble bundle
        return self._assemble_bundle(
            query=f"symbol:{symbol_name}",
            focal_units=focal_units,
            skeletons=skeletons,
            start_time=start_time,
        )

    def build_for_file(
        self,
        file_path: str,
        focal_symbol: Optional[str] = None,
    ) -> ContextBundle:
        """Build a context bundle for a specific file.

        Args:
            file_path: Absolute path to the source file.
            focal_symbol: Optional specific symbol to focus on within the file.

        Returns:
            Assembled ContextBundle for the file.
        """
        start_time = time.time()

        logger.info(f"Building context bundle for file: {file_path}")

        # Get all symbols in the file
        file_units = self.resolver.resolve_from_file_path(file_path)

        if not file_units:
            logger.warning(f"No symbols found in file: {file_path}")
            return self._create_empty_bundle(f"file:{file_path}", start_time)

        # Determine focal units
        if focal_symbol:
            focal_units = [unit for unit in file_units if self._extract_symbol_name(unit.id) == focal_symbol]
            if not focal_units:
                focal_units = [file_units[0]]  # Default to first unit
        else:
            # All units in file are focal
            focal_units = file_units

        # Expand dependencies
        dependency_units = self._expand_dependencies(focal_units)

        # Create skeletons
        focal_ids = {unit.id for unit in focal_units}
        non_focal_deps = [u for u in dependency_units if u.id not in focal_ids]

        if self.config.skeletonize_dependencies:
            skeletons = self._create_skeletons(non_focal_deps)
        else:
            skeletons = [
                CodeUnitSkeleton(
                    id=unit.id,
                    unit_kind=unit.unit_kind.value,
                    signature=unit.signature,
                    file_path=unit.file_path,
                    line_range=unit.line_range,
                    docstring=unit.docstring,
                )
                for unit in non_focal_deps
            ]

        # Assemble bundle
        return self._assemble_bundle(
            query=f"file:{file_path}" + (f"#{focal_symbol}" if focal_symbol else ""),
            focal_units=focal_units,
            skeletons=skeletons,
            start_time=start_time,
        )

    def _expand_dependencies(self, focal_units: List[CodeUnit]) -> List[CodeUnit]:
        """Expand dependencies with depth limiting.

        Args:
            focal_units: List of focal code units.

        Returns:
            List of all dependency code units within the configured depth.
        """
        all_deps: Set[str] = set()
        dep_units: List[CodeUnit] = []

        for focal in focal_units:
            # Get dependencies at configured depth
            dep_ids = self.dependency_graph.get_dependencies(
                focal.id,
                depth=self.config.dependency_depth,
            )

            for dep_id in dep_ids:
                if dep_id not in all_deps:
                    all_deps.add(dep_id)
                    # Lookup the dependency unit
                    dep_unit = self._lookup_unit_by_id(dep_id)
                    if dep_unit:
                        dep_units.append(dep_unit)

        # If prioritizing same-file dependencies, sort accordingly
        if self.config.prioritize_same_file and focal_units:
            focal_files = {unit.file_path for unit in focal_units}
            dep_units.sort(key=lambda u: (u.file_path not in focal_files, u.file_path))

        return dep_units

    def _create_skeletons(self, units: List[CodeUnit]) -> List[CodeUnitSkeleton]:
        """Create lightweight skeletons from code units.

        Removes implementation bodies to reduce token usage.

        Args:
            units: List of code units to skeletonize.

        Returns:
            List of CodeUnitSkeleton objects.
        """
        skeletons: List[CodeUnitSkeleton] = []

        for unit in units:
            skeleton = CodeUnitSkeleton(
                id=unit.id,
                unit_kind=unit.unit_kind.value,
                signature=unit.signature,
                file_path=unit.file_path,
                line_range=unit.line_range,
                docstring=unit.docstring,
            )
            skeletons.append(skeleton)

        return skeletons

    def _assemble_bundle(
        self,
        query: str,
        focal_units: List[CodeUnit],
        skeletons: List[CodeUnitSkeleton],
        start_time: float,
    ) -> ContextBundle:
        """Assemble the final context bundle.

        Args:
            query: The original query.
            focal_units: List of focal code units.
            skeletons: List of dependency skeletons.
            start_time: Timestamp when build started.

        Returns:
            Fully assembled ContextBundle.
        """
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Estimate token count
        total_tokens = self._estimate_tokens(focal_units, skeletons)

        # Create metadata
        metadata = ContextMetadata(
            created_at=__import__("datetime").datetime.now(),
            total_tokens=total_tokens,
            num_focal_units=len(focal_units),
            num_dependencies=len(skeletons),
            search_duration_ms=duration_ms,
        )

        # Create repository map if enabled
        repo_map: Optional[RepositoryMap] = None
        if self.config.include_repo_map and focal_units:
            repo_map = self._create_repository_map(focal_units, skeletons)

        return ContextBundle(
            query=query,
            focal_units=focal_units,
            dependency_skeletons=skeletons,
            repository_map=repo_map,
            metadata=metadata,
        )

    def _create_repository_map(
        self,
        focal_units: List[CodeUnit],
        skeletons: List[CodeUnitSkeleton],
    ) -> RepositoryMap:
        """Create a high-level repository structure map.

        Args:
            focal_units: List of focal code units.
            skeletons: List of dependency skeletons.

        Returns:
            RepositoryMap with structure overview.
        """
        # Collect all unique file paths
        all_files: Set[str] = set()
        for unit in focal_units:
            all_files.add(unit.file_path)
        for skeleton in skeletons:
            all_files.add(skeleton.file_path)

        # Extract modules (directories)
        modules: Set[str] = set()
        for file_path in all_files:
            parts = file_path.split("/")
            if len(parts) > 1:
                modules.add(parts[0])

        # Use first focal unit's directory as root hint
        root_path = ""
        if focal_units:
            root_path = focal_units[0].file_path.split("/")[0] if "/" in focal_units[0].file_path else ""

        return RepositoryMap(
            root_path=root_path,
            files=sorted(list(all_files)),
            modules=sorted(list(modules)),
        )

    def _estimate_tokens(
        self,
        focal_units: List[CodeUnit],
        skeletons: List[CodeUnitSkeleton],
    ) -> int:
        """Estimate total token count for the bundle.

        Uses a conservative character-to-token ratio.

        Args:
            focal_units: List of focal code units.
            skeletons: List of dependency skeletons.

        Returns:
            Estimated token count.
        """
        total_chars = 0

        for unit in focal_units:
            # Count full body for focal units
            total_chars += len(unit.body)
            total_chars += len(unit.signature)
            if unit.docstring:
                total_chars += len(unit.docstring)

        for skeleton in skeletons:
            # Count only signature for skeletons
            total_chars += len(skeleton.signature)
            if skeleton.docstring:
                total_chars += len(skeleton.docstring)

        return int(total_chars * self.TOKENS_PER_CHAR)

    def _create_empty_bundle(self, query: str, start_time: float) -> ContextBundle:
        """Create an empty bundle for failed resolutions.

        Args:
            query: The original query.
            start_time: Timestamp when build started.

        Returns:
            Empty ContextBundle with metadata.
        """
        duration_ms = (time.time() - start_time) * 1000

        metadata = ContextMetadata(
            created_at=__import__("datetime").datetime.now(),
            total_tokens=0,
            num_focal_units=0,
            num_dependencies=0,
            search_duration_ms=duration_ms,
        )

        return ContextBundle(
            query=query,
            focal_units=[],
            dependency_skeletons=[],
            repository_map=None,
            metadata=metadata,
        )

    def _lookup_unit_by_id(self, unit_id: str) -> Optional[CodeUnit]:
        """Lookup a code unit by its ID.

        Args:
            unit_id: The code unit ID to lookup.

        Returns:
            The CodeUnit if found, None otherwise.
        """
        # Extract symbol name from ID
        symbol_name = self._extract_symbol_name(unit_id)
        if not symbol_name:
            return None

        # Use lookup to find the unit
        return self.symbol_lookup.lookup_exact(symbol_name)

    def _extract_symbol_name(self, unit_id: str) -> str:
        """Extract the symbol name from a unit ID.

        Args:
            unit_id: The code unit ID (format: repo_path/file:symbol_name).

        Returns:
            The symbol name.
        """
        if ":" in unit_id:
            return unit_id.split(":")[-1]
        return unit_id
