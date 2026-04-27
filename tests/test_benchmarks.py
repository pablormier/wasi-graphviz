"""Benchmarks: wasmtime vs pywasm across graph sizes.

Skipped by default (see pyproject `addopts = -m 'not perf'`).

Run with:
    uv run pytest tests/test_benchmarks.py -m perf --benchmark-only

The pywasm interpreter is roughly two orders of magnitude slower than
wasmtime, so its rounds are kept low to keep total wall time tolerable.
"""

import pytest


def _dot(n: int) -> str:
    edges = " ".join(f"n{i} -> n{i + 1};" for i in range(n))
    return f"digraph G {{ {edges} }}"


SIZES = [
    pytest.param(10, id="small-10e"),
    pytest.param(100, id="medium-100e"),
    pytest.param(400, id="large-400e"),
]

# Backend instances are constructed once per module so the benchmark times
# pure render cost, not WASM module instantiation.
_BACKENDS: dict = {}


def _backend(name):
    if name not in _BACKENDS:
        if name == "wasmtime":
            from wasi_graphviz.backends.wasmtime_backend import WasmtimeBackend

            _BACKENDS[name] = WasmtimeBackend()
        elif name == "pywasm":
            from wasi_graphviz.backends.pywasm_backend import PywasmBackend

            _BACKENDS[name] = PywasmBackend()
        else:
            raise ValueError(name)
    return _BACKENDS[name]


@pytest.mark.perf
@pytest.mark.parametrize("n_edges", SIZES)
def test_render_wasmtime(benchmark, n_edges):
    backend = _backend("wasmtime")
    dot = _dot(n_edges)
    benchmark.group = f"render-{n_edges}e"
    out = benchmark(backend.render, dot)
    assert out.rstrip().endswith(b"</svg>")


@pytest.mark.perf
@pytest.mark.benchmark(min_rounds=3, warmup=False, max_time=15.0)
@pytest.mark.parametrize("n_edges", SIZES)
def test_render_pywasm(benchmark, n_edges):
    backend = _backend("pywasm")
    dot = _dot(n_edges)
    benchmark.group = f"render-{n_edges}e"
    out = benchmark(backend.render, dot)
    assert out.rstrip().endswith(b"</svg>")
