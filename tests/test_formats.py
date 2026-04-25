"""Format matrix: each output format produces its expected sentinel."""

import pytest

DOT = "digraph G { a -> b; }"

FORMAT_SENTINELS = {
    "svg": b"</svg>",
    "dot": b"digraph",
    "xdot": b"digraph",
    "json": b'"name"',
    "plain": b"graph ",
}


@pytest.mark.parametrize("backend", ["wasmtime", "pywasm"])
@pytest.mark.parametrize("fmt,sentinel", list(FORMAT_SENTINELS.items()))
def test_format(backend, fmt, sentinel):
    from wasi_graphviz import render

    out = render(DOT, format=fmt, backend=backend)
    assert sentinel in out, f"format={fmt} backend={backend}: missing {sentinel!r}"
