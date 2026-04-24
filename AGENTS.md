# AGENTS.md – wasi-graphviz

## 1. Project Overview

This project adapts the upstream `@hpcc-js/wasm` Graphviz build (located in `external/hpcc-js-wasm`) to produce a **standalone, WASI-compatible `graphviz.wasm`** that can be executed from Python using both **pywasm** and **wasmtime**.

The upstream build is deeply tied to Emscripten (`EM_ASM`, `embind`, JS glue). Our job is to:
1. Replace the Emscripten-specific C++ wrapper with a plain C API.
2. Re-target the build from Emscripten to a WASI toolchain (e.g. `wasi-sdk` or `zig cc`).
3. Provide Python backends that load and run the resulting `.wasm`.

## 2. Repository Layout

```
.
├── AGENTS.md               # This file
├── README.md               # Human-facing docs
├── pyproject.toml          # uv project configuration
├── .python-version         # CPython pin for uv
├── src/
│   └── wasi_graphviz/      # Main Python package
│       ├── __init__.py
│       ├── _constants.py   # Paths (EXTERNAL_DIR, DEFAULT_WASM_PATH, etc.)
│       ├── builder.py      # Build orchestration (downloads toolchain, compiles wasm)
│       ├── backends/
│       │   ├── __init__.py
│       │   ├── wasmtime_backend.py
│       │   └── pywasm_backend.py
│       └── assets/
│           └── graphviz.wasm   # Vendored WASM artifact shipped with the package
├── native/                 # Our plain-C wrapper + build files (gitignored)
│   ├── main.c
│   └── build.zig (or CMakeLists.txt)
├── scripts/                # One-off helper scripts
├── tests/                  # pytest suite
├── build/                  # Build artifacts (gitignored)
│   └── graphviz.wasm
└── external/               # Git submodule — upstream source ONLY
    └── hpcc-js-wasm/       # @hpcc-js/wasm monorepo (Emscripten build)
```

**Important:** `external/` is a **git submodule** pointing to the upstream repo. Do not modify files there. Our own code goes in `native/`, build outputs go in `build/`, and the final `.wasm` artifact that ships with the Python package goes in `src/wasi_graphviz/assets/`.

## 3. Tooling

| Purpose                | Tool | Notes |
|------------------------|------|-------|
| Python project & deps  | **uv** | `pyproject.toml` is the source of truth. Use `uv add`, `uv run`, `uv build`. |
| Non-Python build deps  | **pixi** (optional) | Can provision `zig`, `cmake`, `ninja`, `wasi-sdk`, etc. if the host lacks them. |
| WASM runtime (Python)  | **wasmtime** | Full WASI support; primary target. |
| WASM runtime (Python)  | **pywasm** | Pure-Python interpreter with **built-in WASI Preview 1 support** via `pywasm.wasi.Preview1`. |
| WASM build toolchain   | **zig** or **wasi-sdk** | Target `wasm32-wasi`. Prefer `zig` because it bundles libc and cross-compilation support. |

### Using pixi for build tools

If `zig` or `wasi-sdk` are not on the host `$PATH`, add them via `pixi`:

```bash
pixi init          # if pixi.toml does not yet exist
pixi add zig       # or pixi add wasi-sdk
pixi run zig --version
```

Python code that shells out to the toolchain should prefer `pixi run` or locate binaries via `shutil.which` inside the pixi env when available.

## 4. Build Strategy

### 4.1 Why the upstream WASM fails

The upstream `packages/graphviz/src-cpp/main.cpp` uses:
- `#include <emscripten.h>` and `EM_ASM` blocks for filesystem operations.
- `#include <emscripten/bind.h>` and `EMSCRIPTEN_BINDINGS` to expose a JS class API.
- Emscripten linker flags (`-sMODULARIZE`, `-sEXPORT_ES6`, `-lembind`, etc.).

This makes the resulting `.wasm` depend on Emscripten JS runtime imports (`env.emscripten_resize_heap`, `env._emscripten_throw_longjmp`, etc.) that neither `wasmtime` nor `pywasm` provide.

### 4.2 Adaptation steps

1. **Rewrite the C++ wrapper** into a plain C file with no Emscripten APIs (live in `native/main.c`):
   - Remove `EM_ASM`; use standard C memory/file buffers instead.
   - Remove `embind`; expose plain exported functions such as:
     ```c
     char* graphviz_render(const char* dot, const char* format, const char* engine);
     void graphviz_free(char* ptr);
     const char* graphviz_version(void);
     ```
   - Keep the existing Graphviz C library calls (`gvContextPlugins`, `agmemread`, `gvLayout`, `gvRenderData`, etc.).

2. **Create a WASI build script** (invoked from Python via `builder.py`):
   - Point at the Graphviz source installed by upstream vcpkg (or fetch it separately).
   - Compile the wrapper + required Graphviz libraries (`gvc`, `cgraph`, `cdt`, layout plugins, etc.) with `zig cc -target wasm32-wasi` or `clang` from `wasi-sdk`.
   - Link into a single `build/graphviz.wasm`.
   - Copy the validated artifact into `src/wasi_graphviz/assets/graphviz.wasm` for distribution.

3. **WASI considerations for pywasm**
   - `pywasm` provides a full `Preview1` WASI implementation (`pywasm.wasi.Preview1`).
   - The Python backend simply needs to instantiate `Preview1`, call `bind(runtime)`, and load the `.wasm`.
   - No manual stub-writing is required.

## 5. Python Code Conventions

- **Formatter / linter**: Use `ruff` (add via `uv add --dev ruff`).
- **Type hints**: All public functions must be typed.
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes.
- **Error handling**: Raise domain-specific exceptions (`WasiGraphvizError`) rather than returning `None`.
- **Constants**: Keep paths and magic strings in `_constants.py`.

## 6. Testing

- Unit tests live in `tests/` and are run with `uv run pytest`.
- Each backend must have at least one integration test that renders a simple DOT graph (e.g. `digraph G { a -> b; }`) to SVG.
- CI (if added later) should build the `.wasm` before running tests.

## 7. Known Pitfalls

### NEVER make hand-edited patches to upstream source code
**This is the most important rule.** Upstream code (e.g., Graphviz source downloaded for building) must remain untouched. Do not open individual `.c` or `.cpp` files and edit them by hand to fix build errors.

**Why:** Hand-edited patches are unmaintainable. When a new version of Graphviz is released, every manual edit must be rediscovered and reapplied. This is error-prone and wastes time.

**What to do instead:**
- Use **compiler flags** (e.g., `-D_WASI_EMULATED_SIGNAL`) and **stub headers** (e.g., `native/wasi_stubs.h` injected via `-include`) to work around missing POSIX functions.
- Use **automated scripts** (e.g., `scripts/prepare_graphviz_wasi.py`) that apply pattern-based transforms to the source tree before CMake configure. The script should be documented and reproducible.
- If CMake options can disable a problematic feature, use those first.

If you find yourself editing a third-party source file, stop and ask: "Can I fix this with a compiler flag, a stub header, or an automated script instead?"

### Do not run `pixi init`
`pixi init` requires a TTY and fails in non-interactive environments. Write `pixi.toml` directly instead.

### `wasm-tools` is not in conda-forge
The `wabt` package provides `wasm-objdump`, `wasm2wat`, etc. Use that instead.

### `zig cc` for wasm32-wasi expects `main()`
The bundled libc startup code references `main()`. A dummy `int main(void) { return 0; }` may be needed. For a true "reactor" (no `_start`), avoid linking libc startup files or use `zig build-exe -fno-entry` (but this may not find headers).

### `pywasm` HAS built-in WASI support
Do not assume manual WASI stub-writing is required. Use `pywasm.wasi.Preview1` and call `bind(runtime)` before loading the module.

### wasmtime `Memory.read(store, start, stop)` uses slice semantics
To read 1 byte at address `i`, use `mem.read(store, i, i + 1)`, not `mem.read(store, i, 1)`.

### Use `uv run` consistently
`uv run` manages its own virtual environment. Do not assume `.venv` persists across commands.

## 8. Quick Start for Agents

1. Read the current state of `external/hpcc-js-wasm/packages/graphviz/src-cpp/main.cpp` to understand the upstream wrapper.
2. Check `builder.py` for existing build orchestration logic.
3. When adding new Python files, run `uv run ruff check .` and `uv run ruff format .`.
4. When modifying the build, prefer idempotent operations (e.g. check if `build/graphviz.wasm` already exists before recompiling).
5. Keep the upstream source in `external/hpcc-js-wasm/` untouched except for files we explicitly copy/generate (so upstream can be updated easily).
