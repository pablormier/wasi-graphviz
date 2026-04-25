"""Pywasm backend for wasi-graphviz."""

import io
import struct
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
        return self._runtime.invocate(self._inst, "malloc", [size])[0]

    def _free(self, addr: int) -> None:
        self._runtime.invocate(self._inst, "graphviz_free", [addr])

    def _write_string(self, text: str) -> int:
        data = (text + "\x00").encode("utf-8")
        addr = self._malloc(len(data))
        self._mem.data[addr : addr + len(data)] = data
        return addr

    def _read_bytes(self, addr: int, length: int) -> bytes:
        return bytes(self._mem.data[addr : addr + length])

    def _read_cstring(self, addr: int, max_len: int = 4096) -> str:
        buf = bytes(self._mem.data[addr : addr + max_len])
        nul = buf.find(0)
        if nul >= 0:
            buf = buf[:nul]
        return buf.decode("utf-8", errors="replace")

    def _read_u32(self, addr: int) -> int:
        return struct.unpack("<I", bytes(self._mem.data[addr : addr + 4]))[0]

    def render(
        self, dot_source: str, *, format: str = "svg", engine: str = "dot"
    ) -> bytes:
        """Render a DOT string to the requested format."""
        dot_ptr = self._write_string(dot_source)
        fmt_ptr = self._write_string(format)
        engine_ptr = self._write_string(engine)
        out_len_ptr = self._malloc(4)

        try:
            result_ptr = self._runtime.invocate(
                self._inst,
                "graphviz_render",
                [dot_ptr, fmt_ptr, engine_ptr, out_len_ptr],
            )[0]

            if result_ptr == 0:
                err_ptr = self._runtime.invocate(
                    self._inst, "graphviz_last_error", []
                )[0]
                error = self._read_cstring(err_ptr)
                raise RenderError(error or "Graphviz rendering failed")

            out_len = self._read_u32(out_len_ptr)
            try:
                return self._read_bytes(result_ptr, out_len)
            finally:
                self._free(result_ptr)
        finally:
            self._free(dot_ptr)
            self._free(fmt_ptr)
            self._free(engine_ptr)
            self._free(out_len_ptr)
