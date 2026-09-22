"""Tests for supplying image files to the WASI guest."""

import base64
import xml.etree.ElementTree as ET

import pytest

from wasi_graphviz import render
from wasi_graphviz._assets import embed_svg_assets


SVG_IMAGE = b"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16">
  <rect width="16" height="16" fill="red"/>
</svg>
"""
PNG_IMAGE = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/g9sAAAAASUVORK5CYII="
)
DOT_WITH_IMAGE = """digraph G {
  node [shape=none, image="/assets/glyph.svg", label=""]
  glyph
}"""
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"


def _images(svg):
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        root = ET.fromstring(
            b'<svg xmlns="http://www.w3.org/2000/svg" '
            b'xmlns:xlink="http://www.w3.org/1999/xlink">' + svg + b"</svg>"
        )
    return [
        image.get(XLINK_HREF) or image.get("href")
        for image in root.iter("{http://www.w3.org/2000/svg}image")
    ]


@pytest.mark.parametrize("backend", ["auto", "wasmtime", "pywasm"])
def test_render_svg_image_asset(backend):
    svg = render(
        DOT_WITH_IMAGE,
        backend=backend,
        assets={"glyph.svg": SVG_IMAGE},
    )

    images = _images(svg)
    assert len(images) == 1
    mime, encoded = images[0].split(",", 1)
    assert mime == "data:image/svg+xml;base64"
    assert base64.b64decode(encoded) == SVG_IMAGE
    assert b"/assets/" not in svg


@pytest.mark.parametrize("backend", ["wasmtime", "pywasm"])
@pytest.mark.parametrize(
    "format",
    [
        "svg:svg",
        "svg_inline",
        "svg_inline:svg",
        "svg:svg:core",
        "svg_inline:svg:core",
    ],
)
def test_embed_svg_format_variants(backend, format):
    svg = render(
        DOT_WITH_IMAGE,
        format=format,
        backend=backend,
        assets={"glyph.svg": SVG_IMAGE},
    )

    images = _images(svg)
    assert len(images) == 1
    mime, encoded = images[0].split(",", 1)
    assert mime == "data:image/svg+xml;base64"
    assert base64.b64decode(encoded) == SVG_IMAGE
    assert b"/assets/" not in svg


@pytest.mark.parametrize("backend", ["wasmtime", "pywasm"])
@pytest.mark.parametrize(
    "image,asset_name,imagepath",
    [
        ("/assets/./glyph.svg", "glyph.svg", "/assets"),
        ("glyph.svg", "glyph.svg", "/assets"),
        ("icons/marker.svg", "icons/marker.svg", "/assets"),
        ("marker.svg", "icons/marker.svg", "/assets/icons"),
    ],
)
def test_embed_normalized_and_imagepath_relative_references(
    backend, image, asset_name, imagepath
):
    dot = f'''graph G {{
      graph [imagepath="{imagepath}"]
      node [shape=none, label=""]
      glyph [image="{image}"]
    }}'''

    svg = render(dot, backend=backend, assets={asset_name: SVG_IMAGE})

    images = _images(svg)
    assert len(images) == 1
    mime, encoded = images[0].split(",", 1)
    assert mime == "data:image/svg+xml;base64"
    assert base64.b64decode(encoded) == SVG_IMAGE
    assert b"/assets/" not in svg


def test_preserves_unrelated_image_references():
    svg = b"""<svg xmlns="http://www.w3.org/2000/svg"
      xmlns:xlink="http://www.w3.org/1999/xlink">
      <image xlink:href="/assets/glyph.svg"/>
      <image xlink:href="https://example.invalid/other.svg"/>
    </svg>"""

    embedded = embed_svg_assets(svg, {"glyph.svg": SVG_IMAGE})

    images = _images(embedded)
    mime, encoded = images[0].split(",", 1)
    assert mime == "data:image/svg+xml;base64"
    assert base64.b64decode(encoded) == SVG_IMAGE
    assert images[1] == "https://example.invalid/other.svg"


def test_ambiguous_relative_image_reference_requires_explicit_path():
    svg = b"""<svg xmlns="http://www.w3.org/2000/svg"
      xmlns:xlink="http://www.w3.org/1999/xlink">
      <image xlink:href="glyph.svg"/>
    </svg>"""

    with pytest.raises(ValueError, match="use an explicit /assets/<path>"):
        embed_svg_assets(
            svg, {"icons/glyph.svg": SVG_IMAGE, "logos/glyph.svg": SVG_IMAGE}
        )


@pytest.mark.parametrize("backend", ["auto", "wasmtime", "pywasm"])
def test_embed_multiple_assets_with_nested_paths(backend):
    dot = """digraph G {
      node [shape=none, label=""]
      glyph [image="/assets/glyph.svg"]
      marker [image="/assets/icons/marker.png"]
    }"""

    svg = render(
        dot,
        backend=backend,
        assets={"glyph.svg": SVG_IMAGE, "icons/marker.png": PNG_IMAGE},
    )

    images = _images(svg)
    assert len(images) == 2
    assert {
        mime: base64.b64decode(encoded)
        for mime, encoded in (image.split(",", 1) for image in images)
    } == {
        "data:image/svg+xml;base64": SVG_IMAGE,
        "data:image/png;base64": PNG_IMAGE,
    }
    assert b"/assets/" not in svg


def test_unused_non_image_asset_does_not_block_svg_embedding():
    svg = render(
        DOT_WITH_IMAGE,
        backend="wasmtime",
        assets={"glyph.svg": SVG_IMAGE, "notes.txt": b"asset metadata"},
    )

    images = _images(svg)
    assert len(images) == 1
    mime, encoded = images[0].split(",", 1)
    assert mime == "data:image/svg+xml;base64"
    assert base64.b64decode(encoded) == SVG_IMAGE


@pytest.mark.parametrize("backend", ["auto", "wasmtime", "pywasm"])
def test_image_assets_are_isolated_per_render(backend):
    with_asset = render(
        DOT_WITH_IMAGE,
        backend=backend,
        assets={"glyph.svg": SVG_IMAGE},
    )
    without_asset = render(DOT_WITH_IMAGE, backend=backend)

    assert b"<image" in with_asset
    assert b"<image" not in without_asset


@pytest.mark.parametrize("backend", ["wasmtime", "pywasm"])
def test_assets_do_not_expose_host_files(backend, tmp_path):
    outside_file = tmp_path / "outside.svg"
    outside_file.write_bytes(SVG_IMAGE)
    dot = f'''digraph G {{
      node [shape=none, image="{outside_file}", label=""]
      glyph
    }}'''

    svg = render(dot, backend=backend, assets={"safe.svg": SVG_IMAGE})

    assert b"<image" not in svg


@pytest.mark.parametrize(
    "bad_path", ["../secret", "/absolute", "a\\b", "C:/secret", "bad&name.svg"]
)
def test_rejects_unsafe_asset_paths(bad_path):
    with pytest.raises(ValueError, match="safe relative path"):
        render("digraph G {}", backend="wasmtime", assets={bad_path: b"content"})


def test_rejects_non_bytes_asset_content():
    with pytest.raises(TypeError, match="bytes-like"):
        render("digraph G {}", backend="wasmtime", assets={"asset.svg": "text"})


def test_rejects_unsupported_svg_image_type():
    svg = b"""<svg xmlns="http://www.w3.org/2000/svg"
      xmlns:xlink="http://www.w3.org/1999/xlink">
      <image xlink:href="/assets/glyph.bmp"/>
    </svg>"""

    with pytest.raises(ValueError, match="unsupported image extension"):
        embed_svg_assets(svg, {"glyph.bmp": b"image"})
