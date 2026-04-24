"""Core constants for wasi-graphviz."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
EXTERNAL_DIR = PROJECT_ROOT / "external"
NATIVE_DIR = PROJECT_ROOT / "native"
BUILD_DIR = PROJECT_ROOT / "build"
DEFAULT_WASM_PATH = BUILD_DIR / "graphviz.wasm"
ASSETS_DIR = Path(__file__).resolve().parent / "assets"
PACKAGE_WASM_PATH = ASSETS_DIR / "graphviz.wasm"
