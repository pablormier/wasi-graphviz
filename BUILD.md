# BUILD.md – Building graphviz.wasm

This document describes how to build the `graphviz.wasm` artifact from source. It is designed to be automated in CI (e.g. GitHub Actions).

## Prerequisites

The build requires:

- **pixi** — for provisioning build tools (zig, cmake, bison, flex, wabt)
- **uv** — for Python virtual environment management (already used by the project)

Install pixi: https://pixi.sh/latest/

## One-time setup

```bash
# Install build tools via pixi
pixi install

# Verify tools
pixi run zig version      # should print e.g. 0.15.2
pixi run cmake --version  # should print >= 3.14
pixi run bison --version  # should print >= 3.8
pixi run flex --version   # should print >= 2.6
```

## Build command

The normal build is:

```bash
pixi install
pixi run build-wasm
```

This downloads Graphviz 14.1.5 when needed, prepares the source tree, configures
CMake for `wasm32-wasi`, builds the static libraries, links `build/graphviz.wasm`,
validates the exports/imports, and copies the artifact to
`src/wasi_graphviz/assets/graphviz.wasm`.

Useful options:

```bash
# Re-extract source and recreate the CMake build directory
pixi run build-wasm --force

# Use an existing build/src/graphviz-14.1.5 source tree; do not download
pixi run build-wasm --skip-download
```

## Manual build steps

The scripted task above follows these steps.

### 1. Download Graphviz source

```bash
GRAPHVIZ_VERSION="14.1.5"
mkdir -p build/src
curl -L -o build/src/graphviz.tar.gz \
  "https://gitlab.com/graphviz/graphviz/-/archive/${GRAPHVIZ_VERSION}/graphviz-${GRAPHVIZ_VERSION}.tar.gz"
cd build/src && tar xzf graphviz.tar.gz
```

The source will be extracted to `build/src/graphviz-${GRAPHVIZ_VERSION}/`.

### 2. Prepare the source for wasm32-wasi

Some Graphviz components are incompatible with WASI (e.g. `gvpr` uses `setjmp`/`longjmp`). We apply deterministic, version-tolerant transforms via a Python script rather than hand-editing files.

```bash
python scripts/prepare_graphviz_wasi.py build/src/graphviz-${GRAPHVIZ_VERSION}
```

This script is idempotent — it can be run multiple times safely.

### 3. Configure with CMake

We use a custom toolchain file (`native/wasm32-wasi-toolchain.cmake`) that wraps `zig` for cross-compilation to `wasm32-wasi`.

```bash
pixi run cmake \
  -S build/src/graphviz-${GRAPHVIZ_VERSION} \
  -B build/graphviz-cmake \
  -DCMAKE_TOOLCHAIN_FILE=$(pwd)/native/wasm32-wasi-toolchain.cmake \
  -DBISON_EXECUTABLE=$(pixi run which bison) \
  -DFLEX_EXECUTABLE=$(pixi run which flex) \
  -DGVPLUGIN_CURRENT=8 \
  -DGVPLUGIN_REVISION=0 \
  -DENABLE_LTDL=OFF \
  -DWITH_EXPAT=OFF \
  -DWITH_GVEDIT=OFF \
  -DWITH_SMYRNA=OFF \
  -DWITH_ZLIB=OFF \
  -Duse_win_pre_inst_libs=OFF \
  -DBUILD_SHARED_LIBS=OFF \
  -DENABLE_TCL=OFF \
  -DENABLE_SWIG=OFF \
  -DENABLE_SHARP=OFF \
  -DENABLE_D=OFF \
  -DENABLE_GO=OFF \
  -DENABLE_JAVASCRIPT=OFF \
  -DGRAPHVIZ_CLI=OFF \
  -DWITH_GDK=OFF \
  -DWITH_GTK=OFF \
  -DWITH_POPPLER=OFF \
  -DWITH_RSVG=OFF \
  -DWITH_WEBP=OFF \
  -DWITH_QUARTZ=OFF \
  -DWITH_X=OFF \
  -DENABLE_GUILE=OFF \
  -DENABLE_JAVA=OFF \
  -DENABLE_LUA=OFF \
  -DENABLE_PERL=OFF \
  -DENABLE_PHP=OFF \
  -DENABLE_PYTHON=OFF \
  -DENABLE_R=OFF \
  -DENABLE_RUBY=OFF \
  -Dwith_ipsepcola=OFF \
  -Dwith_cxx_api=OFF \
  -Dwith_cxx_tests=OFF \
  -DCMAKE_BUILD_TYPE=Release
```

#### Why these flags?

| Flag | Reason |
|------|--------|
| `-DCMAKE_TOOLCHAIN_FILE=...` | Cross-compiles to wasm32-wasi using zig |
| `-DGVPLUGIN_CURRENT=8 -DGVPLUGIN_REVISION=0` | Fixes Graphviz 14.1.5 plugin version regression |
| `-DBUILD_SHARED_LIBS=OFF` | Static libraries only |
| `-Dwith_ipsepcola=OFF` | Removes `vpsc` C++ code with WASI-incompatible `std::ofstream` |
| `-DWITH_QUARTZ=OFF` | Prevents macOS host from auto-building Quartz plugin |
| `-DENABLE_*=OFF` | Disables CLI tools, language bindings, GUI components |
| `-DWITH_*=OFF` | Disables optional renderers (GD, Pango, Cairo, etc.) |
| `-D_WASI_EMULATED_SIGNAL` | Enables signal emulation for debug code in `lib/common` |
| `-D_WASI_EMULATED_PROCESS_CLOCKS` | Enables `clock()` emulation for timing code |
| `-include native/wasi_stubs.h` | Injects no-op `flockfile`/`funlockfile` stubs |
| `-include unistd.h` | Ensures `read()` is declared everywhere |

### 4. Build static libraries

```bash
pixi run cmake --build build/graphviz-cmake --parallel
```

This produces static libraries under `build/graphviz-cmake/lib/` and `build/graphviz-cmake/plugin/`.

### 5. Compile the C wrapper

```bash
pixi run zig cc -target wasm32-wasi -O2 \
  -D_WASI_EMULATED_SIGNAL \
  -I"$(pwd)/build/src/graphviz-${GRAPHVIZ_VERSION}/lib/gvc" \
  -I"$(pwd)/build/src/graphviz-${GRAPHVIZ_VERSION}/lib/cgraph" \
  -I"$(pwd)/build/src/graphviz-${GRAPHVIZ_VERSION}/lib/cdt" \
  -I"$(pwd)/build/src/graphviz-${GRAPHVIZ_VERSION}/lib/common" \
  -I"$(pwd)/build/src/graphviz-${GRAPHVIZ_VERSION}/lib/pathplan" \
  -I"$(pwd)/build/src/graphviz-${GRAPHVIZ_VERSION}/lib/util" \
  -I"$(pwd)/build/src/graphviz-${GRAPHVIZ_VERSION}/lib/ast" \
  -I"$(pwd)/build/src/graphviz-${GRAPHVIZ_VERSION}/lib/xdot" \
  -I"$(pwd)/build/src/graphviz-${GRAPHVIZ_VERSION}/lib/pack" \
  -I"$(pwd)/build/src/graphviz-${GRAPHVIZ_VERSION}/lib/label" \
  -I"$(pwd)/build/src/graphviz-${GRAPHVIZ_VERSION}/lib/neatogen" \
  -I"$(pwd)/build/graphviz-cmake" \
  -c native/main.c -o build/main.o
```

### 6. Link the final `.wasm`

Create a response file listing all libraries (to avoid command-line length limits):

```bash
cat > build/link_libs.txt << 'EOF'
build/graphviz-cmake/plugin/core/libgvplugin_core.a
build/graphviz-cmake/plugin/dot_layout/libgvplugin_dot_layout.a
build/graphviz-cmake/plugin/neato_layout/libgvplugin_neato_layout.a
build/graphviz-cmake/plugin/vt/libgvplugin_vt.a
build/graphviz-cmake/lib/dotgen/libdotgen.a
build/graphviz-cmake/lib/neatogen/libneatogen.a
build/graphviz-cmake/lib/fdpgen/libfdpgen.a
build/graphviz-cmake/lib/sfdpgen/libsfdpgen.a
build/graphviz-cmake/lib/twopigen/libtwopigen.a
build/graphviz-cmake/lib/circogen/libcircogen.a
build/graphviz-cmake/lib/osage/libosage.a
build/graphviz-cmake/lib/patchwork/libpatchwork.a
build/graphviz-cmake/lib/ortho/libortho.a
build/graphviz-cmake/lib/sparse/libsparse.a
build/graphviz-cmake/lib/gvc/libgvc.a
build/graphviz-cmake/lib/common/libcommon.a
build/graphviz-cmake/lib/pack/libpack.a
build/graphviz-cmake/lib/label/liblabel.a
build/graphviz-cmake/lib/xdot/libxdot.a
build/graphviz-cmake/lib/pathplan/libpathplan.a
build/graphviz-cmake/lib/cgraph/libcgraph.a
build/graphviz-cmake/lib/cdt/libcdt.a
build/graphviz-cmake/lib/util/libutil.a
build/graphviz-cmake/lib/ast/libast.a
build/graphviz-cmake/lib/rbtree/librbtree.a
build/graphviz-cmake/lib/sfio/libsfio.a
build/graphviz-cmake/lib/edgepaint/libedgepaintlib.a
EOF

pixi run zig cc -target wasm32-wasi -O2 \
  -Wl,-z,stack-size=2097152 \
  -Wl,--export=graphviz_render \
  -Wl,--export=graphviz_free \
  -Wl,--export=graphviz_last_error \
  -Wl,--export=graphviz_version \
  -Wl,--export=malloc \
  -Wl,--export=free \
  -o build/graphviz.wasm \
  build/main.o \
  @build/link_libs.txt
```

### 7. Strip and optimize

Remove DWARF debug sections and run `wasm-opt -Oz` to shrink the artifact
(typical reduction: ~5.8 MB → ~800 KB).

```bash
pixi run wasm-strip build/graphviz.wasm
pixi run wasm-opt -Oz --strip-producers build/graphviz.wasm -o build/graphviz.wasm
```

### 8. Validate the artifact

```bash
# Inspect imports/exports
pixi run wasm-objdump -x build/graphviz.wasm

# Verify only WASI Preview 1 imports are present
pixi run wasm-objdump -x build/graphviz.wasm | grep -c "wasi_snapshot_preview1"

# Verify key exports are present
for sym in graphviz_render graphviz_free graphviz_last_error graphviz_version malloc free; do
  pixi run wasm-objdump -x build/graphviz.wasm | grep -q "${sym}" || echo "MISSING: ${sym}"
done
```

Expected: only `wasi_snapshot_preview1.*` imports, no Emscripten imports.

### 9. Copy to package assets

```bash
cp build/graphviz.wasm src/wasi_graphviz/assets/graphviz.wasm
```

## Compatibility layers used (in order of preference)

Per PLAN.md, we fix WASI build issues using this hierarchy:

1. **CMake options** — disable features not needed for SVG rendering
2. **Toolchain flags** — `-D_WASI_EMULATED_*`, `-include` headers
3. **Injected compatibility headers** — `native/wasi_stubs.h` for missing POSIX stubs
4. **Automated preparation scripts** — `scripts/prepare_graphviz_wasi.py` for build-file transforms

Manual edits to Graphviz source files are never allowed.

## Version upgrade workflow

To upgrade to a new Graphviz version:

```bash
GRAPHVIZ_VERSION="15.0.0"
# ... repeat steps 1-8 above ...
```

If the build fails, triage in this order:

1. Is the failing feature unnecessary? → Add a `-DENABLE_*=OFF` or `-DWITH_*=OFF` flag.
2. Is it a missing WASI libc feature? → Add a `-D_WASI_EMULATED_*` flag in the toolchain.
3. Is it a missing POSIX function safe to stub? → Add it to `native/wasi_stubs.h`.
4. Is it a CMake logic issue? → Update `scripts/prepare_graphviz_wasi.py`.
5. Does it affect the core render path and cannot be stubbed? → Reconsider the supported feature set before patching.

## Files involved

| File | Purpose |
|------|---------|
| `native/main.c` | Plain C wrapper exposing Graphviz ABI |
| `native/wasi_stubs.h` | POSIX stubs for WASI builds |
| `native/wasm32-wasi-toolchain.cmake` | CMake cross-compilation toolchain |
| `native/zig-cc`, `native/zig-c++` | Zig compiler wrappers |
| `native/zig-ar`, `native/zig-ranlib` | Zig archiver wrappers |
| `scripts/prepare_graphviz_wasi.py` | Idempotent source preparation script |
| `build/graphviz.wasm` | Final WASM artifact |
| `src/wasi_graphviz/assets/graphviz.wasm` | Vendored artifact for distribution |
