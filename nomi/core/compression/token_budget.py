"""Token budget management for context compression.

This module provides functionality to manage token budgets when assembling
context bundles, deciding which code units to include fully vs skeletonize.
"""

from dataclasses import dataclass
from typing import List

from nomi.core.context.context_bundle import CodeUnitSkeleton
from nomi.storage.models import CodeUnit


@dataclass
class AllocationResult:
    """Result of token budget allocation.

    Attributes:
        full_units: Units to include with full implementation
        skeleton_units: Units to include as skeletons only
        pruned_units: Units excluded entirely
        estimated_tokens: Total estimated token count
    """

    full_units: List[CodeUnit]
    skeleton_units: List[CodeUnit]
    pruned_units: List[CodeUnit]
    estimated_tokens: int


class TokenBudget:
    """Manages token budget allocation for context bundles.

    Provides token estimation and budget allocation strategies to fit
    context within LLM token limits while maximizing useful information.
    """

    CHARS_PER_TOKEN: float = 4.0

    def __init__(self, max_tokens: int = 4000):
        """Initialize token budget.

        Args:
            max_tokens: Maximum allowed tokens (default 4000 for GPT-4 context)
        """
        self.max_tokens = max_tokens
        self._tiktoken_available = False
        self._encoding = None

        try:
            import tiktoken

            self._tiktoken_available = True
            try:
                self._encoding = tiktoken.encoding_for_model("gpt-4")
            except KeyError:
                self._encoding = tiktoken.get_encoding("cl100k_base")
        except ImportError:
            pass

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Uses tiktoken if available, otherwise falls back to char/4 heuristic.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        if not text:
            return 0

        if self._tiktoken_available and self._encoding:
            try:
                return len(self._encoding.encode(text))
            except Exception:
                pass

        return int(len(text) / self.CHARS_PER_TOKEN)

    def estimate_code_unit_tokens(self, unit: CodeUnit) -> int:
        """Estimate token count for a code unit.

        Args:
            unit: Code unit to estimate

        Returns:
            Estimated token count including signature and body
        """
        content = unit.signature
        if unit.body:
            content += unit.body
        if unit.docstring:
            content += unit.docstring
        return self.estimate_tokens(content)

    def estimate_skeleton_tokens(self, skeleton: CodeUnitSkeleton) -> int:
        """Estimate token count for a skeleton.

        Args:
            skeleton: Skeleton to estimate

        Returns:
            Estimated token count
        """
        content = skeleton.signature
        if skeleton.docstring:
            content += skeleton.docstring
        return self.estimate_tokens(content)

    def allocate_budget(
        self,
        focal_units: List[CodeUnit],
        dependencies: List[CodeUnit],
        skeleton_ratio: float = 0.25,
    ) -> AllocationResult:
        """Allocate token budget between focal units and dependencies.

        Strategy:
        1. Always include focal units in full
        2. Allocate remaining budget to dependencies
        3. Skeletonize dependencies if needed to fit budget
        4. Prune low-priority dependencies if still over budget

        Args:
            focal_units: Primary target units (always kept in full)
            dependencies: Related units to include as context
            skeleton_ratio: Token ratio for skeleton vs full (default 0.25)

        Returns:
            AllocationResult with full, skeleton, and pruned units
        """
        full_units: List[CodeUnit] = []
        skeleton_units: List[CodeUnit] = []
        pruned_units: List[CodeUnit] = []

        total_tokens = 0

        for unit in focal_units:
            tokens = self.estimate_code_unit_tokens(unit)
            total_tokens += tokens
            full_units.append(unit)

        remaining_budget = self.max_tokens - total_tokens

        sorted_deps = sorted(dependencies, key=lambda u: self.estimate_code_unit_tokens(u), reverse=True)

        for unit in sorted_deps:
            full_tokens = self.estimate_code_unit_tokens(unit)
            skeleton_tokens = int(full_tokens * skeleton_ratio)

            if full_tokens <= remaining_budget:
                full_units.append(unit)
                total_tokens += full_tokens
                remaining_budget -= full_tokens
            elif skeleton_tokens <= remaining_budget:
                skeleton_units.append(unit)
                total_tokens += skeleton_tokens
                remaining_budget -= skeleton_tokens
            else:
                pruned_units.append(unit)

        return AllocationResult(
            full_units=full_units,
            skeleton_units=skeleton_units,
            pruned_units=pruned_units,
            estimated_tokens=total_tokens,
        )

    def get_compression_ratio(self, original: CodeUnit, skeleton: CodeUnitSkeleton) -> float:
        """Calculate compression ratio achieved by skeletonization.

        Args:
            original: Original code unit
            skeleton: Skeletonized version

        Returns:
            Compression ratio (0.0 to 1.0, higher = more compression)
        """
        original_tokens = self.estimate_code_unit_tokens(original)
        skeleton_tokens = self.estimate_skeleton_tokens(skeleton)

        if original_tokens == 0:
            return 0.0

        return 1.0 - (skeleton_tokens / original_tokens)

    def get_stats(self, result: AllocationResult) -> dict:
        """Get statistics about token allocation.

        Args:
            result: Allocation result to analyze

        Returns:
            Dictionary with allocation statistics
        """
        full_tokens = sum(self.estimate_code_unit_tokens(u) for u in result.full_units)
        skeleton_tokens = sum(int(self.estimate_code_unit_tokens(u) * 0.25) for u in result.skeleton_units)

        return {
            "max_tokens": self.max_tokens,
            "used_tokens": result.estimated_tokens,
            "remaining_tokens": self.max_tokens - result.estimated_tokens,
            "utilization": result.estimated_tokens / self.max_tokens,
            "full_units_count": len(result.full_units),
            "skeleton_units_count": len(result.skeleton_units),
            "pruned_units_count": len(result.pruned_units),
            "full_tokens": full_tokens,
            "skeleton_tokens": skeleton_tokens,
        }
