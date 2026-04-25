"""Core constants for wasi-graphviz."""

from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
PACKAGE_WASM_PATH = ASSETS_DIR / "graphviz.wasm"
