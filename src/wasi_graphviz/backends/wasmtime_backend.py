"""Wasmtime backend for wasi-graphviz."""

import struct
from pathlib import Path
from typing import Union

import wasmtime

from wasi_graphviz._constants import PACKAGE_WASM_PATH
from wasi_graphviz._exceptions import RenderError


class WasmtimeBackend:
    """Fast Graphviz backend using wasmtime."""

    def __init__(self, wasm_path: Union[str, Path] = PACKAGE_WASM_PATH) -> None:
        self.wasm_path = Path(wasm_path)
        if not self.wasm_path.exists():
            raise FileNotFoundError(f"WASM file not found: {self.wasm_path}")

        self._engine = wasmtime.Engine()
        self._store = wasmtime.Store(self._engine)
        self._module = wasmtime.Module.from_file(self._engine, str(self.wasm_path))

        linker = wasmtime.Linker(self._engine)
        linker.define_wasi()

        wasi_config = wasmtime.WasiConfig()
        wasi_config.inherit_stdout()
        self._store.set_wasi(wasi_config)

        self._instance = linker.instantiate(self._store, self._module)
        self._mem = self._instance.exports(self._store)["memory"]
        self._render_fn = self._instance.exports(self._store)["graphviz_render"]
        self._free_fn = self._instance.exports(self._store)["graphviz_free"]
        self._malloc_fn = self._instance.exports(self._store)["malloc"]
        self._last_error_fn = self._instance.exports(self._store)["graphviz_last_error"]

    def _malloc(self, size: int) -> int:
        return self._malloc_fn(self._store, size)

    def _free(self, addr: int) -> None:
        self._free_fn(self._store, addr)

    def _write_string(self, text: str) -> int:
        data = (text + "\x00").encode("utf-8")
        addr = self._malloc(len(data))
        self._mem.write(self._store, data, addr)
        return addr

    def _read_bytes(self, addr: int, length: int) -> bytes:
        return bytes(self._mem.read(self._store, addr, addr + length))

    def _read_cstring(self, addr: int, max_len: int = 4096) -> str:
        buf = self._mem.read(self._store, addr, addr + max_len)
        nul = buf.find(0)
        if nul >= 0:
            buf = buf[:nul]
        return bytes(buf).decode("utf-8", errors="replace")

    def _read_u32(self, addr: int) -> int:
        return struct.unpack("<I", self._mem.read(self._store, addr, addr + 4))[0]

    def render(
        self, dot_source: str, *, format: str = "svg", engine: str = "dot"
    ) -> bytes:
        """Render a DOT string to the requested format."""
        dot_ptr = self._write_string(dot_source)
        fmt_ptr = self._write_string(format)
        engine_ptr = self._write_string(engine)
        out_len_ptr = self._malloc(4)

        try:
            result_ptr = self._render_fn(
                self._store, dot_ptr, fmt_ptr, engine_ptr, out_len_ptr
            )

            if result_ptr == 0:
                err_ptr = self._last_error_fn(self._store)
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
