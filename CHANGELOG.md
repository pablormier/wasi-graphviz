# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2026-05-01

### Changed
- Improved building stage and CI for auto pull requests.

## [0.1.0] - 2026-04-28

### Added
- First non-alpha release of `wasi-graphviz`.
- Stable `0.1.0` package metadata and release workflow support for tagging and publishing `v0.1.0`.

## [0.1.0a2] - 2026-04-25

### Fixed
- **Output truncation at 64 KB.** Both backends previously scanned the WASM
  return buffer byte-by-byte for a NUL terminator, capped at `max_len=65536`,
  silently truncating any larger render. The C ABI now returns an explicit
  byte count (`size_t* out_len`); the Python backends do a single bulk read
  of exactly that many bytes. Binary-format-safe and ~50× faster on large
  graphs.

### Changed
- **C ABI:** `graphviz_render(dot, format, engine)` →
  `graphviz_render(dot, format, engine, size_t* out_len)`. The returned
  buffer is no longer NUL-terminated; the caller reads `*out_len` bytes.
- **WASM artifact size: 5.8 MB → 1.04 MB (82% reduction).** Build pipeline
  now runs `wasm-strip` (drops DWARF debug sections) followed by
  `wasm-opt -Oz` after linking.
- **Initial WASM memory: 259 → 35 pages** via
  `-Wl,-z,stack-size=2097152` (2 MB stack instead of 16 MB). Faster
  instantiation and lower RSS.
- `scripts/build_wasm.py` now performs the full build end-to-end and is
  what `pixi run build-wasm` invokes; previous prose-only `BUILD.md`
  steps are kept as documentation.
- `_constants.py` no longer exposes build-tree paths (`PROJECT_ROOT`,
  `EXTERNAL_DIR`, `NATIVE_DIR`, `BUILD_DIR`, `DEFAULT_WASM_PATH`) that
  were meaningless inside an installed wheel. Only `PACKAGE_WASM_PATH`
  and `ASSETS_DIR` remain.

### Added
- License & attribution: `NOTICE` file at repo root, EPL-2.0 text bundled
  with the wheel as `wasi_graphviz/assets/GRAPHVIZ_LICENSE`, SPDX header
  on `scripts/prepare_graphviz_wasi.py` (the script's transforms are
  EPL-2.0 modifications of the Graphviz source).
- `pyproject.toml` metadata: `license = "EPL-2.0"`,
  `license-files = ["LICENSE", "NOTICE"]`, keywords, and trove
  classifiers.
- Tests: `test_large_graph` (regression for the 64 KB cap),
  `test_formats` (svg/dot/xdot/json/plain matrix per backend),
  `test_backends_agree` (byte-identical output between wasmtime and
  pywasm), `test_packaging` (vendored `graphviz.wasm` is opened via
  `importlib.resources`). Suite is now 26 tests.
- `binaryen` added to `pixi.toml` for `wasm-opt`.
- `pytest-benchmark` integration: `tests/test_benchmarks.py` compares
  `wasmtime` vs `pywasm` across 10 / 100 / 400 edge graphs. Skipped by
  default; opt in with `pytest -m perf --benchmark-only`. README now
  carries published numbers (wasmtime ~0.3–7 ms vs pywasm ~3–130 s,
  i.e. ~10⁴–10⁵× slower).
- New `test.yml` GitHub Actions workflow runs ruff and pytest on
  push/PR across Python 3.11/3.12/3.13 and ubuntu/macos.

### Removed
- `_memory.py` (dead module — its `MemoryLike` protocol matched neither
  backend and nothing imported it).

## [0.1.0a1] - 2026-04-24

### Added
- First alpha release.
- Graphviz 14.1.5 compiled to `wasm32-wasi` (~6 MB `graphviz.wasm`).
- Plain C ABI wrapper exposing `graphviz_render`, `graphviz_free`, `graphviz_last_error`, `graphviz_version`.
- `PywasmBackend` — pure-Python backend using `pywasm` with built-in WASI Preview 1 support.
- `WasmtimeBackend` — fast optional backend using `wasmtime`.
- `render()` public API with `backend="auto"` (prefers `wasmtime`, falls back to `pywasm`).
- Support for all major layout engines: `dot`, `neato`, `circo`, `fdp`, `sfdp`, `twopi`, `osage`, `patchwork`.
- SVG output format (core plugin).
- Maintainable build system using `zig cc` for `wasm32-wasi` cross-compilation.
- Zero hand-edited Graphviz source patches — fixes applied via compiler flags, stub headers, CMake options, and automated preparation scripts.
- `pixi` build environment for reproducible builds.
- `BUILD.md` documenting the full build pipeline.

[0.1.0a2]: https://github.com/pablormier/wasi-graphviz/releases/tag/v0.1.0a2
[0.1.0a1]: https://github.com/pablormier/wasi-graphviz/releases/tag/v0.1.0a1
[0.1.0]: https://github.com/pablormier/wasi-graphviz/releases/tag/v0.1.0
