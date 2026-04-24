"""Tests for the pywasm backend."""

import pytest

from wasi_graphviz import render
from wasi_graphviz.backends.pywasm_backend import PywasmBackend
from wasi_graphviz._exceptions import RenderError


def test_render_simple_dot():
    """Render a simple directed graph to SVG."""
    svg = render("digraph G { a -> b; }", backend="pywasm")
    assert b"<svg" in svg
    assert b"</svg>" in svg


def test_render_with_pywasm_backend():
    """Use PywasmBackend directly."""
    backend = PywasmBackend()
    svg = backend.render("digraph G { a -> b; }", format="svg", engine="dot")
    assert b"<svg" in svg
    assert b"</svg>" in svg


def test_render_different_engines():
    """Test multiple layout engines."""
    dot = "graph G { a -- b; }"
    for engine in [
        "dot",
        "neato",
        "circo",
        "fdp",
        "sfdp",
        "twopi",
        "osage",
        "patchwork",
    ]:
        svg = render(dot, engine=engine, backend="pywasm")
        assert b"<svg" in svg, f"Engine {engine} failed"


def test_render_invalid_dot():
    """Invalid DOT should raise RenderError."""
    with pytest.raises(RenderError):
        render("not valid dot {", backend="pywasm")
