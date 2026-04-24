"""Exceptions for wasi-graphviz."""


class WasiGraphvizError(Exception):
    """Base exception for wasi-graphviz errors."""


class RenderError(WasiGraphvizError):
    """Raised when graph rendering fails."""


class BackendNotAvailable(WasiGraphvizError):
    """Raised when a requested backend is not installed."""
