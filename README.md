# wasi-graphviz

Run Graphviz from Python via WebAssembly — no native Graphviz binary, no Node.js, no browser required.

## Installation

```bash
# Minimal install with pywasm (pure Python, slower)
pip install wasi-graphviz[pywasm]

# Recommended install with wasmtime (faster)
pip install wasi-graphviz[wasmtime]

# Install both backends
pip install wasi-graphviz[all]
```

## Quick start

```python
from wasi_graphviz import render

# Render a simple graph to SVG (uses wasmtime if available, falls back to pywasm)
svg = render("digraph G { a -> b; }")
print(svg.decode("utf-8"))
```

## Usage

### Basic rendering

```python
from wasi_graphviz import render

# Render to SVG with default dot engine
svg = render("digraph G { a -> b; }")

# Use a different layout engine
svg = render("graph G { a -- b; }", engine="neato")

# Render to DOT format
output = render("digraph G { a -> b; }", format="dot")
```

### Backend selection

```python
from wasi_graphviz import render

# Auto-select (prefer wasmtime, fall back to pywasm)
svg = render("digraph G { a -> b; }", backend="auto")

# Force pywasm (pure Python, works everywhere)
svg = render("digraph G { a -> b; }", backend="pywasm")

# Force wasmtime (faster, requires compiled extension)
svg = render("digraph G { a -> b; }", backend="wasmtime")
```

### Error handling

```python
from wasi_graphviz import render, RenderError

try:
    svg = render("not valid dot {")
except RenderError as e:
    print(f"Render failed: {e}")
```

## Supported layout engines

All major Graphviz layout engines work:
- `dot` — hierarchical layouts (default)
- `neato` — spring model
- `circo` — circular layout
- `fdp` — force-directed placement
- `sfdp` — scalable FDP
- `twopi` — radial layouts
- `osage` — array-based layouts
- `patchwork` — treemaps

## Supported output formats

The core plugin supports:
- `svg` (default)
- `dot`
- `json`
- `ps`
- `map`
- `fig`
- `tk`

## Architecture

The project consists of three layers:

1. **WASM artifact** (`graphviz.wasm`)
   - Graphviz 14.1.5 compiled for `wasm32-wasi`
   - Exposes a plain C ABI: `graphviz_render`, `graphviz_free`, `graphviz_last_error`, `graphviz_version`
   - No Emscripten, no JS glue

2. **Python backends**
   - `PywasmBackend` — pure-Python interpreter with built-in WASI support
   - `WasmtimeBackend` — fast native runtime with full WASI support

3. **Public API**
   - `render(dot, format="svg", engine="dot", backend="auto") -> bytes`

## Building from source

See [BUILD.md](BUILD.md) for detailed build instructions.

Quick summary:

```bash
# Install build tools
pixi install

# Build the WASM artifact
python scripts/prepare_graphviz_wasi.py build/src/graphviz-14.1.5
pixi run cmake -S build/src/graphviz-14.1.5 -B build/graphviz-cmake \
  -DCMAKE_TOOLCHAIN_FILE=$(pwd)/native/wasm32-wasi-toolchain.cmake \
  ...
pixi run cmake --build build/graphviz-cmake --parallel
# ... compile wrapper, link, validate
```

## Development

```bash
# Run tests
uv run pytest

# Format and lint
uv run ruff check .
uv run ruff format .
```

## License & attribution

The Python wrapper, C wrapper (`native/main.c`), and build scripts in this
repository are licensed under **Apache-2.0** (see [`LICENSE`](LICENSE)).

The wheel bundles a compiled build of [Graphviz](https://graphviz.org/),
which is licensed under the **Eclipse Public License 2.0** (EPL-2.0).
The full EPL-2.0 text is shipped inside the wheel at
`wasi_graphviz/assets/GRAPHVIZ_LICENSE`. Source for the bundled Graphviz
version is available upstream:
<https://gitlab.com/graphviz/graphviz/-/tree/14.1.5>.

Modifications applied to the Graphviz source before compilation are
described in
[`scripts/prepare_graphviz_wasi.py`](scripts/prepare_graphviz_wasi.py)
and are themselves licensed under EPL-2.0. See [`NOTICE`](NOTICE) for the
full attribution.

> **wasi-graphviz is an unofficial repackaging and is not affiliated with
> or endorsed by the Graphviz project.**

---

First functional v0.1.0a1 built with [Kimi K2.6](https://www.moonshot.cn/) in ~1h, single session (81% context used). Total cost: ~$1
