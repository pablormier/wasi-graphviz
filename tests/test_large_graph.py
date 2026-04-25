"""Regression test: outputs larger than the historical 64 KB cap.

Earlier ABI returned a NUL-terminated buffer and the Python backends
scanned it byte-by-byte with max_len=65536, silently truncating any
larger render.  The current ABI returns an explicit length, so a graph
whose SVG comfortably exceeds 64 KB must round-trip intact.
"""

import pytest


def _big_dot(n: int = 400) -> str:
    edges = " ".join(f"n{i} -> n{i + 1};" for i in range(n))
    return f"digraph G {{ {edges} }}"


@pytest.mark.parametrize("backend", ["wasmtime", "pywasm"])
def test_large_graph_not_truncated(backend):
    from wasi_graphviz import render

    svg = render(_big_dot(), backend=backend)
    assert len(svg) > 70_000, f"expected >70 KB, got {len(svg)}"
    assert svg.startswith(b"<?xml") or svg.lstrip().startswith(b"<")
    assert svg.rstrip().endswith(b"</svg>"), "render appears truncated"
