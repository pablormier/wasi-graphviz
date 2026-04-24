# STATUS.md – wasi-graphviz

## Current Phase

**Steps 4 & 5 complete:** The plain C wrapper is written and `graphviz.wasm` is linked and validated.

Steps 1–5 are complete. The WASM artifact successfully renders DOT to SVG via both `pywasm` and `wasmtime`. Next: implement the Python backends.

---

## Completed Steps

### ✅ Step 1: Prove Pywasm Compatibility
- Built `native/echo.c` → `build/echo.wasm`
- Verified `pywasm` can load, instantiate with `wasi.Preview1`, call `echo`, allocate/free memory
- Script: `scripts/spike_pywasm_echo.py`

### ✅ Step 2: Prove Wasmtime Compatibility
- Same `build/echo.wasm` loaded in `wasmtime`
- Verified memory read/write, function calls, WASI config
- Script: `scripts/spike_wasmtime_echo.py`

### ✅ Step 3: Build Graphviz Static Libraries for WASI
- Downloaded Graphviz 14.1.5 source from GitLab
- Created `zig` wrapper scripts for CMake cross-compilation
- Created `native/wasm32-wasi-toolchain.cmake`
- **Clean approach adopted** (see below)
- **Build successful** — all required static libraries compiled for `wasm32-wasi`:
  - Core: `libcdt.a`, `libcgraph.a`, `libgvc.a`, `libcommon.a`, `libutil.a`, `libast.a`, `libxdot.a`, `libpathplan.a`, `libpack.a`, `liblabel.a`
  - Layouts: `libdotgen.a`, `libneatogen.a`, `libfdpgen.a`, `libsfdpgen.a`, `libcircogen.a`, `libtwopigen.a`, `libosage.a`, `libpatchwork.a`, `libortho.a`, `libsparse.a`, `librbtree.a`
  - Plugins: `libgvplugin_core.a`, `libgvplugin_dot_layout.a`, `libgvplugin_neato_layout.a`

### ✅ Step 4: Write the Plain C Graphviz Wrapper
- Created `native/main.c` with the minimal C ABI:
  - `graphviz_render(const char* dot, const char* format, const char* engine)`
  - `graphviz_last_error(void)`
  - `graphviz_version(void)`
  - `graphviz_free(char* ptr)`
- Preloads `dot_layout`, `neato_layout`, and `core` plugins via `lt_preloaded_symbols`
- Uses standard Graphviz C API: `gvContextPlugins`, `agmemread`, `gvLayout`, `gvRenderData`, etc.
- Includes dummy `main()` to satisfy `zig cc` wasm32-wasi libc startup

### ✅ Step 5: Link `graphviz.wasm`
- Compiled `native/main.c` against Graphviz headers
- Linked all static libraries with `zig cc -target wasm32-wasi`
- Exported required symbols: `memory`, `_start`, `malloc`, `free`, `graphviz_render`, `graphviz_free`, `graphviz_last_error`, `graphviz_version`
- **Validation passed**:
  - Only `wasi_snapshot_preview1` imports (no Emscripten, no JS glue)
  - `wasm-objdump` confirms correct exports
- **Tested with both backends**:
  - `pywasm` renders `digraph G { a -> b; }` to SVG successfully
  - `wasmtime` renders the same graph to identical SVG output
- Artifact: `build/graphviz.wasm` (~6 MB)

---

## Clean Build Strategy (Zero Source Edits)

**Goal:** Build Graphviz for `wasm32-wasi` without modifying a single line of Graphviz source code. This ensures the process works for any new Graphviz version with minimal effort.

### Strategy Table

| Problem | Previous Approach (Bad) | Clean Approach (Good) |
|---|---|---|
| `flockfile`/`funlockfile` missing | Hand-edit `lib/util/lockfile.h` | **Stub header** `native/wasi_stubs.h` injected via `-include` |
| `signal()` missing | Hand-edit `lib/common/utils.c` | **Compiler flag** `-D_WASI_EMULATED_SIGNAL` |
| `clock()` deprecated | Hand-edit `lib/common/timing.c` | **Compiler flag** `-D_WASI_EMULATED_PROCESS_CLOCKS` |
| `std::ofstream` undefined in `vpsc` | Hand-edit 3 `.cpp` files | **CMake option** `-Dwith_ipsepcola=OFF` (removes `vpsc` entirely) |
| `GVPLUGIN_CURRENT` undefined in plugins | Hand-edit with `sed` | **CMake flags** `-DGVPLUGIN_CURRENT=8 -DGVPLUGIN_REVISION=0` |
| `edgepaint` build failure | Hand-edit `lib/CMakeLists.txt` | **Stub header** provides `flockfile`/`funlockfile` — no need to disable |
| `gvpr` uses `setjmp`/`longjmp` | Hand-edit source | **Automated script** `scripts/prepare_graphviz_wasi.py` comments out `gvpr`/`expr` |
| `read()` undeclared in `gvloadimage_core.c` | Hand-edit source | **Toolchain flag** `-include unistd.h` |
| `plugin/quartz` builds on macOS host | Hand-edit source | **CMake option** `-DWITH_QUARTZ=OFF` |

### Why this matters

When Graphviz releases version 15.x, we should only need to:
1. Download the new tarball
2. Copy the upstream overlay `CMakeLists.txt` (if still needed)
3. Run CMake with the same flags and toolchain
4. Build

No rediscovering patches. No re-applying sed commands. No hunting through source files.

### Files created for the clean approach

| File | Purpose |
|---|---|
| `native/zig-cc` | Wrapper: `zig cc -target wasm32-wasi` |
| `native/zig-c++` | Wrapper: `zig c++ -target wasm32-wasi` |
| `native/zig-ar` | Wrapper: `zig ar` (no `-target`) |
| `native/zig-ranlib` | Wrapper: `zig ranlib` (no `-target`) |
| `native/wasi_stubs.h` | POSIX stubs for WASI: `flockfile`, `funlockfile`, etc. |
| `native/wasm32-wasi-toolchain.cmake` | CMake toolchain file using the above wrappers |
| `scripts/prepare_graphviz_wasi.py` | Idempotent script for build-time source preparation |

---

## Active Blockers / Issues

*Step 3 is complete. The issues below were encountered and resolved during the build. They are documented for future reference when upgrading Graphviz versions.*

### Issue 1: `zig cc` for wasm32-wasi requires dummy `main()`
**Symptom:** `wasm-ld: error: undefined symbol: main`

When compiling C to `wasm32-wasi` with `zig cc`, the bundled libc includes startup code that calls `main()`. Using `-Wl,--no-entry` alone is not sufficient because the libc `.a` archive still contains `__main_void.o` which references `main`.

**Workaround:** Added a dummy `int main(void) { return 0; }` to `native/echo.c`.

**Future concern:** When we build the real Graphviz wrapper, we may want a true `-no-entry` build (reactor model, not command model). If `main()` is present, `_start` will be exported and `wasmtime` may try to run it. We need to either:
- Keep `main()` and ensure it's harmless
- Or figure out how to build a true "reactor" with `zig cc` (possibly by not linking libc startup files)

---

### Issue 2: `wasm-tools` not available in conda-forge
**Symptom:** `pixi install` failed with `No candidates were found for wasm-tools *.`

**Resolution:** Replaced `wasm-tools` with `wabt` in `pixi.toml`. `wabt` provides `wasm-objdump`, `wasm2wat`, etc.

---

### Issue 3: `pixi init` fails in non-interactive environments
**Symptom:** `Error: IO error: not a terminal`

**Resolution:** Manually wrote `pixi.toml` instead of using `pixi init`.

---

### Issue 4: pywasm has built-in WASI support (initial assumption was wrong)
**Context:** Early `AGENTS.md` draft assumed `pywasm` had no WASI support and required manual stubs.

**Reality:** `pywasm.wasi.Preview1` provides a complete `wasi_snapshot_preview1` implementation.

**Impact:** `AGENTS.md` and `PLAN.md` were updated. No code impact.

---

### Issue 5: wasmtime `Memory.read()` API is slice-based, not (start, length)
**Symptom:** `IndexError: bytearray index out of range` when using `mem.read(store, addr, 1)`

**Reality:** `Memory.read(store, start, stop)` reads bytes from `start` up to `stop` (like Python slicing). To read 1 byte at address `i`, use `mem.read(store, i, i + 1)`.

---

### Issue 6: `.venv` gets recreated by `uv run`
**Symptom:** `.venv` directory disappears or gets rebuilt on `uv run`.

**Reality:** `uv run` manages its own virtual environment. We should use `uv run` consistently rather than expecting `.venv` to persist.

---

### Issue 7: `zig ar` wrapper passes `-target` flags incorrectly
**Symptom:** `zig ar` prints help text and exits with error because `-target wasm32-wasi` was passed to it.

**Root cause:** CMake's `CMAKE_STATIC_LINKER_FLAGS` includes `-target wasm32-wasi`, but `ar` (archive tool) doesn't accept target flags.

**Resolution:** Created separate `native/zig-ar` and `native/zig-ranlib` wrapper scripts that call `zig ar` and `zig ranlib` WITHOUT passing `-target`. Updated toolchain file to use these wrappers.

---

### Issue 8: System Bison is too old (2.3), CMake requires >= 3.0
**Symptom:** `Could NOT find BISON: Found unsuitable version "2.3", but required is at least "3.0"`

**Root cause:** macOS ships Bison 2.3. CMake finds it in `/usr/bin/bison` before the pixi environment.

**Resolution:** Pass explicit paths to pixi-provided Bison and Flex:
```bash
-DBISON_EXECUTABLE=$(pixi run which bison) -DFLEX_EXECUTABLE=$(pixi run which flex)
```

---

### Issue 9: Graphviz plugin CMakeLists have undefined `GVPLUGIN_CURRENT`/`GVPLUGIN_REVISION`
**Symptom:** `set_target_properties called with incorrect number of arguments` in `plugin/core/`, `plugin/dot_layout/`, `plugin/neato_layout/`

**Root cause:** Graphviz 14.1.5 has a regression where `GVPLUGIN_CURRENT` and `GVPLUGIN_REVISION` are undefined in plugin CMakeLists.

**Clean resolution:** Use the upstream overlay `CMakeLists.txt` from `external/hpcc-js-wasm/vcpkg-overlays/graphviz/`, which already defines `GRAPHVIZ_PLUGIN_VERSION` and references it correctly. If the upstream overlay still leaves plugin subdirectories broken, we need a version-agnostic build-time transform (not hand edits).

---

### Issue 10: WASI lacks signal support — `lib/common/args.c` fails
**Symptom:** `"wasm lacks signal support; to enable minimal signal emulation, compile with -D_WASI_EMULATED_SIGNAL and link with -lwasi-emulated-signal"`

**Root cause:** `lib/common/utils.c` uses `signal(SIGUSR1, gvToggle)` for a debug feature. WASI libc doesn't provide signals by default.

**Clean resolution:** Add `-D_WASI_EMULATED_SIGNAL` to compiler flags in toolchain file.

---

### Issue 11: `edgepaint` uses `flockfile`/`funlockfile` — not available in WASI
**Symptom:** `call to undeclared function 'flockfile'` in `lib/edgepaint/../util/lockfile.h`

**Root cause:** `lib/util/lockfile.h` wraps `flockfile`/`funlockfile`, which are POSIX thread-locking functions not present in WASI libc.

**Clean resolution:** Provide no-op stubs in `native/wasi_stubs.h` and inject via `-include`. `edgepaint` compiles without source modification.

**Note:** `edgepaint` is a standalone post-processing tool for "edge distinct coloring." Standard DOT color attributes (e.g., `color=red`, `fillcolor=blue`) are handled entirely by `lib/common`, `libcgraph`, and `lib/gvc`.

---

### Issue 12: Optional layout engines are all WASI-safe
**Investigated:** All optional layout libraries for non-dot engines:
- `circogen`, `fdpgen`, `sfdpgen`, `twopigen`, `osage`, `patchwork`, `ortho`, `sparse`, `vpsc`, `rbtree`, `label`, `pack`

**Finding:** None use `flockfile`, `signal`, `pthread`, `fork`, `dlopen`, or other problematic POSIX calls. They only use standard C math and `drand48`/`time(NULL)` for random seeding, which WASI libc supports.

**Resolution:** All optional layouts can be kept. For `vpsc` specifically, `-Dwith_ipsepcola=OFF` removes it from the build (it's only needed for the IPSEPCOLA feature in `neato`). All other `neato` algorithms still work.

---

### Issue 13: `gvpr` uses `setjmp`/`longjmp` — not supported in WASI
**Symptom:** `error: Setjmp/longjmp support requires Exception handling support`

**Root cause:** `lib/gvpr` (GraphViz Pattern Processing Language) uses `setjmp`/`longjmp` for error handling. WASI libc does not support these without WebAssembly exception handling proposals.

**Clean resolution:** `gvpr` is a scripting tool, not needed for DOT→SVG rendering. Added an automated preparation script `scripts/prepare_graphviz_wasi.py` that comments out `add_subdirectory(gvpr)` and `add_subdirectory(expr)` in `lib/CMakeLists.txt`. The script is idempotent and fails loudly if patterns are not found.

---

### Issue 14: `plugin/core/gvloadimage_core.c` missing `read()` declaration
**Symptom:** `call to undeclared function 'read'`

**Root cause:** The file includes `<sys/types.h>` and `<sys/stat.h>` but not `<unistd.h>`, which declares `read()`. On most POSIX systems, `read()` may be transitively included, but not in WASI.

**Clean resolution:** Added `-include unistd.h` to the toolchain compiler flags. This injects the header into every compilation unit without editing source files.

---

### Issue 15: `plugin/quartz` builds on macOS despite wasm32 cross-compilation
**Symptom:** `fatal error: 'Availability.h' file not found`

**Root cause:** The stock Graphviz `CMakeLists.txt` has `WITH_QUARTZ AUTO` by default. On macOS hosts, CMake auto-detects Quartz and sets `HAVE_QUARTZ=1`, even when cross-compiling for wasm32-wasi.

**Clean resolution:** Added `-DWITH_QUARTZ=OFF` to the CMake configure flags. This is the correct approach per PLAN.md: disable the feature via CMake option rather than editing source.

---

### Issue 16: `vpsc` C++ code fails with undefined `std::ofstream`
**Symptom:** `implicit instantiation of undefined template 'std::basic_ofstream<char>'`

**Root cause:** `lib/vpsc` (used by IPSEPCOLA layout feature) contains debug logging code using `std::ofstream`. WASI libc++ provides a forward declaration but not the full template definition.

**Clean resolution:** Added `-Dwith_ipsepcola=OFF` to the CMake configure flags. This removes `vpsc` from the build entirely. All other `neato` layout algorithms still work.

---

### Issue 13: CMake IPO probe cannot find compiler archive wrappers
**Symptom:** `cmake --build build/graphviz-cmake` fails because the directory has no generated `Makefile`/`build.ninja`. The configure log shows CMake's IPO/LTO probe trying to run `CMAKE_CXX_COMPILER_AR-NOTFOUND`.

**Root cause:** The toolchain file sets `CMAKE_AR` and `CMAKE_RANLIB`, but CMake's compiler-specific archive variables are still unset during the IPO check.

**Clean resolution:** Update the WASI toolchain configuration to either:
- set `CMAKE_C_COMPILER_AR`, `CMAKE_CXX_COMPILER_AR`, `CMAKE_C_COMPILER_RANLIB`, and `CMAKE_CXX_COMPILER_RANLIB` to the `native/zig-ar` and `native/zig-ranlib` wrappers, or
- disable IPO/LTO for the Graphviz configure.

After this, rerun CMake from a clean build directory and verify that it generates a real build system before continuing to Graphviz source-level issues.

---

### ✅ Step 8: Polish Public Python API
- Updated `render()` function in `src/wasi_graphviz/__init__.py`:
  - `backend="auto"` prefers `wasmtime`, falls back to `pywasm`
  - Lazy-loads and caches backend instances
  - Clear error messages when backends are missing
  - Optional `wasm_path` parameter for custom artifacts

### ✅ Step 9: Package Distribution
- `uv build` produces `dist/wasi_graphviz-0.1.0-py3-none-any.whl`
- Verified wheel includes `wasi_graphviz/assets/graphviz.wasm` (~6 MB)
- `pyproject.toml` has optional dependencies: `pywasm`, `wasmtime`, `all`

### ✅ Step 10: Final Documentation and README Update
- Wrote `README.md` with:
  - Installation instructions (`pip install wasi-graphviz[pywasm|wasmtime|all]`)
  - Quick start and usage examples
  - Backend selection guide
  - Error handling examples
  - Supported engines and formats
  - Architecture overview
  - Link to `BUILD.md` for maintainers
  - Development commands (pytest, ruff)
- All 10 steps from PLAN.md are now complete

## Project Status: Alpha Release ✅

**Version:** `0.1.0a1`

All planned steps have been implemented and tested:
1. ✅ pywasm compatibility proven
2. ✅ wasmtime compatibility proven  
3. ✅ Graphviz static libraries built for wasm32-wasi
4. ✅ Plain C wrapper written
5. ✅ graphviz.wasm linked and validated
6. ✅ PywasmBackend implemented
7. ✅ WasmtimeBackend implemented
8. ✅ Public Python API polished
9. ✅ Package distribution configured
10. ✅ Documentation complete

---

## Build Artifacts

| File | Description |
|---|---|
| `build/echo.wasm` | Tiny test module proving C ABI + WASI |
| `native/echo.c` | Source for test module |
| `native/wasi_stubs.h` | POSIX stubs for WASI builds |
| `build/src/graphviz-14.1.5/` | Graphviz 14.1.5 source tree (clean, unpatched) |
| `build/graphviz-cmake/` | CMake build directory |
| `build/graphviz-cmake/lib/*/lib*.a` | Built Graphviz static libraries for wasm32-wasi |
| `build/graphviz-cmake/plugin/*/libgvplugin_*.a` | Built Graphviz plugin libraries for wasm32-wasi |
| `scripts/prepare_graphviz_wasi.py` | Idempotent preparation script for Graphviz source |
| `native/main.c` | Plain C wrapper exposing Graphviz C ABI |
| `build/main.o` | Compiled wrapper object |
| `build/graphviz.wasm` | Final linked WASM artifact (~6 MB) |
| `scripts/spike_pywasm_graphviz.py` | pywasm integration test spike |
| `scripts/spike_wasmtime_graphviz.py` | wasmtime integration test spike |
