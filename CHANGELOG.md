# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.1.0a1]: https://github.com/pablormier/wasi-graphviz/releases/tag/v0.1.0a1
