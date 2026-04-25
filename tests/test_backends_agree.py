"""Both backends must produce byte-identical output for the same input."""

import pytest


CASES = [
    ("svg", "digraph G { a -> b; }"),
    ("svg", "graph G { a -- b -- c -- a; }"),
    ("dot", "digraph G { a -> b; }"),
    ("plain", "digraph G { a -> b -> c; }"),
]


@pytest.mark.parametrize("fmt,dot", CASES)
def test_backends_agree(fmt, dot):
    from wasi_graphviz.backends.pywasm_backend import PywasmBackend
    from wasi_graphviz.backends.wasmtime_backend import WasmtimeBackend

    a = WasmtimeBackend().render(dot, format=fmt, engine="dot")
    b = PywasmBackend().render(dot, format=fmt, engine="dot")
    assert a == b, f"backends diverged for fmt={fmt}"
