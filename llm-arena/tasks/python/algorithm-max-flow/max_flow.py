"""Maximum flow — implement max_flow(n, edges, source, sink)."""

from __future__ import annotations


def max_flow(
    n: int,
    edges: list[tuple[int, int, int]],
    source: int,
    sink: int,
) -> int:
    """Return maximum flow from source to sink on a directed capacity graph.

    Nodes are 0 .. n-1. edges is a list of (u, v, capacity). Parallel edges allowed.
    """
    raise NotImplementedError("Implement max_flow")
