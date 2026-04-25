"""Lock in the wheel data-file contract: graphviz.wasm ships inside the package."""

from importlib.resources import files


def test_packaged_wasm_present_and_nonempty():
    resource = files("wasi_graphviz").joinpath("assets/graphviz.wasm")
    with resource.open("rb") as fh:
        head = fh.read(8)
    assert head[:4] == b"\x00asm", "vendored asset is not a WASM module"


def test_render_uses_packaged_wasm_by_default():
    from wasi_graphviz import render

    svg = render("digraph G { a -> b; }")
    assert b"</svg>" in svg
