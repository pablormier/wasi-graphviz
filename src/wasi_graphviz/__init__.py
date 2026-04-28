"""wasi-graphviz – run Graphviz compiled to WebAssembly from Python."""

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

_backends: dict[str, object] = {}


def _get_backend(name: str, wasm_path: Path):
    """Lazy-load and cache a backend instance."""
    if name not in _backends:
        if name == "pywasm":
            try:
                from wasi_graphviz.backends.pywasm_backend import PywasmBackend
            except ImportError as exc:
                raise BackendNotAvailable(
                    "pywasm is not installed. Install it with: uv add pywasm"
                ) from exc
            _backends[name] = PywasmBackend(wasm_path)
        elif name == "wasmtime":
            try:
                from wasi_graphviz.backends.wasmtime_backend import WasmtimeBackend
            except ImportError as exc:
                raise BackendNotAvailable(
                    "wasmtime is not installed. Install it with: uv add wasmtime"
                ) from exc
            _backends[name] = WasmtimeBackend(wasm_path)
        else:
            raise ValueError(f"Unknown backend: {name}")
    return _backends[name]


def render(
    dot_source: str,
    *,
    format: str = "svg",
    engine: str = "dot",
    backend: str = "auto",
    wasm_path: Union[str, Path, None] = None,
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
    """
    path = Path(wasm_path) if wasm_path else PACKAGE_WASM_PATH

    if backend == "auto":
        for candidate in ("wasmtime", "pywasm"):
            try:
                return _get_backend(candidate, path).render(
                    dot_source, format=format, engine=engine
                )
            except BackendNotAvailable:
                continue
        raise BackendNotAvailable(
            "No WASM backend is available. Install at least one of: wasmtime, pywasm"
        )

    return _get_backend(backend, path).render(dot_source, format=format, engine=engine)
