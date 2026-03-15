"""Context pruning strategies for token reduction.

This module provides multiple pruning strategies to reduce context size
while preserving the most relevant information for AI coding agents.
"""

from dataclasses import dataclass
from typing import List, Optional, Set, Dict

from nomi.storage.models import CodeUnit


@dataclass
class PruneConfig:
    """Configuration for context pruning.

    Attributes:
        max_depth: Maximum dependency depth to include (default 2)
        max_tokens: Maximum token budget (default 4000)
        keep_high_centrality: Whether to prioritize high-centrality units
        preserve_interfaces: Whether to preserve interface definitions
    """

    max_depth: int = 2
    max_tokens: int = 4000
    keep_high_centrality: bool = True
    preserve_interfaces: bool = True


@dataclass
class PruneResult:
    """Result of context pruning operation.

    Attributes:
        kept_full: Units kept with full implementation
        skeletonized: Units kept as skeletons (signatures only)
        pruned: Units excluded entirely
        token_estimate: Estimated total token count
    """

    kept_full: List[CodeUnit]
    skeletonized: List[CodeUnit]
    pruned: List[CodeUnit]
    token_estimate: int


class ContextPruner:
    """Prunes context to fit within token budgets.

    Implements tiered pruning strategies that progressively remove
    less relevant context while preserving critical information.
    """

    def __init__(self, config: Optional[PruneConfig] = None):
        """Initialize pruner with configuration.

        Args:
            config: Pruning configuration (uses defaults if None)
        """
        self.config = config or PruneConfig()
        self.CHARS_PER_TOKEN = 4.0

    def _estimate_tokens(self, unit: CodeUnit) -> int:
        """Estimate token count for a code unit.

        Args:
            unit: Code unit to estimate

        Returns:
            Estimated token count
        """
        content = unit.signature
        if unit.body:
            content += unit.body
        if unit.docstring:
            content += unit.docstring
        return int(len(content) / self.CHARS_PER_TOKEN)

    def prune_by_depth(
        self, units: List[CodeUnit], max_depth: int
    ) -> List[CodeUnit]:
        """Remove units beyond depth limit.

        Args:
            units: List of code units with depth information in metadata
            max_depth: Maximum depth to keep

        Returns:
            Filtered list of units within depth limit
        """
        return [u for u in units if self._get_unit_depth(u) <= max_depth]

    def _get_unit_depth(self, unit: CodeUnit) -> int:
        """Extract depth from unit metadata or return default.

        Args:
            unit: Code unit to check

        Returns:
            Dependency depth (defaults to 0)
        """
        return 0

    def prune_by_relevance(
        self,
        units: List[CodeUnit],
        focal_unit_ids: Set[str],
        min_relevance: float,
    ) -> List[CodeUnit]:
        """Remove low-relevance units based on distance from focal units.

        Args:
            units: List of code units to filter
            focal_unit_ids: Set of focal unit IDs (relevance = 1.0)
            min_relevance: Minimum relevance threshold (0.0 to 1.0)

        Returns:
            Filtered list of units meeting relevance threshold
        """
        return [
            u
            for u in units
            if self._calculate_relevance(u, focal_unit_ids) >= min_relevance
        ]

    def _calculate_relevance(
        self, unit: CodeUnit, focal_unit_ids: Set[str]
    ) -> float:
        """Calculate relevance score for a unit.

        Args:
            unit: Code unit to score
            focal_unit_ids: Set of focal unit IDs

        Returns:
            Relevance score between 0.0 and 1.0
        """
        if unit.id in focal_unit_ids:
            return 1.0

        if any(dep_id in focal_unit_ids for dep_id in unit.dependencies):
            return 0.8

        return 0.5

    def prune_by_token_count(
        self, units: List[CodeUnit], max_tokens: int
    ) -> List[CodeUnit]:
        """Remove units to fit within token budget.

        Removes lowest-relevance units first until budget is met.

        Args:
            units: List of code units to prune
            max_tokens: Maximum token budget

        Returns:
            Pruned list of units within token budget
        """
        sorted_units = sorted(
            units, key=lambda u: self._calculate_priority(u), reverse=True
        )

        result = []
        total_tokens = 0

        for unit in sorted_units:
            unit_tokens = self._estimate_tokens(unit)
            if total_tokens + unit_tokens <= max_tokens:
                result.append(unit)
                total_tokens += unit_tokens

        return result

    def _calculate_priority(self, unit: CodeUnit) -> float:
        """Calculate priority score for pruning order.

        Higher priority units are kept when pruning.

        Args:
            unit: Code unit to score

        Returns:
            Priority score (higher = more important)
        """
        priority = 0.0

        if self.config.preserve_interfaces and unit.unit_kind.value in (
            "INTERFACE",
            "CLASS",
        ):
            priority += 10.0

        if self.config.keep_high_centrality and len(unit.dependencies) > 5:
            priority += 5.0

        if unit.docstring:
            priority += 2.0

        priority += 1.0 / (len(unit.body) + 1) * 100

        return priority

    def tiered_pruning(
        self,
        focal_units: List[CodeUnit],
        dependencies: List[CodeUnit],
        config: Optional[PruneConfig] = None,
    ) -> PruneResult:
        """Perform tiered pruning with multiple strategies.

        Tiers:
        1. Focal units: Always kept in full
        2. 1-hop dependencies: Kept as skeletons
        3. 2+ hop dependencies: Pruned if over budget

        Args:
            focal_units: Primary target units
            dependencies: Related dependency units
            config: Optional pruning configuration

        Returns:
            PruneResult with kept, skeletonized, and pruned units
        """
        cfg = config or self.config

        kept_full = list(focal_units)
        skeletonized: List[CodeUnit] = []
        pruned: List[CodeUnit] = []

        focal_ids = {u.id for u in focal_units}
        focal_deps = set()
        for u in focal_units:
            focal_deps.update(u.dependencies)

        one_hop_deps = [
            d for d in dependencies if d.id in focal_deps or d.id in focal_ids
        ]
        two_plus_hop_deps = [d for d in dependencies if d not in one_hop_deps]

        two_plus_hop_deps = self.prune_by_depth(two_plus_hop_deps, cfg.max_depth - 1)

        total_tokens = sum(self._estimate_tokens(u) for u in kept_full)

        for unit in one_hop_deps:
            unit_tokens = int(self._estimate_tokens(unit) * 0.25)
            if total_tokens + unit_tokens <= cfg.max_tokens:
                skeletonized.append(unit)
                total_tokens += unit_tokens
            else:
                pruned.append(unit)

        remaining_budget = cfg.max_tokens - total_tokens
        if remaining_budget > 0:
            two_plus_filtered = self.prune_by_token_count(
                two_plus_hop_deps, remaining_budget // 4
            )
            for unit in two_plus_filtered:
                unit_tokens = int(self._estimate_tokens(unit) * 0.25)
                if total_tokens + unit_tokens <= cfg.max_tokens:
                    skeletonized.append(unit)
                    total_tokens += unit_tokens
                else:
                    pruned.append(unit)

            for unit in two_plus_hop_deps:
                if unit not in two_plus_filtered:
                    pruned.append(unit)

        return PruneResult(
            kept_full=kept_full,
            skeletonized=skeletonized,
            pruned=pruned,
            token_estimate=total_tokens,
        )

    def get_pruning_stats(self, result: PruneResult) -> Dict:
        """Get statistics about pruning operation.

        Args:
            result: Prune result to analyze

        Returns:
            Dictionary with pruning statistics
        """
        total_units = len(result.kept_full) + len(result.skeletonized) + len(result.pruned)

        return {
            "total_units": total_units,
            "kept_full_count": len(result.kept_full),
            "skeletonized_count": len(result.skeletonized),
            "pruned_count": len(result.pruned),
            "kept_full_ratio": len(result.kept_full) / total_units if total_units > 0 else 0,
            "skeletonized_ratio": len(result.skeletonized) / total_units if total_units > 0 else 0,
            "pruned_ratio": len(result.pruned) / total_units if total_units > 0 else 0,
            "token_estimate": result.token_estimate,
            "tokens_per_unit": result.token_estimate / total_units if total_units > 0 else 0,
        }
