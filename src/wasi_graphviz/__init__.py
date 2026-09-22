"""wasi-graphviz – run Graphviz compiled to WebAssembly from Python."""

from collections.abc import Mapping
from pathlib import Path
from typing import Union

from wasi_graphviz._constants import PACKAGE_WASM_PATH
from wasi_graphviz._exceptions import (
    BackendNotAvailable,
    RenderError,
    WasiGraphvizError,
)

__all__ = [
    "render",
    "WasiGraphvizError",
    "RenderError",
    "BackendNotAvailable",
]

_backends: dict[tuple[str, Path], object] = {}


def _get_backend(name: str, wasm_path: Path):
    """Lazy-load and cache a backend instance."""
    key = (name, wasm_path.resolve())
    if key not in _backends:
        if name == "pywasm":
            try:
                from wasi_graphviz.backends.pywasm_backend import PywasmBackend
            except ImportError as exc:
                raise BackendNotAvailable(
                    "pywasm is not installed. Install it with: uv add pywasm"
                ) from exc
            _backends[key] = PywasmBackend(wasm_path)
        elif name == "wasmtime":
            try:
                from wasi_graphviz.backends.wasmtime_backend import WasmtimeBackend
            except ImportError as exc:
                raise BackendNotAvailable(
                    "wasmtime is not installed. Install it with: uv add wasmtime"
                ) from exc
            _backends[key] = WasmtimeBackend(wasm_path)
        else:
            raise ValueError(f"Unknown backend: {name}")
    return _backends[key]


def render(
    dot_source: str,
    *,
    format: str = "svg",
    engine: str = "dot",
    backend: str = "auto",
    wasm_path: Union[str, Path, None] = None,
    assets: Mapping[str, bytes | bytearray | memoryview] | None = None,
) -> bytes:
    """Render a DOT string to the requested image format.

    Parameters
    ----------
    dot_source:
        The Graphviz DOT source string.
    format:
        Output format (e.g. ``svg``, ``png``, ``dot``).
    engine:
        Layout engine (e.g. ``dot``, ``neato``, ``circo``).
    backend:
        Which Python WASM runtime to use.

        - ``"auto"`` — prefer ``wasmtime``, fall back to ``pywasm``.
        - ``"pywasm"`` — pure-Python backend (works on any CPython,
          but not in Pyodide because it requires ``fcntl``).
        - ``"wasmtime"`` — faster native backend.
    wasm_path:
        Override the path to the ``graphviz.wasm`` artifact.
        Defaults to the vendored copy shipped with the package.
    assets:
        Optional files made available to Graphviz for this render. Keys are
        portable ASCII relative paths under ``/assets`` and values are file
        contents. Reference them from DOT with paths such as
        ``/assets/glyph.svg``. For SVG output, referenced SVG, PNG, GIF, and
        JPEG assets are embedded in the returned SVG as data URIs. Embedding
        applies to Graphviz formats whose base selector is ``svg`` or
        ``svg_inline`` (for example, ``svg:svg:core``), and to image references
        resolved through the graph's ``imagepath`` attribute.

    Returns
    -------
    bytes
        The rendered output.

    Raises
    ------
    RenderError
        If Graphviz cannot render the input.
    BackendNotAvailable
        If the requested backend is not installed.
    ValueError
        If an asset path is unsafe or an SVG image asset has an unsupported
        extension, or a relative SVG image reference is ambiguous.
    """
    path = Path(wasm_path) if wasm_path else PACKAGE_WASM_PATH

    if backend == "auto":
        for candidate in ("wasmtime", "pywasm"):
            try:
                return _get_backend(candidate, path).render(
                    dot_source, format=format, engine=engine, assets=assets
                )
            except BackendNotAvailable:
                continue
        raise BackendNotAvailable(
            "No WASM backend is available. Install at least one of: wasmtime, pywasm"
        )

    return _get_backend(backend, path).render(
        dot_source, format=format, engine=engine, assets=assets
    )
