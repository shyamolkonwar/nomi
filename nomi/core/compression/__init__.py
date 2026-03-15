"""Context compression package for Nomi.

This package provides token reduction strategies for AI coding agents,
including code skeletonization, token budget management, and context pruning.
"""

from nomi.core.compression.pruner import ContextPruner, PruneConfig, PruneResult
from nomi.core.compression.skeletonizer import Skeletonizer
from nomi.core.compression.token_budget import AllocationResult, TokenBudget

__all__ = [
    "Skeletonizer",
    "TokenBudget",
    "AllocationResult",
    "ContextPruner",
    "PruneConfig",
    "PruneResult",
]
