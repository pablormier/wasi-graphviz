"""Pywasm backend for wasi-graphviz."""

import io
import sys
from pathlib import Path
from typing import Union

import pywasm
from pywasm import wasi

from wasi_graphviz._constants import PACKAGE_WASM_PATH
from wasi_graphviz._exceptions import RenderError


class PywasmBackend:
    """Pure-Python Graphviz backend using pywasm."""

    def __init__(self, wasm_path: Union[str, Path] = PACKAGE_WASM_PATH) -> None:
        self.wasm_path = Path(wasm_path)
        if not self.wasm_path.exists():
            raise FileNotFoundError(f"WASM file not found: {self.wasm_path}")

        self._runtime = pywasm.core.Runtime()
        # pywasm Preview1 accesses sys.stdin.fileno() on construction.
        # When pytest captures stdin this is a pseudofile whose fileno()
        # raises UnsupportedOperation, so we temporarily substitute the
        # real stdin.
        _orig_stdin = sys.stdin
        try:
            try:
                sys.stdin.fileno()
            except (OSError, io.UnsupportedOperation):
                sys.stdin = sys.__stdin__
            self._wasi = wasi.Preview1(args=[], dirs={}, envs={})
        finally:
            sys.stdin = _orig_stdin
        self._wasi.bind(self._runtime)
        self._inst = self._runtime.instance_from_file(str(self.wasm_path))
        self._mem = self._runtime.exported_memory(self._inst, "memory")

    def _malloc(self, size: int) -> int:
        """Allocate memory in the WASM heap."""
        return self._runtime.invocate(self._inst, "malloc", [size])[0]

    def _free(self, addr: int) -> None:
        """Free memory in the WASM heap."""
        self._runtime.invocate(self._inst, "graphviz_free", [addr])

    def _write_string(self, text: str) -> int:
        """Write a null-terminated UTF-8 string into WASM memory."""
        data = (text + "\x00").encode("utf-8")
        addr = self._malloc(len(data))
        self._mem.data[addr : addr + len(data)] = data
        return addr

    def _read_string(self, addr: int, max_len: int = 65536) -> str:
        """Read a null-terminated UTF-8 string from WASM memory."""
        result = bytearray()
        for i in range(addr, addr + max_len):
            b = self._mem.data[i]
            if b == 0:
                break
            result.append(b)
        return result.decode("utf-8")

    def render(
        self, dot_source: str, *, format: str = "svg", engine: str = "dot"
    ) -> bytes:
        """Render a DOT string to the requested format.

        Parameters
        ----------
        dot_source:
            The Graphviz DOT source string.
        format:
            Output format (e.g. ``svg``, ``png``, ``dot``).
        engine:
            Layout engine (e.g. ``dot``, ``neato``, ``circo``).

        Returns
        -------
        bytes
            The rendered output.

        Raises
        ------
        RenderError
            If the rendering fails.
        """
        dot_ptr = self._write_string(dot_source)
        fmt_ptr = self._write_string(format)
        engine_ptr = self._write_string(engine)

        try:
            result_ptr = self._runtime.invocate(
                self._inst, "graphviz_render", [dot_ptr, fmt_ptr, engine_ptr]
            )[0]

            if result_ptr == 0:
                err_ptr = self._runtime.invocate(self._inst, "graphviz_last_error", [])[
                    0
                ]
                error = self._read_string(err_ptr)
                raise RenderError(error or "Graphviz rendering failed")

            result = self._read_string(result_ptr)
            self._free(result_ptr)
            return result.encode("utf-8")
        finally:
            self._free(dot_ptr)
            self._free(fmt_ptr)
            self._free(engine_ptr)
