"""Hard tests for maximum flow."""

from __future__ import annotations

from collections import deque

import pytest

from max_flow import max_flow


def _edmonds_karp(
    n: int,
    edges: list[tuple[int, int, int]],
    source: int,
    sink: int,
) -> int:
    if source == sink:
        return 0
    # residual adjacency: list of [to, cap, rev_index]
    g: list[list[list[int]]] = [[] for _ in range(n)]

    def add_edge(u: int, v: int, c: int) -> None:
        g[u].append([v, c, len(g[v])])
        g[v].append([u, 0, len(g[u]) - 1])

    for u, v, c in edges:
        if c < 0:
            raise ValueError("negative capacity")
        add_edge(u, v, c)

    flow = 0
    while True:
        parent: list[tuple[int, int] | None] = [None] * n
        q: deque[int] = deque([source])
        parent[source] = (-1, -1)
        found = False
        while q and not found:
            u = q.popleft()
            for i, (v, cap, _) in enumerate(g[u]):
                if parent[v] is None and cap > 0:
                    parent[v] = (u, i)
                    if v == sink:
                        found = True
                        break
                    q.append(v)
        if not found:
            break
        # bottleneck
        aug = 10**18
        v = sink
        while v != source:
            u, i = parent[v]  # type: ignore
            aug = min(aug, g[u][i][1])
            v = u
        v = sink
        while v != source:
            u, i = parent[v]  # type: ignore
            g[u][i][1] -= aug
            rev = g[u][i][2]
            to = g[u][i][0]
            g[to][rev][1] += aug
            v = u
        flow += aug
    return flow


class TestMaxFlowBasic:
    def test_classic_example(self):
        n = 4
        edges = [(0, 1, 3), (0, 2, 2), (1, 2, 5), (1, 3, 2), (2, 3, 3)]
        assert max_flow(n, edges, 0, 3) == 5

    def test_source_equals_sink(self):
        assert max_flow(3, [(0, 1, 5)], 1, 1) == 0

    def test_no_path(self):
        assert max_flow(3, [(0, 1, 10)], 0, 2) == 0

    def test_single_edge(self):
        assert max_flow(2, [(0, 1, 7)], 0, 1) == 7

    def test_zero_capacity(self):
        assert max_flow(2, [(0, 1, 0)], 0, 1) == 0

    def test_parallel_edges(self):
        edges = [(0, 1, 3), (0, 1, 4), (1, 2, 10)]
        assert max_flow(3, edges, 0, 2) == 7

    def test_diamond(self):
        # 0 -> 1 -> 3, 0 -> 2 -> 3, bottleneck 1+1
        edges = [(0, 1, 1), (0, 2, 1), (1, 3, 100), (2, 3, 100)]
        assert max_flow(4, edges, 0, 3) == 2


class TestMaxFlowHard:
    def test_bipartite_matching_style(self):
        # source 0, left 1..3, right 4..6, sink 7
        edges = []
        for L in (1, 2, 3):
            edges.append((0, L, 1))
        for R in (4, 5, 6):
            edges.append((R, 7, 1))
        # complete bipartite left-right capacity 1
        for L in (1, 2, 3):
            for R in (4, 5, 6):
                edges.append((L, R, 1))
        assert max_flow(8, edges, 0, 7) == 3

    def test_random_graphs_match_reference(self):
        x = 42
        for trial in range(25):
            n = 8 + (trial % 5)
            m = 15 + trial * 2
            edges: list[tuple[int, int, int]] = []
            for _ in range(m):
                x = (1103515245 * x + 12345) & 0x7FFFFFFF
                u = x % n
                x = (1103515245 * x + 12345) & 0x7FFFFFFF
                v = x % n
                x = (1103515245 * x + 12345) & 0x7FFFFFFF
                c = (x % 20) + 1
                if u != v:
                    edges.append((u, v, c))
            s, t = 0, n - 1
            got = max_flow(n, edges, s, t)
            exp = _edmonds_karp(n, edges, s, t)
            assert got == exp, f"trial {trial}: got {got} expected {exp}"

    def test_dense_graph(self):
        n = 40
        edges: list[tuple[int, int, int]] = []
        # layered network 0 -> mid -> sink
        mid = list(range(1, n - 1))
        for i in mid:
            edges.append((0, i, 5))
            edges.append((i, n - 1, 5))
        for i in mid:
            for j in mid:
                if i < j:
                    edges.append((i, j, 1))
        got = max_flow(n, edges, 0, n - 1)
        exp = _edmonds_karp(n, edges, 0, n - 1)
        assert got == exp
        assert got == 5 * len(mid)
