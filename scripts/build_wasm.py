#!/usr/bin/env python3
"""Build the Graphviz WASI artifact and vendor it into the Python package."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path


GRAPHVIZ_VERSION = "14.1.5"

ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = ROOT / "build"
SRC_DIR = BUILD_DIR / "src"
GRAPHVIZ_TARBALL = SRC_DIR / "graphviz.tar.gz"
CMAKE_BUILD_DIR = BUILD_DIR / "graphviz-cmake"
MAIN_OBJECT = BUILD_DIR / "main.o"
WASM_PATH = BUILD_DIR / "graphviz.wasm"
PACKAGE_WASM_PATH = ROOT / "src" / "wasi_graphviz" / "assets" / "graphviz.wasm"
LINK_LIBS_FILE = BUILD_DIR / "link_libs.txt"


CMAKE_FLAGS = [
    "-DGVPLUGIN_CURRENT=8",
    "-DGVPLUGIN_REVISION=0",
    "-DENABLE_LTDL=OFF",
    "-DWITH_EXPAT=OFF",
    "-DWITH_GVEDIT=OFF",
    "-DWITH_SMYRNA=OFF",
    "-DWITH_ZLIB=OFF",
    "-Duse_win_pre_inst_libs=OFF",
    "-DBUILD_SHARED_LIBS=OFF",
    "-DENABLE_TCL=OFF",
    "-DENABLE_SWIG=OFF",
    "-DENABLE_SHARP=OFF",
    "-DENABLE_D=OFF",
    "-DENABLE_GO=OFF",
    "-DENABLE_JAVASCRIPT=OFF",
    "-DGRAPHVIZ_CLI=OFF",
    "-DWITH_GDK=OFF",
    "-DWITH_GTK=OFF",
    "-DWITH_POPPLER=OFF",
    "-DWITH_RSVG=OFF",
    "-DWITH_WEBP=OFF",
    "-DWITH_QUARTZ=OFF",
    "-DWITH_X=OFF",
    "-DENABLE_GUILE=OFF",
    "-DENABLE_JAVA=OFF",
    "-DENABLE_LUA=OFF",
    "-DENABLE_PERL=OFF",
    "-DENABLE_PHP=OFF",
    "-DENABLE_PYTHON=OFF",
    "-DENABLE_R=OFF",
    "-DENABLE_RUBY=OFF",
    "-Dwith_ipsepcola=OFF",
    "-Dwith_cxx_api=OFF",
    "-Dwith_cxx_tests=OFF",
    "-DCMAKE_BUILD_TYPE=MinSizeRel",
]


WRAPPER_INCLUDE_DIRS = [
    "lib/gvc",
    "lib/cgraph",
    "lib/cdt",
    "lib/common",
    "lib/pathplan",
    "lib/util",
    "lib/ast",
    "lib/xdot",
    "lib/pack",
    "lib/label",
    "lib/neatogen",
]


LINK_LIBS = [
    "plugin/core/libgvplugin_core.a",
    "plugin/dot_layout/libgvplugin_dot_layout.a",
    "plugin/neato_layout/libgvplugin_neato_layout.a",
    "plugin/vt/libgvplugin_vt.a",
    "lib/dotgen/libdotgen.a",
    "lib/neatogen/libneatogen.a",
    "lib/fdpgen/libfdpgen.a",
    "lib/sfdpgen/libsfdpgen.a",
    "lib/twopigen/libtwopigen.a",
    "lib/circogen/libcircogen.a",
    "lib/osage/libosage.a",
    "lib/patchwork/libpatchwork.a",
    "lib/ortho/libortho.a",
    "lib/sparse/libsparse.a",
    "lib/gvc/libgvc.a",
    "lib/common/libcommon.a",
    "lib/pack/libpack.a",
    "lib/label/liblabel.a",
    "lib/xdot/libxdot.a",
    "lib/pathplan/libpathplan.a",
    "lib/cgraph/libcgraph.a",
    "lib/cdt/libcdt.a",
    "lib/util/libutil.a",
    "lib/ast/libast.a",
    "lib/rbtree/librbtree.a",
    "lib/sfio/libsfio.a",
    "lib/edgepaint/libedgepaintlib.a",
]


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def pixi(*args: str) -> list[str]:
    return ["pixi", "run", *args]


def pixi_which(name: str) -> str:
    result = subprocess.run(
        pixi("which", name),
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def graphviz_srcdir(version: str) -> Path:
    return SRC_DIR / f"graphviz-{version}"


def download_source(version: str, *, force: bool) -> Path:
    srcdir = graphviz_srcdir(version)
    if srcdir.exists() and not force:
        print(f"Using existing Graphviz source: {srcdir}")
        return srcdir

    SRC_DIR.mkdir(parents=True, exist_ok=True)
    if force and srcdir.exists():
        shutil.rmtree(srcdir)

    if not GRAPHVIZ_TARBALL.exists() or force:
        url = (
            "https://gitlab.com/graphviz/graphviz/-/archive/"
            f"{version}/graphviz-{version}.tar.gz"
        )
        print(f"Downloading {url}")
        urllib.request.urlretrieve(url, GRAPHVIZ_TARBALL)

    print(f"Extracting {GRAPHVIZ_TARBALL}")
    with tarfile.open(GRAPHVIZ_TARBALL) as tar:
        tar.extractall(SRC_DIR)

    return srcdir


def prepare_source(srcdir: Path) -> None:
    run([sys.executable, "scripts/prepare_graphviz_wasi.py", str(srcdir)])


def configure(srcdir: Path, *, force: bool) -> None:
    if force and CMAKE_BUILD_DIR.exists():
        shutil.rmtree(CMAKE_BUILD_DIR)

    run(
        pixi(
            "cmake",
            "-S",
            str(srcdir),
            "-B",
            str(CMAKE_BUILD_DIR),
            f"-DCMAKE_TOOLCHAIN_FILE={ROOT / 'native' / 'wasm32-wasi-toolchain.cmake'}",
            f"-DBISON_EXECUTABLE={pixi_which('bison')}",
            f"-DFLEX_EXECUTABLE={pixi_which('flex')}",
            *CMAKE_FLAGS,
        )
    )


def build_static_libs() -> None:
    run(pixi("cmake", "--build", str(CMAKE_BUILD_DIR), "--parallel"))


def compile_wrapper(srcdir: Path) -> None:
    include_flags = []
    for include_dir in WRAPPER_INCLUDE_DIRS:
        include_flags.extend(["-I", str(srcdir / include_dir)])
    include_flags.extend(["-I", str(CMAKE_BUILD_DIR)])

    run(
        pixi(
            "zig",
            "cc",
            "-target",
            "wasm32-wasi",
            "-Oz",
            "-flto",
            "-ffunction-sections",
            "-fdata-sections",
            "-D_WASI_EMULATED_SIGNAL",
            *include_flags,
            "-c",
            "native/main.c",
            "-o",
            str(MAIN_OBJECT),
        )
    )


def write_link_libs_file() -> None:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    LINK_LIBS_FILE.write_text(
        "".join(f"{CMAKE_BUILD_DIR / lib}\n" for lib in LINK_LIBS)
    )


def link_wasm() -> None:
    write_link_libs_file()
    run(
        pixi(
            "zig",
            "cc",
            "-target",
            "wasm32-wasi",
            "-Oz",
            "-flto",
            "-Wl,--gc-sections",
            "-Wl,-z,stack-size=2097152",
            "-Wl,--export=graphviz_render",
            "-Wl,--export=graphviz_free",
            "-Wl,--export=graphviz_last_error",
            "-Wl,--export=graphviz_version",
            "-Wl,--export=malloc",
            "-Wl,--export=free",
            "-o",
            str(WASM_PATH),
            str(MAIN_OBJECT),
            f"@{LINK_LIBS_FILE}",
        )
    )


def shrink_wasm() -> None:
    run(pixi("wasm-strip", str(WASM_PATH)))
    run(
        pixi(
            "wasm-opt",
            "-Oz",
            "--strip-producers",
            "--enable-bulk-memory",
            "--enable-bulk-memory-opt",
            "--enable-nontrapping-float-to-int",
            "--enable-sign-ext",
            "--enable-mutable-globals",
            str(WASM_PATH),
            "-o",
            str(WASM_PATH),
        )
    )


def validate_wasm() -> None:
    result = subprocess.run(
        pixi("wasm-objdump", "-x", str(WASM_PATH)),
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )

    forbidden_imports = ["emscripten", "env."]
    for forbidden in forbidden_imports:
        if forbidden in result.stdout:
            raise RuntimeError(f"Unexpected non-WASI import found: {forbidden}")

    for symbol in [
        "graphviz_render",
        "graphviz_free",
        "graphviz_last_error",
        "graphviz_version",
        "malloc",
        "free",
    ]:
        if symbol not in result.stdout:
            raise RuntimeError(f"Missing expected WASM export: {symbol}")


def vendor_wasm() -> None:
    PACKAGE_WASM_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(WASM_PATH, PACKAGE_WASM_PATH)
    print(f"Copied {WASM_PATH} -> {PACKAGE_WASM_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graphviz-version", default=GRAPHVIZ_VERSION)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-extract source and recreate the CMake build directory.",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Require an existing build/src/graphviz-<version> source tree.",
    )
    args = parser.parse_args()

    if args.skip_download:
        srcdir = graphviz_srcdir(args.graphviz_version)
        if not srcdir.exists():
            raise SystemExit(f"Missing source directory: {srcdir}")
    else:
        srcdir = download_source(args.graphviz_version, force=args.force)

    prepare_source(srcdir)
    configure(srcdir, force=args.force)
    build_static_libs()
    compile_wrapper(srcdir)
    link_wasm()
    shrink_wasm()
    validate_wasm()
    vendor_wasm()

    print(f"Built {WASM_PATH}")


if __name__ == "__main__":
    main()
