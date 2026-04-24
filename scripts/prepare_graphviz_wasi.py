#!/usr/bin/env python3
"""Prepare a clean Graphviz source tree for wasm32-wasi cross-compilation.

This script applies deterministic, version-tolerant transforms to the Graphviz
source before CMake configure.  It is the last resort in the compatibility
strategy after CMake options, toolchain flags, and injected headers.

Usage:
    python scripts/prepare_graphviz_wasi.py build/src/graphviz-14.1.5

Rules:
- The script must be idempotent.
- Each transform documents WHY it exists.
- The script fails loudly if an expected pattern is not found.
- No hand-editing of Graphviz source files is allowed outside this script.
"""

import argparse
import sys
from pathlib import Path


def _comment_out_line(filepath: Path, marker: str) -> None:
    """Comment out a line containing *marker* in *filepath*.

    Idempotent: if the line is already commented, does nothing.
    Fails loudly if the line is not found.
    """
    content = filepath.read_text()
    lines = content.splitlines(keepends=True)

    found = False
    already_done = False
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if marker in line:
            if stripped.startswith("#"):
                already_done = True
            else:
                new_lines.append(f"# {line}")
                found = True
                continue
        new_lines.append(line)

    if not found and not already_done:
        print(
            f"ERROR: Expected pattern '{marker}' not found in {filepath}",
            file=sys.stderr,
        )
        sys.exit(1)

    if already_done and not found:
        print(f"Skipped {filepath}: '{marker}' already commented out")
        return

    filepath.write_text("".join(new_lines))
    print(f"Patched {filepath}: commented out '{marker}'")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("srcdir", type=Path, help="Path to Graphviz source directory")
    args = parser.parse_args()

    srcdir = args.srcdir.resolve()
    if not srcdir.is_dir():
        print(f"ERROR: {srcdir} is not a directory", file=sys.stderr)
        sys.exit(1)

    lib_cmake = srcdir / "lib" / "CMakeLists.txt"
    if not lib_cmake.exists():
        print(f"ERROR: {lib_cmake} not found", file=sys.stderr)
        sys.exit(1)

    # WHY: lib/gvpr uses setjmp/longjmp which WASI libc does not support.
    # gvpr is the GraphViz Pattern Processing Language (a scripting tool),
    # not needed for DOT->SVG rendering.
    _comment_out_line(lib_cmake, "add_subdirectory(gvpr)")

    # WHY: lib/expr is only used by gvpr.  Disabling gvpr makes expr unused.
    _comment_out_line(lib_cmake, "add_subdirectory(expr)")

    print("Graphviz source prepared for wasm32-wasi build.")


if __name__ == "__main__":
    main()
