# wasi-graphviz

Run Graphviz from Python via WebAssembly — no native Graphviz binary, no Node.js, no browser required.

## Why this exists

Rendering DOT graphs from Python sits in an awkward gap.

- **Browser-based WASM renderers** like
  [`@hpcc-js/wasm-graphviz`](https://github.com/hpcc-systems/hpcc-js-wasm)
  ship Graphviz as a WebAssembly module — but it's an Emscripten build
  wrapped in JavaScript glue, designed to run in a browser or Node.
  Tools like [easydot](https://github.com/pablormier/easydot) wrap that
  flow so you can call it from Python and display SVGs in a notebook,
  but the renderer itself still ultimately needs a JS runtime / browser
  surface to produce pixels — fine for interactive notebooks, awkward
  for headless static SVG generation in CI, batch jobs, or server-side
  pipelines.
- **System-binary Python wrappers** like `graphviz` and `pygraphviz`
  shell out to a system-installed `dot` or link against `libcgraph`.
  That means every deployment target — laptops, CI runners, Lambda
  functions, Docker base images — has to install Graphviz separately,
  and your code has to spawn subprocesses or manage shared-library
  loading.

`wasi-graphviz` plugs the gap: a `wasm32-wasi` build of upstream
Graphviz plus a thin Python wrapper. `pip install` is the entire
install story, the wheel is ~440 KB, and rendering happens entirely
in-process — no subprocesses, no system packages, no JS, no browser.
Works the same in a notebook, a CI job, a serverless function, or an
offline air-gapped environment.

The wheel itself does **not** include a WASM runtime — that's an
explicit choice (see [Installation](#installation) below) so you can
pick the runtime that matches your deployment constraints.

## Installation

`wasi-graphviz` needs a runtime to execute the bundled `graphviz.wasm`.
Two are supported, picked via extras:

```bash
# Recommended for most users — fast native runtime
pip install wasi-graphviz[wasmtime]

# Pure-Python runtime — slow, but works anywhere CPython does (not Pyodide)
pip install wasi-graphviz[pywasm]

# Install both — `render(..., backend="auto")` will prefer wasmtime
pip install wasi-graphviz[all]
```

### Choosing a backend

|                  | `wasmtime`                                | `pywasm`                              |
|------------------|-------------------------------------------|---------------------------------------|
| Implementation   | Native runtime (Rust) with Python bindings | Pure-Python WASM interpreter          |
| Speed            | ~0.3–7 ms per render (see below)          | ~3–130 s per render — *4–5 orders of magnitude slower* |
| Install size     | ~15 MB wheel (compiled extensions)        | ~200 KB wheel                         |
| Platforms        | Linux/macOS/Windows on x86_64 + arm64     | Anywhere CPython 3.11+ runs (see Pyodide note below) |
| Cold start       | Slightly heavier instantiation            | Fastest to import                     |
| Use when…        | Production, CI, notebooks, anything performance-sensitive | Last-resort portability — exotic CPU/OS, no-native-deps environments |

`backend="auto"` (the default) prefers `wasmtime` when available and
silently falls back to `pywasm`, so most code can ignore the
distinction. Force one explicitly when you have a reason — see
[Backend selection](#backend-selection) below.

> **Pyodide / marimo / WebAssembly-based Python environments**
>
> `pywasm` is pure-Python, but it imports `fcntl` (for stdin handling)
> which is **not available in Pyodide** because Pyodide itself runs
> inside a browser WebAssembly sandbox that lacks POSIX file-control
> APIs.
>
> Neither backend works in Pyodide today. A future
> `browser` / `pyodide` backend (using the browser's native
> `WebAssembly` object + a WASI polyfill) is possible, but not yet
> implemented.
>
> If you need Graphviz in a Pyodide or marimo notebook, use
> [`easydot`](https://github.com/pablormier/easydot) instead — it wraps
> the browser's `@hpcc-js/wasm` renderer and works out of the box in
> those environments.

#### Benchmarks

Median wall time per render on Apple M-series, Python 3.11, measured
via `pytest-benchmark` (run yourself with `uv run pytest
tests/test_benchmarks.py -m perf --benchmark-only`):

| Graph             | `wasmtime` | `pywasm`  | wasmtime speedup |
|-------------------|-----------:|----------:|-----------------:|
| 10 edges          |    0.29 ms |    3.7 s  |        ~12,800 × |
| 100 edges         |    1.74 ms |   32.5 s  |        ~18,700 × |
| 400 edges         |    6.86 ms |  133.3 s  |        ~19,400 × |

`pywasm` is a pure-Python WASM interpreter, so the ratio is roughly
"interpreted Python evaluating WASM bytecode" vs "native compiled
code" — expect orders of magnitude, not factors. Use `wasmtime`
unless your environment forbids native code.

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

See the [trade-off table](#choosing-a-backend) above for when to pick
which.

```python
from wasi_graphviz import render

# Auto-select (prefer wasmtime, fall back to pywasm)
svg = render("digraph G { a -> b; }", backend="auto")

# Force pywasm — pure Python, slow but maximally portable
svg = render("digraph G { a -> b; }", backend="pywasm")

# Force wasmtime — fast native runtime, requires compiled extension
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
# Run tests (perf benchmarks are skipped by default)
uv run pytest

# Format and lint
uv run ruff check .
uv run ruff format .

# Run benchmarks comparing wasmtime vs pywasm across graph sizes
uv run pytest tests/test_benchmarks.py -m perf --benchmark-only
```

## License & attribution

This package is licensed under the **Eclipse Public License 2.0**
(EPL-2.0). See [`LICENSE`](LICENSE) for the full text.

The wheel bundles a compiled build of [Graphviz](https://graphviz.org/)
(also EPL-2.0). The full EPL-2.0 text is also shipped inside the wheel at
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
